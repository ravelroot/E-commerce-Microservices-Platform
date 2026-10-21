"""API da identidade (Django REST Framework): cadastro, login, sessões e gestão de usuários."""

from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from argo.common.errors import ApiError, error_responses, not_found
from argo.common.pagination import paginate
from argo.common.security import IsAuthenticated, Role, roles
from argo.common.validation import valid

from . import services
from .models import User
from .serializers import (
    LoginSerializer,
    PasswordChangeSerializer,
    RefreshSerializer,
    RegisterSerializer,
    TokenPairSerializer,
    UserCreateSerializer,
    UserPageSerializer,
    UserSerializer,
    UserUpdateSerializer,
)

AUTH = ["Autenticação"]
USERS = ["Usuários"]
admin_only = roles(Role.ADMIN)


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
    return Response(services.login(user.email, body["password"]), status=201)


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
    return Response(services.login(body["email"], body["password"]))


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
    return Response(services.refresh(body["refresh_token"]))


@extend_schema(tags=AUTH, summary="Encerrar a sessão", request=RefreshSerializer, responses={204: None}, auth=[])
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def logout(request):
    body = valid(RefreshSerializer, request.data)
    services.logout(body["refresh_token"])
    return Response(status=204)


@extend_schema(tags=AUTH, summary="Dados da conta logada", responses={200: UserSerializer, **error_responses(401, 404)})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    user = User.objects.filter(pk=request.user.id).first()
    if user is None:
        raise not_found("Usuário")
    return Response(UserSerializer(user).data)


@extend_schema(
    tags=AUTH,
    summary="Trocar a senha",
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
    with services.atomic():
        user.password_hash = services.hash_password(body["new_password"])
        user.save(update_fields=["password_hash"])
        services.revoke_all_for_user(user.id)
    return Response(status=204)


@extend_schema(
    tags=USERS,
    methods=["GET"],
    operation_id="users_list",
    summary="Listar usuários",
    parameters=[
        OpenApiParameter("q", str, description="Busca por nome ou e-mail"),
        OpenApiParameter("role", str, enum=[r.value for r in Role]),
        OpenApiParameter("page", int),
        OpenApiParameter("size", int),
    ],
    responses={200: UserPageSerializer, **error_responses(401, 403)},
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
    qs = User.objects.all()
    q = request.query_params.get("q")
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(email__icontains=q.lower()))
    role = request.query_params.get("role")
    if role:
        if role not in Role.__members__:
            raise ApiError(422, "validation_error", "Confira os campos destacados.", {"role": "Papel inválido."})
        qs = qs.filter(role=role)
    qs = qs.order_by("-created_at", "name")
    page, size = _int(request, "page", 1), _int(request, "size", 20)
    return Response(paginate(qs, page, size, lambda u: UserSerializer(u).data))


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
    user = User.objects.filter(pk=user_id).first()
    if user is None:
        raise not_found("Usuário")
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


def _int(request, name: str, default: int) -> int:
    try:
        return int(request.query_params.get(name, default))
    except ValueError:
        raise ApiError(422, "validation_error", "Confira os campos destacados.", {name: "Informe um número inteiro."}) from None
