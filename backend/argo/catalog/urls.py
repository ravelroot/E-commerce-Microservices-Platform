from django.urls import path

from argo.common.views import service_urls

from . import views

urlpatterns = [
    path("products", views.products),
    path("products/categories", views.categories),
    path("products/<str:product_id>", views.product_detail),
    path("products/<str:product_id>/stock", views.adjust_stock),
    path("products/<str:product_id>/movements", views.movements),
    path("stock/summary", views.summary),
    path("stock/stream", views.stock_stream),
    path("internal/products/lookup", views.lookup),
    path("internal/stock/commit", views.commit),
    path("internal/stock/release", views.release),
    *service_urls(
        "catalog",
        title="Argo · Catálogo e estoque",
        description=(
            "Produtos dos vendedores e controle de estoque em tempo real.\n\n"
            "- Toda alteração de estoque gera um movimento imutável (entrada, saída, contagem, venda ou devolução).\n"
            "- A baixa de um pedido é feita pela fila (Celery), com trava de linha e de forma idempotente.\n"
            "- `GET /stock/stream` envia o novo saldo para as telas abertas por Server-Sent Events."
        ),
        tags=[
            {"name": "Produtos", "description": "Cadastro e consulta. Escrita exige Vendedor (dono) ou Administrador."},
            {"name": "Estoque", "description": "Resumo e fluxo em tempo real"},
            {"name": "Interno", "description": "Rotas chamadas pelos outros serviços com `X-Internal-Token`"},
        ],
        extra=views.STREAM_DOC,
    ),
]
