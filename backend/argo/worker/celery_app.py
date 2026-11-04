import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "argo.settings")

celery = Celery("argo", include=["argo.worker.tasks"])
celery.config_from_object("django.conf:settings", namespace="CELERY")
