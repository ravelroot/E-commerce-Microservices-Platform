from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from argo.common.errors import ApiError, error_responses, not_found
from argo.common.pagination import paginate
from argo.common.security import InternalToken, IsAuthenticated, Role, roles
from argo.common.utils import client_ip, user_agent, utcnow
from argo.common.validation import valid

from . import services
from .models import User
from .serializers import (
    AdminPasswordSerializer,
    CleanupSerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    ProfileUpdateSerializer,
    RefreshSerializer,
    RegisterSerializer,
    RevokedSerializer,
    SessionSerializer,
    TokenPairSerializer,
    UserCreateSerializer,
    UserPageSerializer,
    UserQuerySerializer,
    UserSerializer,
    UserUpdateSerializer,
)

AUTH = ["Autenticação"]
ACCOUNT = ["Minha conta"]
USERS = ["Usuários"]
INTERNAL = ["Interno"]
admin_only = roles(Role.ADMIN)


def _client(request) -> services.ClientInfo:
    return services.ClientInfo(ip_address=client_ip(request), user_agent=user_agent(request))


def _me(request) -> User:
    user = User.objects.filter(pk=request.user.id).first()
    if user is None:
        raise not_found("Usuário")
    return user


def _user(user_id: str) -> User:
    user = User.objects.filter(pk=user_id).first()
    if user is None:
        raise not_found("Usuário")
    return user


@extend_schema(
    tags=AUTH,
    summary="Criar conta de Cliente ou Vendedor",
    request=RegisterSerializer,
    responses={201: TokenPairSerializer, **error_responses(409, 422)},
    auth=[],
)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def register(request):
    body = valid(RegisterSerializer, request.data)
    user = services.create_user(name=body["name"], email=body["email"], password=body["password"], role=body["role"])
    return Response(services.login(user.email, body["password"], _client(request)), status=201)


@extend_schema(
    tags=AUTH,
    summary="Entrar com e-mail e senha",
    description="Devolve um access token (JWT, 15 min) e um refresh token (7 dias, uso único).\n\n"
    "Cinco senhas erradas seguidas bloqueiam a conta por 5 minutos (código 423).",
    request=LoginSerializer,
    responses={200: TokenPairSerializer, **error_responses(401, 403, 422, 423)},
    auth=[],
)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def login(request):
    body = valid(LoginSerializer, request.data)
    return Response(services.login(body["email"], body["password"], _client(request)))


@extend_schema(
    tags=AUTH,
    summary="Trocar o refresh token por um novo par",
    description="Rotação: o refresh token enviado deixa de valer. Reapresentar um token já trocado\n"
    "encerra todas as sessões daquela família (detecção de roubo).",
    request=RefreshSerializer,
    responses={200: TokenPairSerializer, **error_responses(401)},
    auth=[],
)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def refresh(request):
    body = valid(RefreshSerializer, request.data)
    return Response(services.refresh(body["refresh_token"], _client(request)))


@extend_schema(tags=AUTH, summary="Encerrar a sessão", request=RefreshSerializer, responses={204: None}, auth=[])
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def logout(request):
    body = valid(RefreshSerializer, request.data)
    services.logout(body["refresh_token"])
    return Response(status=204)


@extend_schema(
    tags=ACCOUNT,
    methods=["GET"],
    summary="Dados da conta logada",
    responses={200: UserSerializer, **error_responses(401, 404)},
)
@extend_schema(
    tags=ACCOUNT,
    methods=["PATCH"],
    summary="Alterar o próprio nome",
    description="O novo nome aparece nos próximos tokens e nos pedidos feitos a partir de agora.",
    request=ProfileUpdateSerializer,
    responses={200: UserSerializer, **error_responses(401, 404, 422)},
)
@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def me(request):
    user = _me(request)
    if request.method == "PATCH":
        body = valid(ProfileUpdateSerializer, request.data)
        user.name = body["name"]
        user.save(update_fields=["name"])
    return Response(UserSerializer(user).data)


@extend_schema(
    tags=ACCOUNT,
    summary="Trocar a senha",
    description="Encerra todas as outras sessões abertas. A sessão atual continua valendo.",
    request=PasswordChangeSerializer,
    responses={204: None, **error_responses(400, 401, 422)},
)
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def change_password(request):
    body = valid(PasswordChangeSerializer, request.data)
    user = User.objects.filter(pk=request.user.id).first()
    if user is None or not services.verify_password(body["current_password"], user.password_hash):
        raise ApiError(400, "wrong_password", "A senha atual não confere.", {"current_password": "Senha incorreta."})
    if body["current_password"] == body["new_password"]:
        fields = {"new_password": "Use uma senha diferente da atual."}
        raise ApiError(422, "validation_error", "Confira os campos destacados.", fields)
    services.set_password(user, body["new_password"], keep_family=request.user.session_id)
    return Response(status=204)


