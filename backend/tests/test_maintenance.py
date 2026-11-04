import json
import logging
from datetime import timedelta
from io import StringIO

import httpx
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from argo.common.demo import demo_id
from argo.common.utils import utcnow
from argo.worker import tasks

COFFEE = demo_id("p01")


def place(orders, auth, qty=1):
    return orders.post("/orders", headers=auth("cliente"), json={"items": [{"product_id": COFFEE, "quantity": qty}]}).json()["id"]


def test_shipping_and_delivery_emails(orders, worker, auth, mailoutbox):
    oid = place(orders, auth)
    worker.drain()
    orders.patch(f"/orders/{oid}/status", headers=auth("vendedor"), json={"status": "SHIPPED", "note": "Rastreio BR987654321BR"})
    worker.drain()
    shipped = mailoutbox[-1]
    assert shipped.subject == f"Pedido AR-{oid:06d} enviado"
    assert "BR987654321BR" in shipped.body and "BR987654321BR" in shipped.alternatives[0].content
    orders.patch(f"/orders/{oid}/status", headers=auth("vendedor"), json={"status": "DELIVERED"})
    worker.drain()
    assert mailoutbox[-1].subject == f"Pedido AR-{oid:06d} entregue"
    assert len(mailoutbox) == 3
    assert tasks.send_status_email.run(oid, "SHIPPED") == {"order": oid, "sent": False}


def test_status_email_smtp_failure_is_transient(orders, worker, auth, monkeypatch):
    oid = place(orders, auth)
    worker.drain()
    orders.patch(f"/orders/{oid}/status", headers=auth("vendedor"), json={"status": "SHIPPED"})
    worker.dispatcher.notified.clear()

    def broken(*_):
        raise OSError("smtp fora do ar")

    monkeypatch.setattr(worker.mailer, "send", broken)
    with pytest.raises(tasks.TransientError):
        tasks.send_status_email.run(oid, "SHIPPED")


def test_recover_task_requeues_and_finishes_orders(orders, worker, auth, mailoutbox):
    from argo.orders.models import Order

    oid = place(orders, auth)
    worker.dispatcher.processed.clear()
    Order.objects.filter(pk=oid).update(created_at=utcnow() - timedelta(minutes=30))
    result = tasks.recover_orders.apply().get()
    assert result == {"pending": 1, "missing_email": 0, "missing_invoice": 0}
    order = orders.get(f"/orders/{oid}", headers=auth("cliente")).json()
    assert order["status"] == "CONFIRMED" and order["invoice_number"] and order["email_sent_at"]

    Order.objects.filter(pk=oid).update(invoice_number=None, email_sent_at=None, updated_at=utcnow() - timedelta(minutes=30))
    result = tasks.recover_orders.apply().get()
    assert result == {"pending": 0, "missing_email": 1, "missing_invoice": 1}
    assert orders.get(f"/orders/{oid}", headers=auth("cliente")).json()["invoice_number"]


def test_cleanup_task_calls_identity(worker, identity):
    assert tasks.cleanup_tokens.apply().get() == {"deleted": 0}


def test_recover_orders_command(orders, worker, auth):
    from argo.orders.models import Order

    oid = place(orders, auth)
    worker.dispatcher.processed.clear()
    Order.objects.filter(pk=oid).update(created_at=utcnow() - timedelta(minutes=30))
    out = StringIO()
    call_command("recover_orders", dry_run=True, stdout=out)
    assert f"AR-{oid:06d}" in out.getvalue()
    assert worker.dispatcher.processed == []
    call_command("recover_orders", stdout=out)
    assert worker.dispatcher.processed == [oid]


@pytest.mark.nodb
def test_dispatcher_builder():
    from argo.orders.dispatch import CeleryDispatcher, InlineDispatcher, RecordingDispatcher, build_dispatcher

    assert isinstance(build_dispatcher("test", True), RecordingDispatcher)
    assert isinstance(build_dispatcher("production", True), InlineDispatcher)
    assert isinstance(build_dispatcher("production", False), CeleryDispatcher)


def test_inline_dispatcher_runs_tasks_in_a_thread(orders, worker, auth, monkeypatch):
    import threading

    from argo.orders.dispatch import InlineDispatcher

    calls = []
    done = threading.Event()

    def fake_apply(args):
        calls.append(args)
        done.set()

    monkeypatch.setattr(tasks.process_order, "apply", fake_apply)
    InlineDispatcher().process(7)
    assert done.wait(5)
    assert calls == [[7]]


