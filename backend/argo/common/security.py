"""JWT de acesso, papéis e as classes de autenticação e permissão do Django REST Framework.

O token é emitido pela identidade e validado por todos os serviços, inclusive
o de faturamento em Java, com o mesmo segredo (ARGO_JWT_SECRET).
"""

from __future__ import annotations

import hmac
import uuid
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

import jwt
from django.conf import settings
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.permissions import BasePermission

from .errors import ApiError, forbidden, unauthorized
from .utils import utcnow


class Role(StrEnum):
    ADMIN = "ADMIN"
    SELLER = "SELLER"
    CUSTOMER = "CUSTOMER"


ROLE_LABEL = {Role.ADMIN: "Administrador", Role.SELLER: "Vendedor", Role.CUSTOMER: "Cliente"}


@dataclass(frozen=True)
class Principal:
    """Quem fez a requisição (``request.user`` nas views)."""

    id: str
    role: Role
    name: str
    email: str

    is_authenticated = True

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN


def create_access_token(principal: Principal, *, minutes: int | None = None, secret: str | None = None) -> tuple[str, int]:
    now = utcnow()
    ttl = timedelta(minutes=settings.ARGO_ACCESS_TOKEN_MINUTES if minutes is None else minutes)
    claims = {
        "iss": settings.ARGO_JWT_ISSUER,
        "sub": principal.id,
        "role": principal.role.value,
        "name": principal.name,
        "email": principal.email,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(claims, secret or settings.ARGO_JWT_SECRET, algorithm="HS256")
    return token, int(ttl.total_seconds())


def decode_access_token(token: str, *, secret: str | None = None) -> Principal:
    try:
        claims = jwt.decode(
            token,
            secret or settings.ARGO_JWT_SECRET,
            algorithms=["HS256"],
            issuer=settings.ARGO_JWT_ISSUER,
            options={"require": ["exp", "iat", "sub", "iss"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise unauthorized("Sua sessão expirou. Entre novamente.") from exc
    except jwt.PyJWTError as exc:
        raise unauthorized() from exc
    if claims.get("type") != "access":
        raise unauthorized()
    try:
        role = Role(claims.get("role"))
    except ValueError as exc:
        raise unauthorized() from exc
    return Principal(id=claims["sub"], role=role, name=claims.get("name", ""), email=claims.get("email", ""))


def bearer_token(request) -> str | None:
    header = get_authorization_header(request).decode("latin-1").strip()
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


class JWTAuthentication(BaseAuthentication):
    """``Authorization: Bearer <JWT>``. Não consulta banco: os dados do usuário vêm no token."""

    def authenticate(self, request):
        token = bearer_token(request)
        if token is None:
            return None
        try:
            return decode_access_token(token), token
        except ApiError as exc:
            raise exceptions.AuthenticationFailed(exc.message) from None

    def authenticate_header(self, request) -> str:
        return "Bearer"


class IsAuthenticated(BasePermission):
    def has_permission(self, request, view) -> bool:
        if not isinstance(request.user, Principal):
            raise exceptions.NotAuthenticated("Envie o cabeçalho Authorization: Bearer <token>.")
        return True


def roles(*allowed: Role) -> type[BasePermission]:
    """Permissão do DRF que só deixa passar os papéis informados."""

    class HasRole(IsAuthenticated):
        def has_permission(self, request, view) -> bool:
            super().has_permission(request, view)
            if request.user.role not in allowed:
                raise forbidden()
            return True

    HasRole.__name__ = "Has" + "Or".join(r.value.title() for r in allowed)
    return HasRole


class InternalToken(BasePermission):
    """Rotas /internal/*: só outros serviços da plataforma, com o segredo compartilhado."""

    def has_permission(self, request, view) -> bool:
        received = request.headers.get("X-Internal-Token") or ""
        if not received or not hmac.compare_digest(received, settings.ARGO_INTERNAL_TOKEN):
            raise forbidden("Rota interna: apenas outros serviços da plataforma podem chamar.")
        return True


class JWTScheme(OpenApiAuthenticationExtension):
    target_class = "argo.common.security.JWTAuthentication"
    name = "bearer"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Token de acesso emitido por POST /api/identity/auth/login",
        }
