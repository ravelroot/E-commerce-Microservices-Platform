from rest_framework import serializers


def valid(serializer_class: type[serializers.Serializer], data) -> dict:
    """Valida e devolve os dados limpos; erro vira 422 ``validation_error`` com os campos."""
    s = serializer_class(data=data)
    s.is_valid(raise_exception=True)
    return dict(s.validated_data)


class IntegerField(serializers.IntegerField):
    """Inteiro com mensagens em português claro (a tradução padrão do DRF tem erro de digitação)."""

    default_error_messages = {
        "invalid": "Informe um número inteiro.",
        "min_value": "Informe um valor maior ou igual a {min_value}.",
        "max_value": "Informe um valor menor ou igual a {max_value}.",
        "max_string_length": "Número grande demais.",
    }
