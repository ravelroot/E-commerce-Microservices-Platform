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
