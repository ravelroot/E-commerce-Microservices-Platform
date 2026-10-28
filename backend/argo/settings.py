"""Configurações do Django para os três microserviços Python do Argo.

O mesmo código vira um serviço diferente conforme ARGO_SERVICE:

- identity, catalog ou orders: um app Django, um banco (ARGO_DATABASE_URL) e as rotas em /api/<serviço>/
- worker: o worker Celery, sem banco (fala com os serviços por HTTP)
- all: os três apps no mesmo processo, cada um no seu banco (desenvolvimento e testes)
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlparse

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name: str, default: str = "") -> str:
    value = os.environ.get(f"ARGO_{name}")
    return default if value is None or value.strip() == "" else value.strip()


def env_bool(name: str, default: bool) -> bool:
    return env(name, "true" if default else "false").lower() in {"1", "true", "yes", "sim", "on"}


def env_int(name: str, default: int) -> int:
    return int(env(name, str(default)))


def database(url: str) -> dict:
    """Aceita mysql://usuario:senha@servidor:3306/banco e sqlite:///caminho."""
    if url.startswith("sqlite"):
        path = url.split(":///", 1)[1] if ":///" in url else ":memory:"
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": path or ":memory:"}
    u = urlparse(url)
    if u.scheme not in {"mysql", "mysql+mysqldb"}:
        raise ImproperlyConfigured(f"Banco não suportado em {u.scheme}://. Use mysql:// ou sqlite:///.")
    return {
        "ENGINE": "django.db.backends.mysql",
        "NAME": unquote(u.path.lstrip("/")),
        "USER": unquote(u.username or ""),
        "PASSWORD": unquote(u.password or ""),
        "HOST": u.hostname or "localhost",
        "PORT": str(u.port or 3306),
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {"charset": "utf8mb4", **dict(parse_qsl(u.query))},  # ex.: ?ssl_mode=REQUIRED
        "TEST": {"CHARSET": "utf8mb4", "COLLATION": "utf8mb4_0900_ai_ci"},
    }


# ------------------------------------------------------------------ serviço
SERVICE_APPS = {"identity": "argo.identity", "catalog": "argo.catalog", "orders": "argo.orders"}
ARGO_SERVICE = env("SERVICE", "all")
if ARGO_SERVICE == "all":
    ARGO_SERVICES = list(SERVICE_APPS)
elif ARGO_SERVICE in SERVICE_APPS:
    ARGO_SERVICES = [ARGO_SERVICE]
else:
    ARGO_SERVICES = []  # worker
ARGO_ENVIRONMENT = env("ENVIRONMENT", "development")
ARGO_VERSION = "1.1.0"

SECRET_KEY = env("JWT_SECRET", "troque-este-segredo-por-um-valor-longo-e-aleatorio")
DEBUG = ARGO_ENVIRONMENT == "development" and env_bool("DEBUG", False)
ALLOWED_HOSTS = [h.strip() for h in env("ALLOWED_HOSTS", "*").split(",") if h.strip()]

INSTALLED_APPS = [
    "rest_framework",
    "drf_spectacular",
    "argo.common",
    *[SERVICE_APPS[s] for s in ARGO_SERVICES],
]

MIDDLEWARE = [
    "argo.common.middleware.RequestContextMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
if env("CORS_ORIGINS"):
    MIDDLEWARE.insert(1, "argo.common.middleware.CorsMiddleware")
ARGO_CORS_ORIGINS = [o.strip() for o in env("CORS_ORIGINS").split(",") if o.strip()]

ROOT_URLCONF = "argo.urls"
WSGI_APPLICATION = "argo.wsgi.application"
ASGI_APPLICATION = "argo.asgi.application"
APPEND_SLASH = False
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
# API sem cookies (JWT no cabeçalho), então não há CSRF; HTTPS e HSTS ficam no proxy na frente do gateway.
SILENCED_SYSTEM_CHECKS = ["security.W003", "security.W004", "security.W008"]

TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "APP_DIRS": True}]

# ------------------------------------------------------------------ bancos
# Cada serviço tem o próprio banco e nunca lê o banco de outro.
if ARGO_SERVICE == "all":
    DATABASES = {
        "default": database(env("DATABASE_URL", f"sqlite:///{BASE_DIR / 'argo_identity.sqlite3'}")),
        "catalog": database(env("CATALOG_DATABASE_URL", f"sqlite:///{BASE_DIR / 'argo_catalog.sqlite3'}")),
        "orders": database(env("ORDERS_DATABASE_URL", f"sqlite:///{BASE_DIR / 'argo_orders.sqlite3'}")),
    }
