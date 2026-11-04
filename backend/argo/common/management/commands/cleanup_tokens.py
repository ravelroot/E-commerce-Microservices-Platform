from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Apaga refresh tokens expirados ou revogados há mais de N dias (serviço de identidade)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=settings.ARGO_TOKEN_RETENTION_DAYS)

    def handle(self, *args, days, **options):
        if "identity" not in settings.ARGO_SERVICES:
            raise CommandError("Rode com ARGO_SERVICE=identity ou ARGO_SERVICE=all.")
        from argo.identity.services import cleanup_tokens

        deleted = cleanup_tokens(days)
        self.stdout.write(self.style.SUCCESS(f"{deleted} refresh token(s) removido(s)."))
