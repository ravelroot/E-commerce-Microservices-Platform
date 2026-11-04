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
    path("auth/sessions", views.sessions),
    path("auth/sessions/revoke-others", views.revoke_other_sessions),
    path("auth/sessions/<str:session_id>", views.session_detail),
    path("users", views.users),
    path("users/<str:user_id>", views.update_user),
    path("users/<str:user_id>/password", views.reset_password),
    path("users/<str:user_id>/unlock", views.unlock_user),
    path("internal/tokens/cleanup", views.cleanup_tokens),
    *service_urls(
        "identity",
        title="Argo · Identidade",
        description=(
            "Cadastro, login e sessões da plataforma Argo.\n\n"
            "**Fluxo:** `POST /auth/login` devolve `access_token` (JWT de 15 min) e `refresh_token` "
            "(uso único, 7 dias). Envie o access token como `Authorization: Bearer <token>` para todos os serviços. "
            "Quando ele expirar, troque o refresh token em `POST /auth/refresh`.\n\n"
            "**Sessões:** cada login abre uma sessão que pode ser listada e encerrada em `/auth/sessions`.\n\n"
            "**Papéis:** `ADMIN`, `SELLER` (Vendedor) e `CUSTOMER` (Cliente)."
        ),
        tags=[
            {"name": "Autenticação", "description": "Login, cadastro, refresh token e logout"},
            {"name": "Minha conta", "description": "Perfil, senha e sessões abertas da conta logada"},
            {"name": "Usuários", "description": "Gestão de contas (somente Administrador)"},
            {"name": "Interno", "description": "Rotas chamadas pelo agendador com `X-Internal-Token`"},
        ],
    ),
]
