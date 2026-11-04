from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Põe de novo na fila pedidos parados em Processando e pedidos confirmados sem e-mail ou nota fiscal."

    def add_arguments(self, parser):
        parser.add_argument("--minutes", type=int, default=settings.ARGO_RECOVER_AFTER_MINUTES)
        parser.add_argument("--dry-run", action="store_true", help="Só lista, sem enfileirar")

    def handle(self, *args, minutes, dry_run, **options):
        if "orders" not in settings.ARGO_SERVICES:
            raise CommandError("Rode com ARGO_SERVICE=orders ou ARGO_SERVICE=all.")
        from argo.orders.services import stale_orders

        found = stale_orders(minutes)
        for label, key in (("Processando", "pending"), ("Sem e-mail", "missing_email"), ("Sem nota fiscal", "missing_invoice")):
            ids = ", ".join(f"AR-{i:06d}" for i in found[key]) or "nenhum"
            self.stdout.write(f"{label}: {ids}")
        if dry_run:
            return
        from argo.orders.dispatch import get_dispatcher
        from argo.worker.celery_app import celery

        for order_id in found["pending"]:
            get_dispatcher().process(order_id)
        for order_id in found["missing_email"]:
            celery.send_task("argo.orders.email", args=[order_id], queue="orders")
        for order_id in found["missing_invoice"]:
            celery.send_task("argo.orders.invoice", args=[order_id], queue="orders")
        total = sum(len(v) for v in found.values())
        self.stdout.write(self.style.SUCCESS(f"{total} tarefa(s) enviada(s) para a fila."))
