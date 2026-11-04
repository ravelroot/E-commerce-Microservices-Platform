from __future__ import annotations

import logging
import threading
from typing import Protocol

from argo.common.context import current_request_id, request_id

PROCESS_ORDER = "argo.orders.process"
CANCEL_ORDER = "argo.orders.cancel"
STATUS_EMAIL = "argo.orders.status_email"

log = logging.getLogger("argo.dispatch")


class Dispatcher(Protocol):
    def process(self, order_id: int) -> None: ...

    def cancel(self, order_id: int) -> None: ...

    def status_changed(self, order_id: int, status: str) -> None: ...


class CeleryDispatcher:
    def _send(self, name: str, *args) -> None:
        from argo.worker.celery_app import celery

        headers = {"argo_request_id": current_request_id()} if current_request_id() else None
        celery.send_task(name, args=list(args), queue="orders", headers=headers)

    def process(self, order_id: int) -> None:
        self._send(PROCESS_ORDER, order_id)

    def cancel(self, order_id: int) -> None:
        self._send(CANCEL_ORDER, order_id)

    def status_changed(self, order_id: int, status: str) -> None:
        self._send(STATUS_EMAIL, order_id, status)


class InlineDispatcher:
    def _run(self, name: str, *args) -> None:
        rid = current_request_id()

        def target() -> None:
            token = request_id.set(rid)
            try:
                from argo.worker import tasks

                task = {
                    PROCESS_ORDER: tasks.process_order,
                    CANCEL_ORDER: tasks.cancel_order,
                    STATUS_EMAIL: tasks.send_status_email,
                }[name]
                task.apply(args=list(args))
            except Exception:
                log.exception("falha ao executar %s sem fila %s", name, args)
            finally:
                request_id.reset(token)

        threading.Thread(target=target, name=f"argo-inline-{args[0]}", daemon=True).start()

    def process(self, order_id: int) -> None:
        self._run(PROCESS_ORDER, order_id)

    def cancel(self, order_id: int) -> None:
        self._run(CANCEL_ORDER, order_id)

    def status_changed(self, order_id: int, status: str) -> None:
        self._run(STATUS_EMAIL, order_id, status)


class RecordingDispatcher:
    def __init__(self) -> None:
        self.processed: list[int] = []
        self.canceled: list[int] = []
        self.notified: list[tuple[int, str]] = []

    def process(self, order_id: int) -> None:
        self.processed.append(order_id)

    def cancel(self, order_id: int) -> None:
        self.canceled.append(order_id)

    def status_changed(self, order_id: int, status: str) -> None:
        self.notified.append((order_id, status))


_dispatcher: Dispatcher | None = None
_lock = threading.Lock()


def build_dispatcher(environment: str, inline: bool) -> Dispatcher:
    if environment == "test":
        return RecordingDispatcher()
    if inline:
        return InlineDispatcher()
    return CeleryDispatcher()


def get_dispatcher() -> Dispatcher:
    global _dispatcher
    with _lock:
        if _dispatcher is None:
            from django.conf import settings

            _dispatcher = build_dispatcher(settings.ARGO_ENVIRONMENT, settings.ARGO_INLINE_QUEUE)
        return _dispatcher


def set_dispatcher(dispatcher: Dispatcher | None) -> None:
    global _dispatcher
    with _lock:
        _dispatcher = dispatcher
