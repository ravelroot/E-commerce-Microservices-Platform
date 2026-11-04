from __future__ import annotations

import asyncio
import contextlib
import json

from django.db import IntegrityError
from django.db.models import Case, Count, F, IntegerField, Q, Sum, When
from django.db.models.functions import Coalesce
from django.http import JsonResponse, StreamingHttpResponse
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, authentication_classes, permission_classes, renderer_classes
from rest_framework.response import Response

from argo.common.errors import ApiError, body, conflict, error_responses, forbidden, not_found
from argo.common.events import STOCK_CHANNEL, get_bus
from argo.common.export import CSV_RESPONSE, EXPORT_RENDERERS, csv_response, decimal_brl, local_datetime, yes_no
from argo.common.pagination import paginate
from argo.common.security import InternalToken, IsAuthenticated, Principal, Role, bearer_token, decode_access_token, roles
from argo.common.validation import valid

from . import stock
from .models import LOW_STOCK, Product, StockMovement
from .serializers import (
    CategoryCountSerializer,
    FeedMovementSerializer,
    FeedPageSerializer,
    FeedQuerySerializer,
    LookupSerializer,
    MovementPageSerializer,
    MovementSerializer,
    PageQuerySerializer,
    ProductCreateSerializer,
    ProductPageSerializer,
    ProductQuerySerializer,
    ProductSerializer,
    ProductSnapshotSerializer,
    ProductUpdateSerializer,
    StockAdjustSerializer,
    StockCommitResultSerializer,
    StockCommitSerializer,
    StockReleaseResultSerializer,
    StockReleaseSerializer,
    StockSummarySerializer,
)

PRODUCTS = ["Produtos"]
INVENTORY = ["Estoque"]
INTERNAL = ["Interno"]
seller_or_admin = roles(Role.SELLER, Role.ADMIN)

SORTS = {
    "name": ("name",),
    "price_asc": ("price_cents", "name"),
    "price_desc": ("-price_cents", "name"),
    "newest": ("-created_at",),
    "stock": ("stock", "name"),
}


def _owned(product_id: str, user: Principal) -> Product:
    product = Product.objects.filter(pk=product_id).first()
    if product is None:
        raise not_found("Produto")
    if not user.is_admin and product.seller_id != user.id:
        raise forbidden("Este produto pertence a outro vendedor.")
    return product


def _data(product: Product) -> dict:
    return ProductSerializer(product).data


