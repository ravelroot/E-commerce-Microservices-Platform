"""Peças comuns de URL: saúde do serviço e documentação OpenAPI."""

from django.conf import settings
from django.urls import path
from drf_spectacular.utils import extend_schema, inline_serializer
from drf_spectacular.views import SpectacularJSONAPIView
from rest_framework import serializers
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

HEALTH = inline_serializer(
    "Health",
    {
        "status": serializers.CharField(help_text="ok"),
        "service": serializers.CharField(help_text="catalog"),
        "version": serializers.CharField(help_text="1.0.0"),
    },
)


def health_view(service: str):
    @extend_schema(tags=["Saúde"], summary="Situação do serviço", responses=HEALTH, auth=[])
    @api_view(["GET"])
    @authentication_classes([])
    @permission_classes([AllowAny])
    def health(request):
        return Response({"status": "ok", "service": service, "version": settings.ARGO_VERSION})

    return health


class SchemaView(SpectacularJSONAPIView):
    """Esquema OpenAPI 3 em JSON. O nome do arquivo fica em ASCII (cabeçalhos HTTP não aceitam "·")."""

    service = "argo"

    def _get_filename(self, request, version):
        return f"argo-{self.service}-openapi.json"


def service_urls(service: str, *, title: str, description: str, tags: list[dict], extra: dict | None = None) -> list:
    """Rotas de saúde e do esquema OpenAPI (lido pela página /docs do gateway)."""
    schema = SchemaView.as_view(
        service=service,
        urlconf=f"argo.{service}.urls",
        custom_settings={
            "TITLE": title,
            "DESCRIPTION": description,
            "TAGS": tags + [{"name": "Saúde", "description": "Verificação de disponibilidade"}],
            "SERVERS": [{"url": f"/api/{service}"}],
            "SCHEMA_PATH_PREFIX": "",
            "APPEND_PATHS": extra or {},
        },
    )
    return [path("health", health_view(service)), path("openapi.json", schema)]
