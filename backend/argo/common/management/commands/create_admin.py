import getpass

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from argo.common.errors import ApiError


class Command(BaseCommand):
    help = "Cria um Administrador ou promove uma conta existente (serviço de identidade)."

    def add_arguments(self, parser):
        parser.add_argument("--email", default=settings.ARGO_ADMIN_EMAIL or None)
        parser.add_argument("--name", default=settings.ARGO_ADMIN_NAME)
        parser.add_argument("--password", default=settings.ARGO_ADMIN_PASSWORD or None)
        parser.add_argument("--reset-password", action="store_true", help="Troca a senha se a conta já existir")
        parser.add_argument("--no-input", action="store_true", help="Não pergunta nada; falha se faltar dado")
        parser.add_argument("--if-missing", action="store_true", help="Só cria; não mexe em conta que já existe")

    def handle(self, *args, email, name, password, reset_password, no_input, if_missing, **options):
        if "identity" not in settings.ARGO_SERVICES:
            raise CommandError("Rode com ARGO_SERVICE=identity ou ARGO_SERVICE=all.")
        if not email:
            if no_input:
                raise CommandError("Informe --email ou ARGO_ADMIN_EMAIL.")
            email = input("E-mail do administrador: ").strip()
        from argo.identity import services
        from argo.identity.models import User
        from argo.identity.serializers import PASSWORD_RULE, check_password

        exists = User.objects.filter(email=email.strip().lower()).exists()
        if exists and if_missing:
            self.stdout.write(f"{email.strip().lower()}: conta já existe, nada a fazer.")
            return
        if not password and (not exists or reset_password):
            if no_input:
                raise CommandError("Informe --password ou ARGO_ADMIN_PASSWORD.")
            password = getpass.getpass("Senha: ")
            if password != getpass.getpass("Repita a senha: "):
                raise CommandError("As senhas não conferem.")
        if password:
            try:
                check_password(password)
            except Exception as exc:
                raise CommandError(PASSWORD_RULE) from exc
        try:
            user, created = services.ensure_admin(email=email, password=password, name=name, reset_password=reset_password)
        except ApiError as exc:
            raise CommandError(exc.message) from exc
        action = "criado" if created else "promovido a Administrador"
        self.stdout.write(self.style.SUCCESS(f"{user.email}: {action}."))
