"""Roteador de bancos: cada app de serviço grava só no próprio banco.

Com um serviço por processo (produção), tudo vai para ``default``. No modo
``all`` (desenvolvimento e testes) o catálogo usa o banco ``catalog``, os
pedidos usam ``orders`` e a identidade fica no ``default``.
"""

from django.conf import settings

SERVICE_LABELS = {"identity", "catalog", "orders"}


def alias_for(app_label: str) -> str:
    return app_label if app_label in settings.DATABASES else "default"


class ServiceRouter:
    def db_for_read(self, model, **hints):
        label = model._meta.app_label
        return alias_for(label) if label in SERVICE_LABELS else None

    db_for_write = db_for_read

    def allow_relation(self, obj1, obj2, **hints):
        return obj1._meta.app_label == obj2._meta.app_label

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in SERVICE_LABELS:
            return db == alias_for(app_label)
        return None
