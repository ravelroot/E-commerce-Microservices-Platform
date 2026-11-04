import os

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Aplica as migrações, cria os dados de demonstração (ARGO_SEED), garante o administrador inicial e sobe o Daphne."

    def add_arguments(self, parser):
        parser.add_argument("--host", default="0.0.0.0")
        parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
        parser.add_argument("--no-migrate", action="store_true", help="Não aplica as migrações ao subir")

    def handle(self, *args, host, port, no_migrate, **options):
        if not no_migrate:
            for alias in settings.DATABASES:
                call_command("migrate", database=alias, interactive=False, verbosity=1)
        if settings.ARGO_SEED:
            call_command("seed")
        if "identity" in settings.ARGO_SERVICES and settings.ARGO_ADMIN_EMAIL and settings.ARGO_ADMIN_PASSWORD:
            call_command("create_admin", no_input=True, if_missing=True)
        from daphne.cli import CommandLineInterface

        mode = " · fila sem Redis (ARGO_INLINE_QUEUE)" if settings.ARGO_INLINE_QUEUE else ""
        self.stdout.write(f"Argo {settings.ARGO_VERSION} · {settings.ARGO_SERVICE} na porta {port}{mode}")
        CommandLineInterface().run(["-b", host, "-p", str(port), "--proxy-headers", "-v", "0", "argo.asgi:application"])
