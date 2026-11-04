import socket

import httpx
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.migrations.executor import MigrationExecutor

from argo.common.checks import secret_problems

OK, WARN, FAIL = "ok", "atenção", "falha"


class Command(BaseCommand):
    help = "Confere configuração, bancos, migrações, Redis, SMTP e os outros serviços. Sai com código 1 se algo falhar."

    def add_arguments(self, parser):
        parser.add_argument("--skip-http", action="store_true", help="Não chama a saúde dos outros serviços")

    def handle(self, *args, skip_http, **options):
        self.failures = 0
        head = f"Argo {settings.ARGO_VERSION} · serviço {settings.ARGO_SERVICE} · ambiente {settings.ARGO_ENVIRONMENT}"
        self.stdout.write(head + "\n")
        for code, message, hint in secret_problems():
            self._line(WARN, f"Configuração ({code})", f"{message} {hint}")
        if not secret_problems():
            self._line(OK, "Segredos", "ARGO_JWT_SECRET e ARGO_INTERNAL_TOKEN configurados")
        for alias in settings.DATABASES:
            self._database(alias)
        self._redis()
        self._smtp()
        if not skip_http:
            for name, url in (
                ("identidade", settings.ARGO_IDENTITY_URL),
                ("catálogo", settings.ARGO_CATALOG_URL),
                ("pedidos", settings.ARGO_ORDERS_URL),
                ("faturamento", settings.ARGO_BILLING_URL),
            ):
                self._http(name, url)
        if self.failures:
            raise CommandError(f"{self.failures} verificação(ões) falharam.")
        self.stdout.write(self.style.SUCCESS("\nTudo certo."))

    def _line(self, status: str, label: str, detail: str) -> None:
        style = {OK: self.style.SUCCESS, WARN: self.style.WARNING, FAIL: self.style.ERROR}[status]
        if status == FAIL:
            self.failures += 1
        self.stdout.write(f"{style(f'[{status}]'):<20} {label}: {detail}")

    def _database(self, alias: str) -> None:
        connection = connections[alias]
        try:
            connection.ensure_connection()
            executor = MigrationExecutor(connection)
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        except Exception as exc:
            self._line(FAIL, f"Banco {alias}", f"{exc.__class__.__name__}: {exc}")
            return
        vendor = f"{connection.vendor} {connection.settings_dict.get('NAME')}"
        if plan:
            pending = f"{len(plan)} migração(ões) pendente(s): rode python manage.py migrate"
            self._line(WARN, f"Banco {alias}", f"{vendor} com {pending}")
        else:
            self._line(OK, f"Banco {alias}", f"{vendor}, migrações em dia")

    def _redis(self) -> None:
        if settings.ARGO_INLINE_QUEUE:
            self._line(OK, "Fila", "modo sem Redis (ARGO_INLINE_QUEUE): tarefas rodam no próprio processo")
            return
        try:
            import redis

            redis.Redis.from_url(settings.ARGO_REDIS_URL, socket_connect_timeout=3).ping()
            self._line(OK, "Redis", settings.ARGO_REDIS_URL)
        except Exception as exc:
            self._line(FAIL, "Redis", f"{settings.ARGO_REDIS_URL}: {exc.__class__.__name__}")

    def _smtp(self) -> None:
        options = settings.MAILERS["default"].get("OPTIONS", {})
        host, port = options.get("host"), options.get("port")
        if not host:
            self._line(OK, "E-mail", "backend em memória")
            return
        try:
            with socket.create_connection((host, port), timeout=3):
                pass
            self._line(OK, "SMTP", f"{host}:{port}")
        except OSError as exc:
            self._line(WARN, "SMTP", f"{host}:{port} não respondeu ({exc.__class__.__name__}); e-mails ficam na fila")

    def _http(self, name: str, base: str) -> None:
        url = f"{base.rstrip('/')}/health"
        try:
            response = httpx.get(url, timeout=3)
            data = response.json()
        except Exception as exc:
            self._line(FAIL, f"Serviço de {name}", f"{url}: {exc.__class__.__name__}")
            return
        if response.status_code == 200:
            self._line(OK, f"Serviço de {name}", f"versão {data.get('version')} em {base}")
        else:
            self._line(FAIL, f"Serviço de {name}", f"{url}: HTTP {response.status_code} {data.get('checks', '')}")
