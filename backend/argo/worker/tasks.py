"""Tarefas da fila de pedidos (Celery). Falam com os serviços só por HTTP, com X-Internal-Token.

Erros de rede, 5xx, 408 e 429 são temporários: a tarefa tenta de novo com espera exponencial.
Cada tarefa confere a situação do pedido antes de agir, então pode rodar mais de uma vez sem efeito duplicado.
"""

import logging

import httpx
from django.conf import settings

from argo.common.http import service_client
from argo.orders.dispatch import CANCEL_ORDER, PROCESS_ORDER

from .celery_app import celery
from .mailer import DjangoMailer, Mailer, confirmation_email

log = logging.getLogger("argo.worker")

CONFIRMED_STATES = ("CONFIRMED", "SHIPPED", "DELIVERED")


class TransientError(Exception):
    pass


class PermanentError(Exception):
    pass


class Services:
    """Clientes HTTP e o e-mail, criados sob demanda a partir das settings do Django (trocáveis nos testes)."""

    def __init__(self) -> None:
        self._catalog: httpx.Client | None = None
        self._orders: httpx.Client | None = None
        self._billing: httpx.Client | None = None
        self._mailer: Mailer | None = None

    def configure(self, *, catalog=None, orders=None, billing=None, mailer=None) -> None:
        self._catalog, self._orders, self._billing, self._mailer = catalog, orders, billing, mailer

    @property
    def catalog(self) -> httpx.Client:
        if self._catalog is None:
            self._catalog = service_client(settings.ARGO_CATALOG_URL, settings.ARGO_INTERNAL_TOKEN)
        return self._catalog

    @property
    def orders(self) -> httpx.Client:
        if self._orders is None:
            self._orders = service_client(settings.ARGO_ORDERS_URL, settings.ARGO_INTERNAL_TOKEN)
        return self._orders

    @property
    def billing(self) -> httpx.Client:
        if self._billing is None:
            self._billing = service_client(settings.ARGO_BILLING_URL, settings.ARGO_INTERNAL_TOKEN, timeout=10)
        return self._billing

    @property
    def mailer(self) -> Mailer:
        if self._mailer is None:
            self._mailer = DjangoMailer()
        return self._mailer


services = Services()


def request(client: httpx.Client, method: str, url: str, *, allow_404: bool = False, **kwargs) -> dict | None:
    try:
        resp = client.request(method, url, **kwargs)
    except httpx.HTTPError as exc:
        raise TransientError(f"{method} {url}: {exc}") from exc
    if resp.status_code >= 500 or resp.status_code in (408, 429):
        raise TransientError(f"{method} {url}: HTTP {resp.status_code}")
    if resp.status_code == 404 and allow_404:
        return None
    if resp.status_code >= 400:
        raise PermanentError(f"{method} {url}: HTTP {resp.status_code} {resp.text[:200]}")
    return resp.json() if resp.content else {}


def _order(order_id: int) -> dict:
    return request(services.orders, "GET", f"/internal/orders/{order_id}")


def _event(order_id: int, type_: str, **extra) -> dict:
    return request(services.orders, "POST", f"/internal/orders/{order_id}/events", json={"type": type_, **extra})


RETRY = {
    "bind": True,
    "autoretry_for": (TransientError,),
    "retry_backoff": 2,
    "retry_backoff_max": 60,
    "retry_jitter": True,
    "max_retries": 8,
}


@celery.task(name=PROCESS_ORDER, **RETRY)
def process_order(self, order_id: int) -> dict:
    order = _order(order_id)
    if order["status"] != "PENDING":
        return {"order": order_id, "skipped": order["status"]}

    items = [{"product_id": i["product_id"], "quantity": i["quantity"]} for i in order["items"]]
    result = request(services.catalog, "POST", "/internal/stock/commit", json={"order_id": order_id, "items": items})
    if not result["ok"]:
        missing = "; ".join(f"{s['name']} (pedido {s['requested']}, disponível {s['available']})" for s in result["shortages"])
        _event(order_id, "rejected", reason=f"Estoque insuficiente: {missing}.")
        log.info("pedido %s recusado: %s", order_id, missing)
        return {"order": order_id, "status": "REJECTED"}

    updated = _event(order_id, "confirmed")
    if updated["status"] != "CONFIRMED":
        request(services.catalog, "POST", "/internal/stock/release", json={"order_id": order_id})
        _event(order_id, "released")
        return {"order": order_id, "status": updated["status"]}

    send_confirmation_email.delay(order_id)
    issue_invoice.delay(order_id)
    log.info("pedido %s confirmado", order_id)
    return {"order": order_id, "status": "CONFIRMED"}


@celery.task(name="argo.orders.email", **RETRY)
def send_confirmation_email(self, order_id: int) -> dict:
    order = _order(order_id)
    if order["email_sent_at"] or order["status"] not in CONFIRMED_STATES:
        return {"order": order_id, "sent": False}
    subject, text, html = confirmation_email(order, settings.ARGO_PUBLIC_URL)
    try:
        services.mailer.send(order["customer_email"], subject, text, html)
    except OSError as exc:
        raise TransientError(f"SMTP: {exc}") from exc
    _event(order_id, "email_sent")
    return {"order": order_id, "sent": True}


@celery.task(name="argo.orders.invoice", **RETRY)
def issue_invoice(self, order_id: int) -> dict:
    order = _order(order_id)
    if order["invoice_number"] or order["status"] not in CONFIRMED_STATES:
        return {"order": order_id, "invoice": order["invoice_number"]}
    payload = {
        "orderId": order["id"],
        "orderCode": order["code"],
        "customerId": order["customer_id"],
        "customerName": order["customer_name"],
        "totalCents": order["total_cents"],
        "items": [
            {
                "productId": i["product_id"],
                "sellerId": i["seller_id"],
                "description": i["product_name"],
                "quantity": i["quantity"],
                "unitPriceCents": i["unit_price_cents"],
            }
            for i in order["items"]
        ],
    }
    invoice = request(services.billing, "POST", "/internal/invoices", json=payload)
    _event(order_id, "invoiced", invoice_number=invoice["number"])
    return {"order": order_id, "invoice": invoice["number"]}


@celery.task(name=CANCEL_ORDER, **RETRY)
def cancel_order(self, order_id: int) -> dict:
    order = _order(order_id)
    if order["status"] != "CANCELED":
        return {"order": order_id, "skipped": order["status"]}
    released = request(services.catalog, "POST", "/internal/stock/release", json={"order_id": order_id})
    if released["released"]:
        _event(order_id, "released")
    request(services.billing, "POST", f"/internal/invoices/{order_id}/cancel", allow_404=True)
    return {"order": order_id, "released": released["released"]}
