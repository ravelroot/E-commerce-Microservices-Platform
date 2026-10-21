import re

from rest_framework import serializers

from argo.common.security import Role

from .models import User

PASSWORD_RULE = "A senha precisa ter ao menos 8 caracteres, com letras e números."


def check_password(value: str) -> str:
    if len(value) < 8 or not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise serializers.ValidationError(PASSWORD_RULE)
    return value


def clean_name(value: str) -> str:
    value = " ".join(value.split())
    if len(value) < 2:
        raise serializers.ValidationError("Informe um nome.")
    return value


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(help_text="cliente@argo.dev")
    password = serializers.CharField(min_length=1, max_length=128, trim_whitespace=False, help_text="Argo@2026")


class RegisterSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=2, max_length=120, help_text="Loja Exemplo")
    email = serializers.EmailField(help_text="nova.loja@argo.dev")
    password = serializers.CharField(max_length=128, trim_whitespace=False, validators=[check_password])
    role = serializers.ChoiceField(
        choices=["CUSTOMER", "SELLER"],
        default="CUSTOMER",
        help_text="Cadastro público só cria Cliente ou Vendedor. Administrador é criado por outro administrador.",
    )

    def validate_name(self, value: str) -> str:
        return clean_name(value)


class UserCreateSerializer(RegisterSerializer):
    role = serializers.ChoiceField(choices=[r.value for r in Role], default="CUSTOMER")


class RefreshSerializer(serializers.Serializer):
    refresh_token = serializers.CharField(min_length=20, help_text="vX2...token-opaco...")


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(trim_whitespace=False)
    new_password = serializers.CharField(max_length=128, trim_whitespace=False, validators=[check_password])


class UserUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=[r.value for r in Role], required=False, allow_null=True)
    active = serializers.BooleanField(required=False, allow_null=True)
    name = serializers.CharField(min_length=2, max_length=120, required=False, allow_null=True)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "name", "email", "role", "active", "created_at", "last_login_at"]


class TokenPairSerializer(serializers.Serializer):
    access_token = serializers.CharField(help_text="JWT HS256 com sub, role, name, email e exp")
    refresh_token = serializers.CharField(help_text="Token opaco de uso único; troque em POST /auth/refresh")
    token_type = serializers.CharField(default="bearer")
    expires_in = serializers.IntegerField(help_text="Segundos até o access token expirar (900)")
    user = UserSerializer()


class UserPageSerializer(serializers.Serializer):
    items = UserSerializer(many=True)
    page = serializers.IntegerField()
    size = serializers.IntegerField()
    total = serializers.IntegerField()
