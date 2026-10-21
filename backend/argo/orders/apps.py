from django.apps import AppConfig


class OrdersConfig(AppConfig):
    name = "argo.orders"
    label = "orders"
    verbose_name = "Pedidos"
    default_auto_field = "django.db.models.BigAutoField"
