"""Middlewares síncronos e assíncronos (a rota de SSE é uma view async rodando no Daphne)."""

import logging
import time
import uuid

from asgiref.sync import iscoroutinefunction
from django.conf import settings
from django.http import HttpResponse
from django.utils.decorators import sync_and_async_middleware

log = logging.getLogger("argo")


def _finish(request, response, rid: str, start: float):
    response["X-Request-ID"] = rid
    elapsed = (time.perf_counter() - start) * 1000
    log.info("%s %s %s %.1fms", request.method, request.path, response.status_code, elapsed)
    return response


@sync_and_async_middleware
def RequestContextMiddleware(get_response):
    """Propaga X-Request-ID e registra método, caminho, status e tempo de cada requisição."""

    if iscoroutinefunction(get_response):

        async def middleware(request):
            rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
            start = time.perf_counter()
            return _finish(request, await get_response(request), rid, start)

    else:

        def middleware(request):
            rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
            start = time.perf_counter()
            return _finish(request, get_response(request), rid, start)

    return middleware


def _cors(request, response):
    origin = request.headers.get("Origin")
    if origin and (origin in settings.ARGO_CORS_ORIGINS or "*" in settings.ARGO_CORS_ORIGINS):
        response["Access-Control-Allow-Origin"] = origin
        response["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-Request-ID"
        response["Vary"] = "Origin"
    return response


@sync_and_async_middleware
def CorsMiddleware(get_response):
    """CORS simples para quem consome a API fora do gateway (ARGO_CORS_ORIGINS)."""

    if iscoroutinefunction(get_response):

        async def middleware(request):
            if request.method == "OPTIONS" and request.headers.get("Origin"):
                return _cors(request, HttpResponse(status=204))
            return _cors(request, await get_response(request))

    else:

        def middleware(request):
            if request.method == "OPTIONS" and request.headers.get("Origin"):
                return _cors(request, HttpResponse(status=204))
            return _cors(request, get_response(request))

    return middleware
