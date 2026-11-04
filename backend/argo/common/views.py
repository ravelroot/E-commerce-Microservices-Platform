import time

from django.conf import settings
from django.db import connections
from django.urls import path
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
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
        "version": serializers.CharField(help_text="1.2.0"),
        "environment": serializers.CharField(help_text="production"),
        "checks": serializers.DictField(child=serializers.CharField(), help_text='{"database": "ok"}'),
        "duration_ms": serializers.FloatField(help_text="3.1"),
    },
)


def database_checks(aliases) -> dict[str, str]:
    results = {}
    for alias in aliases:
        name = "database" if alias == "default" else f"database:{alias}"
        try:
            with connections[alias].cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            results[name] = "ok"
        except Exception as exc:
            results[name] = f"erro: {exc.__class__.__name__}"
    return results


def health_payload(service: str) -> tuple[dict, int]:
    start = time.perf_counter()
    checks = database_checks(settings.DATABASES)
    healthy = all(v == "ok" for v in checks.values())
    payload = {
        "status": "ok" if healthy else "degraded",
        "service": service,
        "version": settings.ARGO_VERSION,
        "environment": settings.ARGO_ENVIRONMENT,
        "checks": checks,
        "duration_ms": round((time.perf_counter() - start) * 1000, 1),
    }
    return payload, 200 if healthy else 503


def health_view(service: str):
    @extend_schema(
        tags=["Saúde"],
        summary="Situação do serviço",
        description="Confere a conexão com o banco do serviço. Responde 503 quando alguma verificação falha.",
        responses={200: HEALTH, 503: OpenApiResponse(HEALTH, description="Alguma dependência fora do ar")},
        auth=[],
    )
    @api_view(["GET"])
    @authentication_classes([])
    @permission_classes([AllowAny])
    def health(request):
        payload, status = health_payload(service)
        response = Response(payload, status=status)
        response["Cache-Control"] = "no-store"
        return response

    return health


class SchemaView(SpectacularJSONAPIView):
    service = "argo"

    def _get_filename(self, request, version):
        return f"argo-{self.service}-openapi.json"


def service_urls(service: str, *, title: str, description: str, tags: list[dict], extra: dict | None = None) -> list:
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
