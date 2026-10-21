import os

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Aplica as migrações, cria os dados de demonstração (ARGO_SEED) e sobe o serviço no Daphne (ASGI)."

    def add_arguments(self, parser):
        parser.add_argument("--host", default="0.0.0.0")
        parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))

    def handle(self, *args, host, port, **options):
        for alias in settings.DATABASES:
            call_command("migrate", database=alias, interactive=False, verbosity=1)
        if settings.ARGO_SEED:
            call_command("seed")
        from daphne.cli import CommandLineInterface

        self.stdout.write(f"Argo · {settings.ARGO_SERVICE} na porta {port}")
        CommandLineInterface().run(["-b", host, "-p", str(port), "--proxy-headers", "-v", "0", "argo.asgi:application"])