@extend_schema(
    tags=ACCOUNT,
    summary="Sessões abertas",
    description="Cada login abre uma sessão; a troca do refresh token mantém a mesma sessão.\n"
    "`current` marca a sessão desta requisição.",
    responses={200: SessionSerializer(many=True), **error_responses(401)},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def sessions(request):
    rows = services.active_sessions(request.user.id, request.user.session_id)
    return Response(SessionSerializer(rows, many=True).data)


@extend_schema(
    tags=ACCOUNT,
    summary="Encerrar uma sessão",
    description="O refresh token daquela sessão deixa de valer. O access token já emitido expira sozinho em até 15 minutos.",
    responses={204: None, **error_responses(401, 404)},
)
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def session_detail(request, session_id: str):
    services.revoke_session(request.user.id, session_id)
    return Response(status=204)


@extend_schema(
    tags=ACCOUNT,
    summary="Encerrar todas as outras sessões",
    request=None,
    responses={200: RevokedSerializer, **error_responses(401)},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def revoke_other_sessions(request):
    count = services.revoke_all_for_user(request.user.id, keep_family=request.user.session_id)
    return Response({"revoked": count})


@extend_schema(
    tags=USERS,
    methods=["GET"],
    operation_id="users_list",
    summary="Listar usuários",
    parameters=[UserQuerySerializer],
    responses={200: UserPageSerializer, **error_responses(401, 403, 422)},
)
@extend_schema(
    tags=USERS,
    methods=["POST"],
    summary="Criar usuário com qualquer papel",
    request=UserCreateSerializer,
    responses={201: UserSerializer, **error_responses(401, 403, 409, 422)},
)
@api_view(["GET", "POST"])
@permission_classes([admin_only])
def users(request):
    if request.method == "POST":
        body = valid(UserCreateSerializer, request.data)
        user = services.create_user(name=body["name"], email=body["email"], password=body["password"], role=body["role"])
        return Response(UserSerializer(user).data, status=201)
    f = valid(UserQuerySerializer, request.query_params)
    qs = User.objects.all()
    if f.get("q"):
        q = f["q"]
        qs = qs.filter(Q(name__icontains=q) | Q(email__icontains=q.lower()))
    if f.get("role"):
        qs = qs.filter(role=f["role"])
    if f.get("active"):
        qs = qs.filter(active=f["active"] == "true")
    if f["locked"]:
        qs = qs.filter(locked_until__gt=utcnow())
    qs = qs.order_by("-created_at", "name")
    return Response(paginate(qs, f["page"], f["size"], lambda u: UserSerializer(u).data))


@extend_schema(
    tags=USERS,
    summary="Alterar papel, nome ou situação",
    request=UserUpdateSerializer,
    responses={200: UserSerializer, **error_responses(400, 401, 403, 404)},
)
@api_view(["PATCH"])
@permission_classes([admin_only])
def update_user(request, user_id: str):
    body = valid(UserUpdateSerializer, request.data)
    user = _user(user_id)
    if user.id == request.user.id and (body.get("active") is False or (body.get("role") and body["role"] != Role.ADMIN)):
        raise ApiError(400, "self_lockout", "Você não pode remover o próprio acesso de administrador.")
    with services.atomic():
        if body.get("name") is not None:
            user.name = " ".join(body["name"].split())
        if body.get("role") is not None:
            user.role = body["role"]
        if body.get("active") is not None:
            user.active = body["active"]
            if not body["active"]:
                services.revoke_all_for_user(user.id)
        user.save()
    return Response(UserSerializer(user).data)


@extend_schema(
    tags=USERS,
    summary="Definir uma nova senha para o usuário",
    description="Também desbloqueia a conta e encerra todas as sessões dela.",
    request=AdminPasswordSerializer,
    responses={200: UserSerializer, **error_responses(401, 403, 404, 422)},
)
@api_view(["POST"])
@permission_classes([admin_only])
def reset_password(request, user_id: str):
    body = valid(AdminPasswordSerializer, request.data)
    user = _user(user_id)
    services.set_password(user, body["password"], keep_family=request.user.session_id if user.id == request.user.id else None)
    return Response(UserSerializer(user).data)


@extend_schema(
    tags=USERS,
    summary="Desbloquear a conta",
    description="Zera as tentativas erradas de login e libera a conta antes dos 5 minutos.",
    request=None,
    responses={200: UserSerializer, **error_responses(401, 403, 404)},
)
@api_view(["POST"])
@permission_classes([admin_only])
def unlock_user(request, user_id: str):
    user = _user(user_id)
    services.unlock(user)
    return Response(UserSerializer(user).data)


@extend_schema(
    tags=INTERNAL,
    summary="Remover refresh tokens antigos",
    description="Apaga tokens expirados ou revogados há mais de `ARGO_TOKEN_RETENTION_DAYS` dias. Chamado pelo agendador.",
    request=None,
    responses={200: CleanupSerializer, **error_responses(403)},
    auth=[],
)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([InternalToken])
def cleanup_tokens(request):
    return Response({"deleted": services.cleanup_tokens()})
