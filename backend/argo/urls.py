"""Cada serviço responde em /api/<serviço>/, o mesmo caminho que o gateway Nginx publica."""

from django.conf import settings
from django.urls import include, path, re_path

from argo.common.errors import not_found_view

urlpatterns = [path(f"api/{service}/", include(f"argo.{service}.urls")) for service in settings.ARGO_SERVICES]
urlpatterns.append(re_path(r"^", not_found_view))
