from importlib import import_module

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Cria os dados de demonstração do(s) serviço(s) ativo(s), só se o banco estiver vazio."

    def handle(self, *args, **options):
        for service in settings.ARGO_SERVICES:
            created = import_module(f"argo.{service}.seed").seed()
            self.stdout.write(f"{service}: {'dados de demonstração criados' if created else 'banco já tinha dados'}")
