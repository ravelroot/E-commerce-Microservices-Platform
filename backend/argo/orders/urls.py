from django.urls import path

from argo.common.views import service_urls

from . import views

urlpatterns = [
    path("orders", views.orders),
    path("orders/stats", views.stats),
    path("orders/export", views.export_orders),
    path("orders/<int:order_id>", views.order_detail),
    path("orders/<int:order_id>/cancel", views.cancel),
    path("orders/<int:order_id>/status", views.change_status),
    path("internal/orders/<int:order_id>", views.internal_detail),
    path("internal/orders/<int:order_id>/events", views.internal_event),
    path("internal/orders/recover", views.internal_recover),
    *service_urls(
        "orders",
        title="Argo · Pedidos",
        description=(
            "Checkout, acompanhamento e indicadores de vendas.\n\n"
            "O checkout responde `202 Accepted` em milissegundos. O pedido segue para a fila "
            "(Celery + Redis), onde o worker baixa o estoque com trava de linha, envia o e-mail "
            "de confirmação e pede a nota fiscal ao serviço de faturamento (Java)."
        ),
        tags=[
            {"name": "Pedidos", "description": "Checkout, consulta, cancelamento e situação"},
            {"name": "Interno", "description": "Rotas usadas pelo worker e pelo agendador com `X-Internal-Token`"},
        ],
    ),
]
