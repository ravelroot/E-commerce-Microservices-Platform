"""Envio das tarefas para a fila. O pedido só entra na fila depois do COMMIT (transaction.on_commit)."""

from __future__ import annotations

import threading
from typing import Protocol

PROCESS_ORDER = "argo.orders.process"
CANCEL_ORDER = "argo.orders.cancel"


class Dispatcher(Protocol):
    def process(self, order_id: int) -> None: ...

    def cancel(self, order_id: int) -> None: ...


class CeleryDispatcher:
    """Publica no Redis pelo app Celery configurado a partir das settings do Django."""

    def process(self, order_id: int) -> None:
        from argo.worker.celery_app import celery

        celery.send_task(PROCESS_ORDER, args=[order_id], queue="orders")

    def cancel(self, order_id: int) -> None:
        from argo.worker.celery_app import celery

        celery.send_task(CANCEL_ORDER, args=[order_id], queue="orders")


class RecordingDispatcher:
    """Usado nos testes: só anota o que iria para a fila."""

    def __init__(self) -> None:
        self.processed: list[int] = []
        self.canceled: list[int] = []

    def process(self, order_id: int) -> None:
        self.processed.append(order_id)

    def cancel(self, order_id: int) -> None:
        self.canceled.append(order_id)


_dispatcher: Dispatcher | None = None
_lock = threading.Lock()


def get_dispatcher() -> Dispatcher:
    global _dispatcher
    with _lock:
        if _dispatcher is None:
            from django.conf import settings

            _dispatcher = RecordingDispatcher() if settings.ARGO_ENVIRONMENT == "test" else CeleryDispatcher()
        return _dispatcher


def set_dispatcher(dispatcher: Dispatcher | None) -> None:
    global _dispatcher
    with _lock:
        _dispatcher = dispatcher
