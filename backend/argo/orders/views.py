"""API de pedidos (Django REST Framework): checkout assíncrono, consulta, cancelamento e indicadores."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response

from argo.common.errors import ApiError, conflict, error_responses, forbidden, not_found
from argo.common.http import call
from argo.common.pagination import paginate
from argo.common.security import InternalToken, IsAuthenticated, Principal, Role, roles
from argo.common.utils import utcnow
from argo.common.validation import valid

from . import clients, services
from .dispatch import get_dispatcher
from .models import Order, OrderItem, OrderStatus, OrderStatusHistory
from .serializers import (
    CancelSerializer,
    CheckoutSerializer,
    InternalEventSerializer,
    OrderPageSerializer,
    OrderQuerySerializer,
    OrderSerializer,
    OrderSummarySerializer,
    StatsQuerySerializer,
    StatsSerializer,
    StatusChangeSerializer,
)

ORDERS = ["Pedidos"]
INTERNAL = ["Interno"]
LOCAL_TZ = ZoneInfo("America/Sao_Paulo")
customer_only = roles(Role.CUSTOMER)
seller_or_admin = roles(Role.ADMIN, Role.SELLER)


def _detail(order_id: int) -> dict:
    return OrderSerializer(services.load(order_id)).data


# ------------------------------------------------------------------ pedidos
@extend_schema(
    tags=ORDERS,
    methods=["GET"],
    operation_id="orders_list",
    summary="Listar pedidos",
    description="Cliente vê os próprios pedidos; vendedor, os pedidos com produtos dele; administrador, todos.",
    parameters=[OrderQuerySerializer],
    responses={200: OrderPageSerializer, **error_responses(401, 422)},
)
@extend_schema(
    tags=ORDERS,
    methods=["POST"],
    summary="Fechar pedido (processamento assíncrono)",
    description="Confere preço e disponibilidade no catálogo, grava o pedido como **PENDING** e responde na hora com "
    "`202 Accepted`. A baixa definitiva no estoque, o e-mail de confirmação e a nota fiscal são feitos pela fila "
    "(Celery + Redis), sem travar a requisição.\n\nAcompanhe a situação em `GET /orders/{id}`: `PENDING` → "
    "`CONFIRMED` ou `REJECTED`.",
    request=CheckoutSerializer,
    responses={202: OrderSerializer, **error_responses(401, 403, 409, 422, 503)},
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def orders(request):
    if request.method == "POST":
        return _checkout(request)
    f = valid(OrderQuerySerializer, request.query_params)
    qs = services.scope(Order.objects.all(), request.user)
    if f.get("status"):
        qs = qs.filter(status=f["status"])
    if f.get("q"):
        q = f["q"]
        digits = "".join(ch for ch in q if ch.isdigit())
        cond = Q(customer_name__icontains=q)
        qs = qs.filter(cond | Q(id=int(digits)) if digits and len(digits) <= 18 else cond)
    qs = qs.order_by("-id")
    return Response(paginate(qs, f["page"], f["size"], lambda o: OrderSummarySerializer(o).data))


def _checkout(request):
    customer_only().has_permission(request, None)
    user: Principal = request.user
    lines = valid(CheckoutSerializer, request.data)["items"]
    resp = call(
        clients.catalog(), "POST", "/internal/products/lookup", "catálogo", json={"ids": [i["product_id"] for i in lines]}
    )
    found = {p["id"]: p for p in resp.json()}
    fields: dict[str, str] = {}
    shortages = []
    for idx, line in enumerate(lines):
        product = found.get(line["product_id"])
        if product is None or not product["active"]:
            fields[f"items.{idx}"] = "Produto indisponível."
        elif product["seller_id"] == user.id:
            fields[f"items.{idx}"] = "Você não pode comprar o próprio produto."
        elif product["stock"] < line["quantity"]:
            shortages.append(f"{product['name']} (disponível: {product['stock']})")
    if fields:
        raise ApiError(422, "validation_error", "Alguns produtos não estão disponíveis.", fields)
    if shortages:
        raise conflict("insufficient_stock", "Estoque insuficiente: " + "; ".join(shortages) + ".")

    items = []
    for line in lines:
        p = found[line["product_id"]]
        items.append(
            OrderItem(
                product_id=p["id"],
                seller_id=p["seller_id"],
                seller_name=p["seller_name"],
                sku=p["sku"],
                product_name=p["name"],
                unit_price_cents=p["price_cents"],
                quantity=line["quantity"],
                subtotal_cents=p["price_cents"] * line["quantity"],
            )
        )
    with services.atomic():
        order = Order.objects.create(
            customer_id=user.id,
            customer_name=user.name,
            customer_email=user.email,
            status="PENDING",
            total_cents=sum(i.subtotal_cents for i in items),
            items_count=sum(i.quantity for i in items),
        )
        for item in items:
            item.order = order
        OrderItem.objects.bulk_create(items)
        OrderStatusHistory.objects.create(order=order, status="PENDING", note=services.STATUS_NOTE["PENDING"], actor=user.name)
        order_id = order.id
        services.on_commit(lambda: get_dispatcher().process(order_id))
    return Response(_detail(order.id), status=202)


@extend_schema(
    tags=ORDERS,
    summary="Indicadores do período",
    description="Faturamento, ticket médio, vendas por dia e mais vendidos. Para o vendedor, considera só\n"
    "os itens dele; para o cliente, só as compras dele.",
    parameters=[StatsQuerySerializer],
    responses={200: StatsSerializer, **error_responses(401, 422)},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def stats(request):
    user: Principal = request.user
    days = valid(StatsQuerySerializer, request.query_params)["days"]
    now = utcnow()
    since = now - timedelta(days=days)
    start_day = (now.astimezone(LOCAL_TZ) - timedelta(days=days - 1)).date()
    rows = services.scope(Order.objects.filter(created_at__gte=since), user).prefetch_related("items")

    by_status: dict[str, int] = {s: 0 for s in OrderStatus.values}
    daily: dict = {start_day + timedelta(days=i): [0, 0] for i in range(days)}
    top: dict[str, list] = defaultdict(lambda: ["", 0, 0])
    revenue = paid = 0
    for order in rows:
        by_status[order.status] += 1
        if order.status not in services.REVENUE_STATUSES:
            continue
        items = [i for i in order.items.all() if user.role != Role.SELLER or i.seller_id == user.id]
        value = sum(i.subtotal_cents for i in items)
        revenue += value
        paid += 1
        day = order.created_at.astimezone(LOCAL_TZ).date()
        if day in daily:
            daily[day][0] += 1
            daily[day][1] += value
        for i in items:
            entry = top[i.product_id]
            entry[0] = i.product_name
            entry[1] += i.quantity
            entry[2] += i.subtotal_cents
    best = sorted(top.items(), key=lambda kv: (-kv[1][2], kv[1][0]))[:5]
    return Response(
        {
            "days": days,
            "revenue_cents": revenue,
            "orders": paid,
            "average_ticket_cents": revenue // paid if paid else 0,
            "processing": by_status["PENDING"],
            "by_status": by_status,
            "daily": [{"day": d.isoformat(), "orders": v[0], "revenue_cents": v[1]} for d, v in sorted(daily.items())],
            "top_products": [{"product_id": k, "name": v[0], "quantity": v[1], "revenue_cents": v[2]} for k, v in best],
        }
    )


@extend_schema(tags=ORDERS, summary="Detalhe do pedido", responses={200: OrderSerializer, **error_responses(401, 404)})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def order_detail(request, order_id: int):
    order = services.load(order_id)
    if not services.can_see(order, request.user):
        raise not_found("Pedido")
    return Response(OrderSerializer(order).data)


@extend_schema(
    tags=ORDERS,
    summary="Cancelar pedido",
    description="Cliente cancela os próprios pedidos e o administrador, qualquer um, enquanto estiverem\n"
    "`PENDING` ou `CONFIRMED`. A devolução ao estoque e o cancelamento da nota vão para a fila.",
    request=CancelSerializer,
    responses={200: OrderSerializer, **error_responses(401, 403, 404, 409)},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cancel(request, order_id: int):
    user: Principal = request.user
    reason = valid(CancelSerializer, request.data or {})["reason"].strip()
    with services.atomic():
        order = services.load(order_id, lock=True)
        if not services.can_see(order, user):
            raise not_found("Pedido")
        if not (user.is_admin or order.customer_id == user.id):
            raise forbidden("Só o cliente ou um administrador pode cancelar este pedido.")
        if order.status not in services.CANCELABLE:
            raise conflict("invalid_status", "Este pedido não pode mais ser cancelado.")
        services.set_status(order, "CANCELED", user.name, reason or services.STATUS_NOTE["CANCELED"])
        services.on_commit(lambda: get_dispatcher().cancel(order_id))
    return Response(_detail(order_id))


@extend_schema(
    tags=ORDERS,
    summary="Marcar como enviado ou entregue",
    description="Administrador altera qualquer pedido; vendedor, os pedidos que têm produtos dele.\n"
    "Sequência válida: `CONFIRMED` → `SHIPPED` → `DELIVERED`.",
    request=StatusChangeSerializer,
    responses={200: OrderSerializer, **error_responses(401, 403, 404, 409, 422)},
)
@api_view(["PATCH"])
@permission_classes([seller_or_admin])
def change_status(request, order_id: int):
    body = valid(StatusChangeSerializer, request.data)
    with services.atomic():
        order = services.load(order_id, lock=True)
        if not services.can_see(order, request.user):
            raise not_found("Pedido")
        if order.status not in services.NEXT_STATUS[body["status"]]:
            raise conflict("invalid_status", f"Não é possível ir de {order.status} para {body['status']}.")
        services.set_status(order, body["status"], request.user.name, body["note"].strip())
    return Response(_detail(order_id))


# ------------------------------------------------------------------ interno
@extend_schema(
    tags=INTERNAL, summary="Pedido completo para o worker", responses={200: OrderSerializer, **error_responses(403, 404)}, auth=[]
)
@api_view(["GET"])
@authentication_classes([])
@permission_classes([InternalToken])
def internal_detail(request, order_id: int):
    return Response(_detail(order_id))


@extend_schema(
    tags=INTERNAL,
    summary="Registrar resultado de uma tarefa da fila",
    description="Idempotente: repetir o mesmo evento não muda o pedido nem duplica o histórico.",
    request=InternalEventSerializer,
    responses={200: OrderSerializer, **error_responses(403, 404, 422)},
    auth=[],
)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([InternalToken])
def internal_event(request, order_id: int):
    body = valid(InternalEventSerializer, request.data)
    order = services.apply_event(order_id, body["type"], reason=body.get("reason"), invoice_number=body.get("invoice_number"))
    return Response(OrderSerializer(order).data)
