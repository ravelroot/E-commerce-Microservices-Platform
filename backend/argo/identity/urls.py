from django.urls import path

from argo.common.views import service_urls

from . import views

urlpatterns = [
    path("auth/register", views.register),
    path("auth/login", views.login),
    path("auth/refresh", views.refresh),
    path("auth/logout", views.logout),
    path("auth/me", views.me),
    path("auth/me/password", views.change_password),
    path("users", views.users),
    path("users/<str:user_id>", views.update_user),
    *service_urls(
        "identity",
        title="Argo · Identidade",
        description=(
            "Cadastro, login e sessões da plataforma Argo.\n\n"
            "**Fluxo:** `POST /auth/login` devolve `access_token` (JWT de 15 min) e `refresh_token` "
            "(uso único, 7 dias). Envie o access token como `Authorization: Bearer <token>` para todos os serviços. "
            "Quando ele expirar, troque o refresh token em `POST /auth/refresh`.\n\n"
            "**Papéis:** `ADMIN`, `SELLER` (Vendedor) e `CUSTOMER` (Cliente)."
        ),
        tags=[
            {"name": "Autenticação", "description": "Login, cadastro, refresh token e logout"},
            {"name": "Usuários", "description": "Gestão de contas (somente Administrador)"},
        ],
    ),
]
