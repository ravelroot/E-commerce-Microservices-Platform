from importlib import import_module

from django.apps import AppConfig


class CommonConfig(AppConfig):
    name = "argo.common"
    label = "common"
    verbose_name = "Argo · comum"

    def ready(self):
        import_module("argo.common.checks")
