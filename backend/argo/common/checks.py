from django.conf import settings
from django.core.checks import Tags, Warning, register

DEFAULT_SECRETS = {
    "troque-este-segredo-por-um-valor-longo-e-aleatorio",
    "troque-por-um-valor-aleatorio-com-pelo-menos-32-caracteres",
    "troque-este-token-interno",
    "troque-por-outro-valor-aleatorio",
}


def secret_problems() -> list[tuple[str, str, str]]:
    problems = []
    jwt_secret = settings.ARGO_JWT_SECRET
    internal = settings.ARGO_INTERNAL_TOKEN
    hint = "Gere um valor aleatório longo (o iniciar.sh e o iniciar.cmd já fazem isso)."
    if jwt_secret in DEFAULT_SECRETS or len(jwt_secret) < 32:
        problems.append(("argo.W001", "ARGO_JWT_SECRET é o valor de exemplo ou tem menos de 32 caracteres.", hint))
    if internal in DEFAULT_SECRETS or len(internal) < 24:
        problems.append(("argo.W002", "ARGO_INTERNAL_TOKEN é o valor de exemplo ou tem menos de 24 caracteres.", hint))
    if internal == jwt_secret:
        problems.append(("argo.W003", "ARGO_INTERNAL_TOKEN e ARGO_JWT_SECRET são iguais.", "Use segredos diferentes."))
    if settings.ARGO_INLINE_QUEUE and settings.ARGO_ENVIRONMENT == "production":
        problems.append(("argo.W004", "ARGO_INLINE_QUEUE ligado em produção.", "Use a fila do Celery com Redis em produção."))
    return problems


@register(Tags.security, deploy=True)
def check_secrets(app_configs, **kwargs):
    return [Warning(msg, hint=hint, id=code) for code, msg, hint in secret_problems()]
