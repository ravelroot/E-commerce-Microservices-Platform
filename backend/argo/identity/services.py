"""Regras de conta e sessão: login com bloqueio, rotação de refresh token e detecção de reuso."""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from functools import lru_cache

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import IntegrityError, router, transaction

from argo.common.errors import ApiError, conflict, unauthorized
from argo.common.security import Principal, Role, create_access_token
from argo.common.utils import new_id, utcnow

from .models import RefreshToken, User
from .serializers import UserSerializer

INVALID_LOGIN = "E-mail ou senha incorretos."


def atomic():
    return transaction.atomic(using=router.db_for_write(User))


def hash_password(raw: str) -> str:
    return make_password(raw)


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return check_password(raw, hashed)
    except ValueError:
        return False


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return make_password("argo-dummy-password")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def principal_of(user: User) -> Principal:
    return Principal(id=user.id, role=Role(user.role), name=user.name, email=user.email)


def create_user(*, name: str, email: str, password: str, role: str) -> User:
    email = email.strip().lower()
    if User.objects.filter(email=email).exists():
        raise conflict("email_taken", "Já existe uma conta com este e-mail.")
    try:
        with atomic():
            return User.objects.create(name=name, email=email, password_hash=hash_password(password), role=role)
    except IntegrityError as exc:
        raise conflict("email_taken", "Já existe uma conta com este e-mail.") from exc


def _issue(user: User, family_id: str | None = None) -> tuple[dict, RefreshToken]:
    raw = secrets.token_urlsafe(48)
    token = RefreshToken.objects.create(
        user=user,
        family_id=family_id or new_id(),
        token_hash=_hash_token(raw),
        expires_at=utcnow() + timedelta(days=settings.ARGO_REFRESH_TOKEN_DAYS),
    )
    access, expires_in = create_access_token(principal_of(user))
    pair = {
        "access_token": access,
        "refresh_token": raw,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": UserSerializer(user).data,
    }
    return pair, token


def login(email: str, password: str) -> dict:
    now = utcnow()
    user = User.objects.filter(email=email.strip().lower()).first()
    if user is None:
        verify_password(password, _dummy_hash())
        raise unauthorized(INVALID_LOGIN)
    if user.locked_until and user.locked_until > now:
        minutes = max(1, int((user.locked_until - now).total_seconds() // 60) + 1)
        raise ApiError(423, "locked", f"Muitas tentativas. Tente de novo em {minutes} min.")
    if not verify_password(password, user.password_hash):
        user.failed_attempts += 1
        if user.failed_attempts >= settings.ARGO_LOGIN_MAX_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=settings.ARGO_LOGIN_LOCK_MINUTES)
            user.failed_attempts = 0
        user.save(update_fields=["failed_attempts", "locked_until"])
        raise unauthorized(INVALID_LOGIN)
    if not user.active:
        raise ApiError(403, "inactive", "Esta conta está desativada. Fale com um administrador.")
    with atomic():
        user.failed_attempts = 0
        user.locked_until = None
        user.last_login_at = now
        user.save(update_fields=["failed_attempts", "locked_until", "last_login_at"])
        pair, _ = _issue(user)
    return pair


def refresh(raw: str) -> dict:
    now = utcnow()
    failure: ApiError | None = None
    with atomic():
        token = RefreshToken.objects.select_for_update().select_related("user").filter(token_hash=_hash_token(raw)).first()
        if token is None:
            raise unauthorized()
        if token.revoked_at is not None:
            revoke_family(token.family_id)  # token reapresentado: encerra a família inteira
            failure = unauthorized("Sessão encerrada por segurança. Entre novamente.")
        elif token.expires_at <= now:
            raise unauthorized("Sua sessão expirou. Entre novamente.")
        elif not token.user.active:
            revoke_family(token.family_id)
            failure = unauthorized("Esta conta foi desativada.")
        else:
            pair, new = _issue(token.user, family_id=token.family_id)
            token.revoked_at = now
            token.replaced_by = new.id
            token.save(update_fields=["revoked_at", "replaced_by"])
    if failure:  # a revogação precisa ser gravada (COMMIT) antes de responder
        raise failure
    return pair


def revoke_family(family_id: str) -> None:
    RefreshToken.objects.filter(family_id=family_id, revoked_at__isnull=True).update(revoked_at=utcnow())


def logout(raw: str) -> None:
    token = RefreshToken.objects.filter(token_hash=_hash_token(raw)).first()
    if token is not None:
        revoke_family(token.family_id)


def revoke_all_for_user(user_id: str) -> None:
    RefreshToken.objects.filter(user_id=user_id, revoked_at__isnull=True).update(revoked_at=utcnow())
