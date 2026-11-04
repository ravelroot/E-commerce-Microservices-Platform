import logging
import re
import time

from asgiref.sync import iscoroutinefunction
from django.conf import settings
from django.http import HttpResponse
from django.utils.decorators import sync_and_async_middleware

from .context import new_request_id, request_id

log = logging.getLogger("argo.http")

VALID_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
QUIET_PATHS = ("/health",)


def _incoming_id(request) -> str:
    received = request.headers.get("X-Request-ID", "")
    return received if VALID_ID.match(received) else new_request_id()


def _finish(request, response, rid: str, start: float):
    response["X-Request-ID"] = rid
    elapsed = round((time.perf_counter() - start) * 1000, 1)
    level = logging.DEBUG if request.path.endswith(QUIET_PATHS) and response.status_code < 400 else logging.INFO
    log.log(
        level,
        "%s %s %s %.1fms",
        request.method,
        request.path,
        response.status_code,
        elapsed,
        extra={"method": request.method, "path": request.path, "status": response.status_code, "duration_ms": elapsed},
    )
    return response


@sync_and_async_middleware
def RequestContextMiddleware(get_response):
    if iscoroutinefunction(get_response):

        async def middleware(request):
            rid = _incoming_id(request)
            token = request_id.set(rid)
            start = time.perf_counter()
            try:
                return _finish(request, await get_response(request), rid, start)
            finally:
                request_id.reset(token)

    else:

        def middleware(request):
            rid = _incoming_id(request)
            token = request_id.set(rid)
            start = time.perf_counter()
            try:
                return _finish(request, get_response(request), rid, start)
            finally:
                request_id.reset(token)

    return middleware


def _cors(request, response):
    origin = request.headers.get("Origin")
    if origin and (origin in settings.ARGO_CORS_ORIGINS or "*" in settings.ARGO_CORS_ORIGINS):
        response["Access-Control-Allow-Origin"] = origin
        response["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-Request-ID, Idempotency-Key"
        response["Access-Control-Expose-Headers"] = "X-Request-ID, Content-Disposition, Idempotent-Replayed"
        response["Vary"] = "Origin"
    return response


@sync_and_async_middleware
def CorsMiddleware(get_response):
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
