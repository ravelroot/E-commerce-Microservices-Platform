from django.apps import AppConfig


class CatalogConfig(AppConfig):
    name = "argo.catalog"
    label = "catalog"
    verbose_name = "Catálogo e estoque"
    default_auto_field = "django.db.models.BigAutoField"