def test_celery_dispatcher_sends_with_request_id(monkeypatch):
    from argo.common.context import request_id
    from argo.orders.dispatch import CeleryDispatcher
    from argo.worker.celery_app import celery

    sent = []
    monkeypatch.setattr(celery, "send_task", lambda name, **kw: sent.append((name, kw)))
    token = request_id.set("abc123")
    try:
        d = CeleryDispatcher()
        d.process(1)
        d.cancel(2)
        d.status_changed(3, "SHIPPED")
    finally:
        request_id.reset(token)
    assert [s[0] for s in sent] == ["argo.orders.process", "argo.orders.cancel", "argo.orders.status_email"]
    assert sent[2][1]["args"] == [3, "SHIPPED"] and sent[0][1]["headers"] == {"argo_request_id": "abc123"}


def test_service_client_propagates_request_id():
    from argo.common.context import request_id
    from argo.common.http import service_client

    seen = {}

    def handler(request):
        seen.update(request.headers)
        return httpx.Response(200, json={})

    client = service_client("http://x", "segredo")
    client._transport = httpx.MockTransport(handler)
    token = request_id.set("rid-0001")
    try:
        client.get("/a")
    finally:
        request_id.reset(token)
    assert seen["x-request-id"] == "rid-0001" and seen["x-internal-token"] == "segredo"


@pytest.mark.nodb
def test_json_log_formatter():
    from argo.common.context import request_id
    from argo.common.logs import JsonFormatter, RequestIdFilter

    record = logging.LogRecord("argo.http", logging.INFO, __file__, 1, "GET %s", ("/x",), None)
    record.status = 200
    token = request_id.set("rid-42")
    try:
        RequestIdFilter().filter(record)
        data = json.loads(JsonFormatter("catalog").format(record))
    finally:
        request_id.reset(token)
    assert data["message"] == "GET /x" and data["request_id"] == "rid-42"
    assert data["service"] == "catalog" and data["status"] == 200 and data["level"] == "INFO"


def test_deploy_checks_flag_weak_secrets(settings):
    from argo.common.checks import check_secrets

    settings.ARGO_JWT_SECRET = "troque-este-segredo-por-um-valor-longo-e-aleatorio"
    settings.ARGO_INTERNAL_TOKEN = "curto"
    assert {w.id for w in check_secrets(None)} == {"argo.W001", "argo.W002"}
    settings.ARGO_JWT_SECRET = settings.ARGO_INTERNAL_TOKEN = "um-segredo-bem-comprido-e-aleatorio-123456"
    assert {w.id for w in check_secrets(None)} == {"argo.W003"}
    settings.ARGO_INTERNAL_TOKEN = "outro-segredo-bem-comprido-123456"
    assert check_secrets(None) == []


def test_doctor_reports_databases_and_failures(settings):
    settings.ARGO_INLINE_QUEUE = True
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    out = StringIO()
    call_command("doctor", skip_http=True, stdout=out)
    text = out.getvalue()
    assert "Banco default" in text and "Banco catalog" in text and "Tudo certo." in text

    settings.ARGO_INLINE_QUEUE = False
    settings.ARGO_REDIS_URL = "redis://127.0.0.1:1/0"
    settings.ARGO_IDENTITY_URL = "http://127.0.0.1:1/api/identity"
    with pytest.raises(CommandError):
        call_command("doctor", stdout=StringIO())


def test_cors_middleware_answers_preflight(settings, wsgi):
    from django.test import RequestFactory

    from argo.common.middleware import CorsMiddleware

    settings.ARGO_CORS_ORIGINS = ["https://painel.exemplo"]
    middleware = CorsMiddleware(lambda request: __import__("django.http", fromlist=["HttpResponse"]).HttpResponse("ok"))
    rf = RequestFactory()
    pre = middleware(rf.options("/api/orders/orders", HTTP_ORIGIN="https://painel.exemplo"))
    assert pre.status_code == 204 and pre["Access-Control-Allow-Origin"] == "https://painel.exemplo"
    assert "Idempotency-Key" in pre["Access-Control-Allow-Headers"]
    other = middleware(rf.get("/api/orders/orders", HTTP_ORIGIN="https://outro.exemplo"))
    assert "Access-Control-Allow-Origin" not in other
