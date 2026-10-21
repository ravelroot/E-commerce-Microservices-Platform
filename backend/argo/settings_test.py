"""Settings dos testes (pytest-django): os três serviços no mesmo processo, SQLite e fila em modo de gravação.

Para rodar os testes no MySQL, defina ARGO_DATABASE_URL, ARGO_CATALOG_DATABASE_URL e
ARGO_ORDERS_DATABASE_URL (mysql://...) antes do pytest; o pytest-django cria e apaga bancos test_<nome>.
"""

import os

os.environ["ARGO_ENVIRONMENT"] = "test"
os.environ["ARGO_SERVICE"] = "all"
os.environ["ARGO_SEED"] = "false"
os.environ["ARGO_JWT_SECRET"] = "segredo-de-teste-com-tamanho-suficiente-para-hs256"
os.environ["ARGO_INTERNAL_TOKEN"] = "token-interno-de-teste"
os.environ["ARGO_PUBLIC_URL"] = "http://argo.test"
os.environ["ARGO_REDIS_URL"] = ""
os.environ["ARGO_CELERY_EAGER"] = "true"
os.environ.pop("ARGO_CORS_ORIGINS", None)

from argo.settings import *

ALLOWED_HOSTS = ["testserver", "localhost"]
