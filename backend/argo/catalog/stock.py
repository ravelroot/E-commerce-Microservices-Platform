"""Regras de estoque. Toda alteração trava as linhas dos produtos (SELECT ... FOR UPDATE),
grava um movimento no livro-razão e publica o novo saldo depois do COMMIT."""

from __future__ import annotations

from django.db import router, transaction

from argo.common.errors import ApiError, not_found
from argo.common.events import STOCK_CHANNEL, get_bus
from argo.common.utils import utcnow

from .models import Product, StockMovement

DEFAULT_REASON = {"IN": "Entrada manual", "OUT": "Saída manual", "COUNT": "Contagem de inventário"}


def atomic():
    return transaction.atomic(using=router.db_for_write(Product))


def stock_event(product: Product, movement: StockMovement) -> dict:
    return {
        "product_id": product.id,
        "sku": product.sku,
        "name": product.name,
        "seller_id": product.seller_id,
        "stock": product.stock,
        "delta": movement.delta,
        "kind": movement.kind,
        "low": product.is_low,
        "order_id": movement.order_id,
        "at": utcnow().isoformat(),
    }


def _publish_on_commit(events: list[dict]) -> None:
    def send() -> None:
        bus = get_bus()
        for event in events:
            bus.publish(STOCK_CHANNEL, event)

    transaction.on_commit(send, using=router.db_for_write(Product))


def _lock(ids) -> dict[str, Product]:
    rows = Product.objects.select_for_update().filter(id__in=sorted(set(ids))).order_by("id")
    return {p.id: p for p in rows}


def _move(product: Product, kind: str, delta: int, reason: str, order_id=None, actor_id=None) -> StockMovement:
    product.stock += delta
    product.version += 1
    product.save(update_fields=["stock", "version"])
    return StockMovement.objects.create(
        product=product,
        kind=kind,
        delta=delta,
        stock_after=product.stock,
        reason=reason,
        order_id=order_id,
        actor_id=actor_id,
    )


def adjust(product_id: str, kind: str, quantity: int, reason: str, actor_id: str | None) -> Product:
    with atomic():
        product = _lock([product_id]).get(product_id)
        if product is None:
            raise not_found("Produto")
        if kind == "IN":
            delta = quantity
        elif kind == "OUT":
            if quantity > product.stock:
                raise ApiError(409, "insufficient_stock", f"Só há {product.stock} unidade(s) em estoque.")
            delta = -quantity
        else:
            delta = quantity - product.stock
        if delta == 0 and kind != "COUNT":
            raise ApiError(422, "validation_error", "Informe uma quantidade maior que zero.", {"quantity": "Maior que zero."})
        movement = _move(product, kind, delta, reason or DEFAULT_REASON[kind], actor_id=actor_id)
        _publish_on_commit([stock_event(product, movement)])
    return product


def commit_order(order_id: int, lines: list[tuple[str, int]]) -> dict:
    """Baixa o estoque de um pedido inteiro ou de nada. Repetir a chamada não baixa de novo."""
    if StockMovement.objects.filter(order_id=order_id, kind="SALE").exists():
        return {"ok": True, "already_processed": True, "shortages": []}

    wanted: dict[str, int] = {}
    for pid, qty in lines:
        wanted[pid] = wanted.get(pid, 0) + qty
    with atomic():
        products = _lock(wanted)
        shortages = []
        for pid, qty in wanted.items():
            p = products.get(pid)
            if p is None or not p.active or p.stock < qty:
                shortages.append(
                    {
                        "product_id": pid,
                        "name": p.name if p else "Produto removido",
                        "requested": qty,
                        "available": p.stock if p and p.active else 0,
                    }
                )
        if shortages:
            return {"ok": False, "already_processed": False, "shortages": shortages}
        events = []
        for pid, qty in wanted.items():
            p = products[pid]
            mv = _move(p, "SALE", -qty, f"Venda do pedido {order_id}", order_id=order_id)
            events.append(stock_event(p, mv))
        _publish_on_commit(events)
    return {"ok": True, "already_processed": False, "shortages": []}


def release_order(order_id: int) -> int:
    """Devolve ao estoque o que o pedido baixou. Idempotente por produto."""
    sales = list(StockMovement.objects.filter(order_id=order_id, kind="SALE"))
    if not sales:
        return 0
    already = set(StockMovement.objects.filter(order_id=order_id, kind="RELEASE").values_list("product_id", flat=True))
    pending = [s for s in sales if s.product_id not in already]
    if not pending:
        return 0
    with atomic():
        products = _lock([s.product_id for s in pending])
        events = []
        for sale in pending:
            p = products[sale.product_id]
            mv = _move(p, "RELEASE", -sale.delta, f"Cancelamento do pedido {order_id}", order_id=order_id)
            events.append(stock_event(p, mv))
        _publish_on_commit(events)
    return len(events)
