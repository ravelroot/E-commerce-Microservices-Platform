from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import IntegrityError, router, transaction
from django.db.models import Q

from argo.common.errors import ApiError, conflict, not_found, unauthorized
from argo.common.security import Principal, Role, create_access_token
from argo.common.utils import new_id, utcnow

from .models import RefreshToken, User
from .serializers import UserSerializer

INVALID_LOGIN = "E-mail ou senha incorretos."


@dataclass(frozen=True)
class ClientInfo:
    ip_address: str | None = None
    user_agent: str = ""


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


def principal_of(user: User, session_id: str | None = None) -> Principal:
    return Principal(id=user.id, role=Role(user.role), name=user.name, email=user.email, session_id=session_id)


def create_user(*, name: str, email: str, password: str, role: str) -> User:
    email = email.strip().lower()
    if User.objects.filter(email=email).exists():
        raise conflict("email_taken", "Já existe uma conta com este e-mail.")
    try:
        with atomic():
            return User.objects.create(name=name, email=email, password_hash=hash_password(password), role=role)
    except IntegrityError as exc:
        raise conflict("email_taken", "Já existe uma conta com este e-mail.") from exc


def _issue(user: User, client: ClientInfo, family_id: str | None = None, started_at=None) -> tuple[dict, RefreshToken]:
    raw = secrets.token_urlsafe(48)
    now = utcnow()
    family = family_id or new_id()
    token = RefreshToken.objects.create(
        user=user,
        family_id=family,
        token_hash=_hash_token(raw),
        expires_at=now + timedelta(days=settings.ARGO_REFRESH_TOKEN_DAYS),
        user_agent=client.user_agent,
        ip_address=client.ip_address,
        session_started_at=started_at or now,
    )
    access, expires_in = create_access_token(principal_of(user, family))
    pair = {
        "access_token": access,
        "refresh_token": raw,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": UserSerializer(user).data,
    }
    return pair, token


def login(email: str, password: str, client: ClientInfo | None = None) -> dict:
    client = client or ClientInfo()
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
        pair, _ = _issue(user, client)
    return pair


def refresh(raw: str, client: ClientInfo | None = None) -> dict:
    client = client or ClientInfo()
    now = utcnow()
    failure: ApiError | None = None
    with atomic():
        token = RefreshToken.objects.select_for_update().select_related("user").filter(token_hash=_hash_token(raw)).first()
        if token is None:
            raise unauthorized()
        if token.revoked_at is not None:
            revoke_family(token.family_id)
            failure = unauthorized("Sessão encerrada por segurança. Entre novamente.")
        elif token.expires_at <= now:
            raise unauthorized("Sua sessão expirou. Entre novamente.")
        elif not token.user.active:
            revoke_family(token.family_id)
            failure = unauthorized("Esta conta foi desativada.")
        else:
            info = ClientInfo(
                ip_address=client.ip_address or token.ip_address,
                user_agent=client.user_agent or token.user_agent,
            )
            started = token.session_started_at or token.created_at
            pair, new = _issue(token.user, info, family_id=token.family_id, started_at=started)
            token.revoked_at = now
            token.replaced_by = new.id
            token.save(update_fields=["revoked_at", "replaced_by"])
    if failure:
        raise failure
    return pair


def revoke_family(family_id: str) -> int:
    return RefreshToken.objects.filter(family_id=family_id, revoked_at__isnull=True).update(revoked_at=utcnow())


def logout(raw: str) -> None:
    token = RefreshToken.objects.filter(token_hash=_hash_token(raw)).first()
    if token is not None:
        revoke_family(token.family_id)


def revoke_all_for_user(user_id: str, *, keep_family: str | None = None) -> int:
    qs = RefreshToken.objects.filter(user_id=user_id, revoked_at__isnull=True)
    if keep_family:
        qs = qs.exclude(family_id=keep_family)
    return qs.update(revoked_at=utcnow())


def active_sessions(user_id: str, current_family: str | None) -> list[dict]:
    now = utcnow()
    rows = RefreshToken.objects.filter(user_id=user_id, revoked_at__isnull=True, expires_at__gt=now).order_by("-created_at")
    sessions = []
    for t in rows:
        sessions.append(
            {
                "id": t.family_id,
                "user_agent": t.user_agent,
                "ip_address": t.ip_address,
                "started_at": t.session_started_at or t.created_at,
                "last_used_at": t.created_at,
                "expires_at": t.expires_at,
                "current": t.family_id == current_family,
            }
        )
    return sessions


def revoke_session(user_id: str, family_id: str) -> None:
    exists = RefreshToken.objects.filter(user_id=user_id, family_id=family_id).exists()
    if not exists:
        raise not_found("Sessão")
    revoke_family(family_id)


def set_password(user: User, raw: str, *, keep_family: str | None = None) -> None:
    with atomic():
        user.password_hash = hash_password(raw)
        user.failed_attempts = 0
        user.locked_until = None
        user.save(update_fields=["password_hash", "failed_attempts", "locked_until"])
        revoke_all_for_user(user.id, keep_family=keep_family)


def unlock(user: User) -> None:
    user.failed_attempts = 0
    user.locked_until = None
    user.save(update_fields=["failed_attempts", "locked_until"])


def cleanup_tokens(retention_days: int | None = None) -> int:
    days = settings.ARGO_TOKEN_RETENTION_DAYS if retention_days is None else retention_days
    limit = utcnow() - timedelta(days=days)
    stale = RefreshToken.objects.filter(Q(expires_at__lt=limit) | Q(revoked_at__lt=limit))
    deleted, _ = stale.delete()
    return deleted


def ensure_admin(*, email: str, password: str | None, name: str, reset_password: bool = False) -> tuple[User, bool]:
    email = email.strip().lower()
    user = User.objects.filter(email=email).first()
    if user is None:
        if not password:
            raise ApiError(422, "validation_error", "Informe a senha do administrador.", {"password": "Obrigatória."})
        return create_user(name=name, email=email, password=password, role=Role.ADMIN.value), True
    with atomic():
        user.role = Role.ADMIN.value
        user.active = True
        user.save(update_fields=["role", "active"])
    if reset_password and password:
        set_password(user, password)
    return user, False