@extend_schema(
    tags=PRODUCTS,
    methods=["GET"],
    operation_id="products_list",
    summary="Listar e buscar produtos",
    parameters=[ProductQuerySerializer],
    responses={200: ProductPageSerializer, **error_responses(401, 422)},
)
@extend_schema(
    tags=PRODUCTS,
    methods=["POST"],
    summary="Cadastrar produto",
    description="O produto fica vinculado ao vendedor logado. O estoque inicial gera um movimento de entrada.",
    request=ProductCreateSerializer,
    responses={201: ProductSerializer, **error_responses(401, 403, 409, 422)},
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def products(request):
    if request.method == "POST":
        return _create(request)
    f = valid(ProductQuerySerializer, request.query_params)
    qs = _filtered(f, request.user)
    return Response(paginate(qs, f["page"], f["size"], _data))


def _filtered(f: dict, user: Principal):
    qs = Product.objects.all()
    if f["mine"]:
        qs = qs.filter(seller_id=user.id)
    elif f.get("seller_id"):
        qs = qs.filter(seller_id=f["seller_id"])
    can_see_inactive = user.is_admin or (user.role == Role.SELLER and f["mine"])
    if not (f["include_inactive"] and can_see_inactive):
        qs = qs.filter(active=True)
    if f.get("q"):
        q = f["q"]
        qs = qs.filter(Q(name__icontains=q) | Q(sku__icontains=q) | Q(seller_name__icontains=q))
    if f.get("category"):
        qs = qs.filter(category=f["category"])
    if f["low_stock"]:
        qs = qs.filter(LOW_STOCK)
    if f["in_stock"]:
        qs = qs.filter(stock__gt=0)
    if f.get("min_price") is not None:
        qs = qs.filter(price_cents__gte=f["min_price"])
    if f.get("max_price") is not None:
        qs = qs.filter(price_cents__lte=f["max_price"])
    return qs.order_by(*SORTS[f["sort"]])


EXPORT_HEADER = [
    "SKU",
    "Nome",
    "Categoria",
    "Loja",
    "Preço (R$)",
    "Estoque",
    "Estoque mínimo",
    "Valor em estoque (R$)",
    "Ativo",
    "Criado em",
    "Atualizado em",
]


@extend_schema(
    tags=PRODUCTS,
    summary="Exportar produtos em CSV",
    description="Mesmos filtros da listagem, sem paginação. Vendedor exporta só os próprios produtos.\n"
    "O arquivo usa `;` como separador e vírgula decimal, pronto para abrir no Excel ou no LibreOffice.",
    parameters=[ProductQuerySerializer],
    responses={**CSV_RESPONSE, **error_responses(401, 403, 422)},
)
@api_view(["GET"])
@renderer_classes(EXPORT_RENDERERS)
@permission_classes([seller_or_admin])
def export_products(request):
    f = valid(ProductQuerySerializer, request.query_params)
    if not request.user.is_admin:
        f["mine"] = True
    qs = _filtered(f, request.user)
    rows = (
        [
            p.sku,
            p.name,
            p.category,
            p.seller_name,
            decimal_brl(p.price_cents),
            p.stock,
            p.low_stock_threshold,
            decimal_brl(p.stock * p.price_cents),
            yes_no(p.active),
            local_datetime(p.created_at),
            local_datetime(p.updated_at),
        ]
        for p in qs.iterator(chunk_size=500)
    )
    return csv_response("argo-produtos.csv", EXPORT_HEADER, rows)


def _create(request):
    roles_check = seller_or_admin()
    roles_check.has_permission(request, None)
    user: Principal = request.user
    data = valid(ProductCreateSerializer, request.data)
    initial = data.pop("stock")
    try:
        with stock.atomic():
            product = Product.objects.create(seller_id=user.id, seller_name=user.name, stock=0, **data)
            if initial:
                product = stock.adjust(product.id, "IN", initial, "Estoque inicial", user.id)
    except IntegrityError as exc:
        raise conflict("sku_taken", "Já existe um produto com este SKU.") from exc
    return Response(_data(product), status=201)


@extend_schema(
    tags=PRODUCTS,
    summary="Categorias com produtos ativos",
    responses={200: CategoryCountSerializer(many=True), **error_responses(401)},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def categories(request):
    rows = Product.objects.filter(active=True).values("category").annotate(products=Count("id")).order_by("category")
    return Response([{"name": r["category"], "products": r["products"]} for r in rows])


@extend_schema(
    tags=PRODUCTS,
    methods=["GET"],
    summary="Detalhe do produto",
    responses={200: ProductSerializer, **error_responses(401, 404)},
)
@extend_schema(
    tags=PRODUCTS,
    methods=["PUT"],
    summary="Editar produto",
    request=ProductUpdateSerializer,
    responses={200: ProductSerializer, **error_responses(401, 403, 404, 409, 422)},
)
@extend_schema(
    tags=PRODUCTS,
    methods=["DELETE"],
    summary="Desativar produto",
    description="Exclusão lógica: o produto some da loja, mas o histórico de pedidos e estoque continua íntegro.",
    responses={204: None, **error_responses(401, 403, 404)},
)
@api_view(["GET", "PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def product_detail(request, product_id: str):
    user: Principal = request.user
    if request.method == "GET":
        product = Product.objects.filter(pk=product_id).first()
        if product is None or (not product.active and not (user.is_admin or product.seller_id == user.id)):
            raise not_found("Produto")
        return Response(_data(product))

    seller_or_admin().has_permission(request, None)
    if request.method == "DELETE":
        with stock.atomic():
            product = _owned(product_id, user)
            product.active = False
            product.version += 1
            product.save(update_fields=["active", "version"])
        return Response(status=204)

    data = valid(ProductUpdateSerializer, request.data)
    with stock.atomic():
        product = _owned(product_id, user)
        version = data.pop("version", None)
        if version is not None and version != product.version:
            raise conflict("version_conflict", "O produto foi alterado por outra pessoa. Recarregue e tente de novo.")
        for field, value in data.items():
            if value is not None:
                setattr(product, field, " ".join(value.split()) if field in ("name", "category") else value)
        product.version += 1
        product.save()
    return Response(_data(product))


@extend_schema(
    tags=PRODUCTS,
    summary="Movimentar estoque",
    description="Entrada, saída ou contagem. A linha do produto é travada durante a operação e o novo\n"
    "saldo é publicado na hora para todas as telas abertas (`GET /stock/stream`).",
    request=StockAdjustSerializer,
    responses={200: ProductSerializer, **error_responses(401, 403, 404, 409, 422)},
)
@api_view(["POST"])
@permission_classes([seller_or_admin])
def adjust_stock(request, product_id: str):
    data = valid(StockAdjustSerializer, request.data)
    _owned(product_id, request.user)
    product = stock.adjust(product_id, data["kind"], data["quantity"], data["reason"].strip(), request.user.id)
    return Response(_data(product))


@extend_schema(
    tags=PRODUCTS,
    summary="Histórico de estoque",
    parameters=[PageQuerySerializer],
    responses={200: MovementPageSerializer, **error_responses(401, 403, 404)},
)
@api_view(["GET"])
@permission_classes([seller_or_admin])
def movements(request, product_id: str):
    _owned(product_id, request.user)
    f = valid(PageQuerySerializer, request.query_params)
    qs = StockMovement.objects.filter(product_id=product_id).order_by("-id")
    return Response(paginate(qs, f["page"], f["size"], lambda m: MovementSerializer(m).data))


@extend_schema(
    tags=INVENTORY,
    summary="Últimas movimentações de estoque",
    description="Administrador vê as de toda a plataforma; vendedor, só as dos produtos dele. Mais recentes primeiro.",
    parameters=[FeedQuerySerializer],
    responses={200: FeedPageSerializer, **error_responses(401, 403, 422)},
)
@api_view(["GET"])
@permission_classes([seller_or_admin])
def feed(request):
    f = valid(FeedQuerySerializer, request.query_params)
    qs = StockMovement.objects.select_related("product")
    if not request.user.is_admin:
        qs = qs.filter(product__seller_id=request.user.id)
    if f.get("kind"):
        qs = qs.filter(kind=f["kind"])
    if f.get("product_id"):
        qs = qs.filter(product_id=f["product_id"])
    qs = qs.order_by("-id")
    return Response(paginate(qs, f["page"], f["size"], lambda m: FeedMovementSerializer(m).data))


@extend_schema(
    tags=INVENTORY,
    summary="Resumo do estoque",
    description="Administrador vê o estoque de toda a plataforma; vendedor, só o dele.",
    responses={200: StockSummarySerializer, **error_responses(401, 403)},
)
@api_view(["GET"])
@permission_classes([seller_or_admin])
def summary(request):
    qs = Product.objects.filter(active=True)
    if not request.user.is_admin:
        qs = qs.filter(seller_id=request.user.id)
    zero = 0
    totals = qs.aggregate(
        products=Count("id"),
        units=Coalesce(Sum("stock"), zero),
        low_stock=Coalesce(Sum(Case(When(LOW_STOCK, then=1), default=0, output_field=IntegerField())), zero),
        out_of_stock=Coalesce(Sum(Case(When(stock=0, then=1), default=0, output_field=IntegerField())), zero),
        inventory_value_cents=Coalesce(Sum(F("stock") * F("price_cents"), output_field=IntegerField()), zero),
    )
    return Response(totals)


async def sse_stream(events, heartbeat: float = 15.0):
    yield "event: ready\ndata: {}\n\n"
    iterator = aiter(events)
    pending: asyncio.Future | None = None
    try:
        while True:
            if pending is None:
                pending = asyncio.ensure_future(anext(iterator))
            done, _ = await asyncio.wait({pending}, timeout=heartbeat)
            if not done:
                yield ": ping\n\n"
                continue
            try:
                event = pending.result()
            except StopAsyncIteration:
                break
            finally:
                if pending.done():
                    pending = None
            yield f"event: stock\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
    finally:
        if pending is not None:
            pending.cancel()
            with contextlib.suppress(asyncio.CancelledError, StopAsyncIteration, Exception):
                await pending
        close = getattr(iterator, "aclose", None)
        if close is not None:
            with contextlib.suppress(Exception):
                await close()


async def stock_stream(request):
    if request.method != "GET":
        return JsonResponse(body("method_not_allowed", "Método não permitido nesta rota."), status=405)
    token = bearer_token(request)
    if not token:
        response = JsonResponse(body("unauthorized", "Envie o cabeçalho Authorization: Bearer <token>."), status=401)
        response["WWW-Authenticate"] = "Bearer"
        return response
    try:
        decode_access_token(token)
    except ApiError as exc:
        response = JsonResponse(body(exc.code, exc.message), status=exc.status)
        response["WWW-Authenticate"] = "Bearer"
        return response
    response = StreamingHttpResponse(sse_stream(get_bus().subscribe(STOCK_CHANNEL)), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


STREAM_DOC = {
    "/stock/stream": {
        "get": {
            "operationId": "stock_stream",
            "tags": INVENTORY,
            "summary": "Estoque em tempo real (Server-Sent Events)",
            "description": "Mantém a conexão aberta e envia `event: stock` a cada venda, cancelamento ou ajuste, "
            "com `product_id`, `stock`, `delta`, `kind` e `low` (estoque baixo). A cada 15 s sem eventos "
            "chega um comentário `: ping` para a conexão não cair.",
            "security": [{"bearer": []}],
            "responses": {
                "200": {
                    "description": "Fluxo `event: stock` com o novo saldo de cada produto",
                    "content": {"text/event-stream": {"schema": {"type": "string"}}},
                },
                "401": {"description": "Token ausente, inválido ou expirado"},
            },
        }
    }
}


def internal(view):
    view = permission_classes([InternalToken])(view)
    return authentication_classes([])(view)


@extend_schema(
    tags=INTERNAL,
    summary="Preço e estoque atuais de vários produtos",
    request=LookupSerializer,
    responses={200: ProductSnapshotSerializer(many=True), **error_responses(403, 422)},
    auth=[],
)
@api_view(["POST"])
@internal
def lookup(request):
    data = valid(LookupSerializer, request.data)
    rows = Product.objects.filter(id__in=data["ids"])
    return Response(ProductSnapshotSerializer(rows, many=True).data)


@extend_schema(
    tags=INTERNAL,
    summary="Baixar estoque de um pedido (tudo ou nada)",
    request=StockCommitSerializer,
    responses={200: StockCommitResultSerializer, **error_responses(403, 422)},
    auth=[],
)
@api_view(["POST"])
@internal
def commit(request):
    data = valid(StockCommitSerializer, request.data)
    lines = [(i["product_id"], i["quantity"]) for i in data["items"]]
    return Response(stock.commit_order(data["order_id"], lines))


@extend_schema(
    tags=INTERNAL,
    summary="Devolver ao estoque o que um pedido baixou",
    request=StockReleaseSerializer,
    responses={200: StockReleaseResultSerializer, **error_responses(403, 422)},
    auth=[],
)
@api_view(["POST"])
@internal
def release(request):
    data = valid(StockReleaseSerializer, request.data)
    return Response({"released": stock.release_order(data["order_id"])})