elif ARGO_SERVICES:
    DATABASES = {"default": database(env("DATABASE_URL", f"sqlite:///{BASE_DIR / f'argo_{ARGO_SERVICE}.sqlite3'}"))}
else:
    DATABASES = {}
DATABASE_ROUTERS = ["argo.common.routers.ServiceRouter"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Senhas com o hasher bcrypt do Django (custo 12).
PASSWORD_HASHERS = ["django.contrib.auth.hashers.BCryptSHA256PasswordHasher"]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ------------------------------------------------------------------ segurança da API
ARGO_JWT_SECRET = SECRET_KEY
ARGO_JWT_ISSUER = env("JWT_ISSUER", "argo-identity")
ARGO_ACCESS_TOKEN_MINUTES = env_int("ACCESS_TOKEN_MINUTES", 15)
ARGO_REFRESH_TOKEN_DAYS = env_int("REFRESH_TOKEN_DAYS", 7)
ARGO_LOGIN_MAX_ATTEMPTS = env_int("LOGIN_MAX_ATTEMPTS", 5)
ARGO_LOGIN_LOCK_MINUTES = env_int("LOGIN_LOCK_MINUTES", 5)
ARGO_INTERNAL_TOKEN = env("INTERNAL_TOKEN", "troque-este-token-interno")
ARGO_SEED = env_bool("SEED", True)

# ------------------------------------------------------------------ outros serviços
ARGO_REDIS_URL = env("REDIS_URL", "redis://localhost:6379/0")
ARGO_CATALOG_URL = env("CATALOG_URL", "http://localhost:8000/api/catalog")
ARGO_ORDERS_URL = env("ORDERS_URL", "http://localhost:8000/api/orders")
ARGO_BILLING_URL = env("BILLING_URL", "http://localhost:8080/api/billing")
ARGO_PUBLIC_URL = env("PUBLIC_URL", "http://localhost:8080")

# ------------------------------------------------------------------ e-mail (django.core.mail, MAILERS do Django 6.1)
MAILERS = {
    "default": (
        {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}
        if ARGO_ENVIRONMENT == "test"
        else {
            "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "OPTIONS": {
                "host": env("SMTP_HOST", "localhost"),
                "port": env_int("SMTP_PORT", 1025),
                "username": env("SMTP_USER"),
                "password": env("SMTP_PASSWORD"),
                "use_tls": env_bool("SMTP_TLS", False),
                "timeout": 10,
            },
        }
    )
}
DEFAULT_FROM_EMAIL = env("MAIL_FROM", "Argo <nao-responda@argo.dev>")

# ------------------------------------------------------------------ Celery (integrado ao Django)
CELERY_BROKER_URL = ARGO_REDIS_URL
CELERY_RESULT_BACKEND = ARGO_REDIS_URL
CELERY_TASK_DEFAULT_QUEUE = "orders"
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_RESULT_EXPIRES = 3600
CELERY_TIMEZONE = "America/Sao_Paulo"
CELERY_ENABLE_UTC = True
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_EAGER", False)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# ------------------------------------------------------------------ Django REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["argo.common.security.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["argo.common.security.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "EXCEPTION_HANDLER": "argo.common.errors.exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "UNAUTHENTICATED_USER": None,
    "UNAUTHENTICATED_TOKEN": None,
}
SPECTACULAR_SETTINGS = {
    "VERSION": ARGO_VERSION,
    "OAS_VERSION": "3.1.0",
    "SORT_OPERATIONS": False,
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
    "SERVE_AUTHENTICATION": [],
    "COMPONENT_SPLIT_REQUEST": True,
    "LICENSE": {"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
    "ENUM_NAME_OVERRIDES": {
        "RoleEnum": ["ADMIN", "SELLER", "CUSTOMER"],
        "OrderStatusEnum": ["PENDING", "CONFIRMED", "REJECTED", "SHIPPED", "DELIVERED", "CANCELED"],
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"argo": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "argo"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO").upper()},
    "loggers": {"django.request": {"level": "ERROR"}, "daphne": {"level": "WARNING"}},
}
