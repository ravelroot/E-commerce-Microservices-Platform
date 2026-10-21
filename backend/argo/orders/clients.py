"""Cliente HTTP do catálogo usado no checkout (com X-Internal-Token)."""

from __future__ import annotations

import threading

import httpx
from django.conf import settings

from argo.common.http import service_client

_catalog: httpx.Client | None = None
_lock = threading.Lock()


def catalog() -> httpx.Client:
    global _catalog
    with _lock:
        if _catalog is None:
            _catalog = service_client(settings.ARGO_CATALOG_URL, settings.ARGO_INTERNAL_TOKEN)
        return _catalog


def set_catalog(client: httpx.Client | None) -> None:
    global _catalog
    with _lock:
        _catalog = client
