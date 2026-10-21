"""Entrada ASGI (Daphne). ASGI é necessário para o estoque em tempo real (Server-Sent Events)."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "argo.settings")
application = get_asgi_application()
