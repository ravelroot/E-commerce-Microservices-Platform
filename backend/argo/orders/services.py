"""Regras dos pedidos: visibilidade por papel, transições de situação e eventos da fila."""

from __future__ import annotations

from django.db import router, transaction
from django.db.models import Prefetch, QuerySet

from argo.common.errors import not_found
from argo.common.security import Principal, Role
from argo.common.utils import utcnow

from .models import Order, OrderItem, OrderStatusHistory

REVENUE_STATUSES = ("CONFIRMED", "SHIPPED", "DELIVERED")
CANCELABLE = ("PENDING", "CONFIRMED")
NEXT_STATUS = {"SHIPPED": ("CONFIRMED",), "DELIVERED": ("SHIPPED",)}
STATUS_NOTE = {
    "PENDING": "Pedido recebido. Reservando estoque.",
    "CONFIRMED": "Estoque reservado e pedido confirmado.",
    "REJECTED": "Pedido recusado.",
    "SHIPPED": "Pedido enviado.",
    "DELIVERED": "Pedido entregue.",
    "CANCELED": "Pedido cancelado.",
}


def atomic():
    return transaction.atomic(using=router.db_for_write(Order))


def on_commit(fn) -> None:
    transaction.on_commit(fn, using=router.db_for_write(Order))


def with_details(qs: QuerySet[Order] | None = None) -> QuerySet[Order]:
    qs = Order.objects.all() if qs is None else qs
    return qs.prefetch_related(
        Prefetch("items", queryset=OrderItem.objects.order_by("id")),
        Prefetch("history", queryset=OrderStatusHistory.objects.order_by("id")),
    )


def load(order_id: int, *, lock: bool = False) -> Order:
    qs = Order.objects.select_for_update() if lock else Order.objects.all()
    order = with_details(qs.filter(pk=order_id)).first()
    if order is None:
        raise not_found("Pedido")
    return order


def can_see(order: Order, user: Principal) -> bool:
    if user.is_admin or order.customer_id == user.id:
        return True
    return user.role == Role.SELLER and any(i.seller_id == user.id for i in order.items.all())


def scope(qs: QuerySet[Order], user: Principal) -> QuerySet[Order]:
    """Cliente vê os próprios pedidos; vendedor, os que têm produtos dele; administrador, todos."""
    if user.role == Role.CUSTOMER:
        return qs.filter(customer_id=user.id)
    if user.role == Role.SELLER:
        return qs.filter(id__in=OrderItem.objects.filter(seller_id=user.id).values("order_id"))
    return qs


def history(order: Order, status: str, note: str, actor: str) -> None:
    OrderStatusHistory.objects.create(order=order, status=status, note=note, actor=actor)


def set_status(order: Order, new: str, actor: str, note: str = "") -> None:
    order.status = new
    order.updated_at = utcnow()
    order.save(update_fields=["status", "updated_at", "rejection_reason"])
    history(order, new, note or STATUS_NOTE[new], actor)


def apply_event(order_id: int, type_: str, *, reason: str | None = None, invoice_number: str | None = None) -> Order:
    """Resultado de uma tarefa da fila. Idempotente: repetir o evento não muda nada."""
    with atomic():
        order = load(order_id, lock=True)
        if type_ == "confirmed" and order.status == "PENDING":
            set_status(order, "CONFIRMED", "Fila de pedidos")
        elif type_ == "rejected" and order.status == "PENDING":
            order.rejection_reason = reason or "Estoque insuficiente."
            set_status(order, "REJECTED", "Fila de pedidos", order.rejection_reason)
        elif type_ == "invoiced" and invoice_number and not order.invoice_number:
            order.invoice_number = invoice_number
            order.save(update_fields=["invoice_number"])
            history(order, order.status, f"Nota fiscal {invoice_number} emitida.", "Faturamento")
        elif type_ == "email_sent" and order.email_sent_at is None:
            order.email_sent_at = utcnow()
            order.save(update_fields=["email_sent_at"])
        elif type_ == "released" and order.status == "CANCELED":
            history(order, "CANCELED", "Itens devolvidos ao estoque.", "Fila de pedidos")
    return load(order_id)
