"""Formato único de erro em todos os serviços: ``{"code", "message", "fields"}``."""

from __future__ import annotations

from typing import Any

from django.http import Http404, JsonResponse
from drf_spectacular.utils import OpenApiResponse
from rest_framework import exceptions, serializers
from rest_framework.response import Response


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, fields: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.fields = fields or {}


def not_found(what: str = "Recurso") -> ApiError:
    return ApiError(404, "not_found", f"{what} não encontrado.")


def forbidden(message: str = "Você não tem permissão para esta ação.") -> ApiError:
    return ApiError(403, "forbidden", message)


def unauthorized(message: str = "Sessão inválida ou expirada. Entre novamente.") -> ApiError:
    return ApiError(401, "unauthorized", message)


def conflict(code: str, message: str) -> ApiError:
    return ApiError(409, code, message)


def body(code: str, message: str, fields: dict[str, str] | None = None) -> dict:
    return {"code": code, "message": message, "fields": fields or {}}


def flatten(detail: Any, prefix: str = "") -> dict[str, str]:
    """Erros aninhados do DRF viram ``{"items.0.quantity": "mensagem"}``."""
    if isinstance(detail, dict):
        out: dict[str, str] = {}
        for key, value in detail.items():
            name = "corpo" if key == "non_field_errors" and not prefix else (f"{prefix}.{key}" if prefix else str(key))
            out.update(flatten(value, name))
        return out
    if isinstance(detail, list):
        if detail and all(not isinstance(x, dict | list) for x in detail):
            return {prefix or "corpo": str(detail[0])}
        out = {}
        for i, value in enumerate(detail):
            if value:
                out.update(flatten(value, f"{prefix}.{i}" if prefix else str(i)))
        return out
    return {prefix or "corpo": str(detail)}


def _response(status: int, code: str, message: str, fields: dict | None = None) -> Response:
    response = Response(body(code, message, fields), status=status)
    if status == 401:
        response["WWW-Authenticate"] = "Bearer"
    return response


def exception_handler(exc: Exception, context: dict) -> Response | None:
    if isinstance(exc, ApiError):
        return _response(exc.status, exc.code, exc.message, exc.fields)
    if isinstance(exc, exceptions.ValidationError):
        return _response(422, "validation_error", "Confira os campos destacados.", flatten(exc.detail))
    if isinstance(exc, exceptions.ParseError):
        return _response(422, "validation_error", "Corpo da requisição inválido.", {"corpo": "JSON inválido."})
    if isinstance(exc, exceptions.NotAuthenticated | exceptions.AuthenticationFailed):
        return _response(401, "unauthorized", str(exc.detail))
    if isinstance(exc, exceptions.PermissionDenied):
        return _response(403, "forbidden", str(exc.detail))
    if isinstance(exc, Http404 | exceptions.NotFound):
        return _response(404, "not_found", "Recurso não encontrado.")
    if isinstance(exc, exceptions.MethodNotAllowed):
        return _response(405, "method_not_allowed", "Método não permitido nesta rota.")
    if isinstance(exc, exceptions.APIException):
        return _response(exc.status_code, "http_error", str(exc.detail))
    return None


def not_found_view(request, *args, **kwargs) -> JsonResponse:
    return JsonResponse(body("not_found", "Rota não encontrada."), status=404)


# ----------------------------------------------------------- documentação (OpenAPI)
class ErrorBodySerializer(serializers.Serializer):
    code = serializers.CharField(help_text="not_found")
    message = serializers.CharField(help_text="Recurso não encontrado.")
    fields = serializers.DictField(child=serializers.CharField(), help_text='{"email": "E-mail inválido."}')


ERROR_TEXT = {
    400: "Requisição inválida",
    401: "Token ausente, inválido ou expirado",
    403: "Papel sem permissão para a ação",
    404: "Não encontrado",
    409: "Conflito com o estado atual",
    422: "Campos inválidos",
    423: "Conta bloqueada temporariamente",
    503: "Serviço dependente indisponível",
}


def error_responses(*codes: int) -> dict:
    return {c: OpenApiResponse(ErrorBodySerializer, description=ERROR_TEXT.get(c, "Erro")) for c in codes}
