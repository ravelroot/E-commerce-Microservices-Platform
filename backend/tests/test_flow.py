import pytest

from argo.common.demo import demo_id
from argo.worker import tasks

COFFEE = demo_id("p01")
OLIVE = demo_id("p04")
NOTEBOOK = demo_id("p09")


def stock(catalog, auth, pid):
    return catalog.get(f"/products/{pid}", headers=auth("cliente")).json()["stock"]


def test_order_is_confirmed_by_the_queue(orders, catalog, worker, auth, mailoutbox):
    oid = orders.post(
        "/orders",
        headers=auth("cliente"),
        json={"items": [{"product_id": COFFEE, "quantity": 2}, {"product_id": NOTEBOOK, "quantity": 3}]},
    ).json()["id"]
    assert stock(catalog, auth, COFFEE) == 48
    worker.drain()

    order = orders.get(f"/orders/{oid}", headers=auth("cliente")).json()
    assert order["status"] == "CONFIRMED"
    assert order["invoice_number"] == "NF-2026-000001"
    assert order["email_sent_at"]
    assert stock(catalog, auth, COFFEE) == 46 and stock(catalog, auth, NOTEBOOK) == 57

    mail = mailoutbox[0]
    assert mail.to == ["cliente@argo.dev"]
    assert mail.subject == f"Pedido AR-{oid:06d} confirmado"
    assert "R$ 230,50" in mail.body
    assert mail.alternatives[0].mimetype == "text/html"
    sent = worker.billing.invoices[oid]["body"]
    assert sent["totalCents"] == 2 * 6290 + 3 * 3490 and len(sent["items"]) == 2

    tasks.process_order.apply(args=[oid]).get()
    tasks.send_confirmation_email.apply(args=[oid]).get()
    tasks.issue_invoice.apply(args=[oid]).get()
    assert len(mailoutbox) == 1 and len(worker.billing.invoices) == 1
    assert stock(catalog, auth, COFFEE) == 46


def test_order_is_rejected_when_stock_ran_out(orders, catalog, worker, auth, mailoutbox):
    oid = orders.post("/orders", headers=auth("cliente"), json={"items": [{"product_id": OLIVE, "quantity": 3}]}).json()["id"]

    catalog.post(f"/products/{OLIVE}/stock", headers=auth("vendedor"), json={"kind": "OUT", "quantity": 2})
    worker.drain()
    order = orders.get(f"/orders/{oid}", headers=auth("cliente")).json()
    assert order["status"] == "REJECTED"
    assert "Azeite" in order["rejection_reason"]
    assert stock(catalog, auth, OLIVE) == 2
    assert mailoutbox == [] and worker.billing.invoices == {}


def test_cancel_after_confirmation_returns_stock_and_cancels_invoice(orders, catalog, worker, auth):
    oid = orders.post("/orders", headers=auth("cliente"), json={"items": [{"product_id": COFFEE, "quantity": 5}]}).json()["id"]
    worker.drain()
    assert stock(catalog, auth, COFFEE) == 43
    orders.post(f"/orders/{oid}/cancel", headers=auth("cliente"))
    worker.drain()
    assert stock(catalog, auth, COFFEE) == 48
    assert worker.billing.canceled == [oid]
    notes = [h["note"] for h in orders.get(f"/orders/{oid}", headers=auth("cliente")).json()["history"]]
    assert "Itens devolvidos ao estoque." in notes


def test_cancel_before_processing_skips_everything(orders, catalog, worker, auth, mailoutbox):
    oid = orders.post("/orders", headers=auth("cliente"), json={"items": [{"product_id": COFFEE, "quantity": 1}]}).json()["id"]
    orders.post(f"/orders/{oid}/cancel", headers=auth("cliente"))
    worker.drain()
    assert stock(catalog, auth, COFFEE) == 48
    assert worker.billing.canceled == [] and mailoutbox == []


def test_cancel_while_queue_is_working(orders, catalog, worker, auth, monkeypatch):
    oid = orders.post("/orders", headers=auth("cliente"), json={"items": [{"product_id": COFFEE, "quantity": 4}]}).json()["id"]
    original = tasks._event

    def racing(order_id, type_, **extra):
        if type_ == "confirmed":
            orders.post(f"/orders/{order_id}/cancel", headers=auth("cliente"))
        return original(order_id, type_, **extra)

    monkeypatch.setattr(tasks, "_event", racing)
    result = tasks.process_order.apply(args=[oid]).get()
    assert result["status"] == "CANCELED"
    assert stock(catalog, auth, COFFEE) == 48


def test_billing_outage_is_retried(orders, worker, auth):
    oid = orders.post("/orders", headers=auth("cliente"), json={"items": [{"product_id": COFFEE, "quantity": 1}]}).json()["id"]
    worker.billing.fail_next = 1
    with pytest.raises(tasks.TransientError):
        tasks.request(tasks.services.billing, "POST", "/internal/invoices", json={})
    worker.drain()
    assert orders.get(f"/orders/{oid}", headers=auth("cliente")).json()["invoice_number"]


def test_request_helper_classifies_errors(worker):
    import httpx

    def handler(request):
        return {"/a": httpx.Response(404), "/b": httpx.Response(400, text="ruim"), "/c": httpx.Response(429)}[request.url.path]

    client = httpx.Client(base_url="http://x", transport=httpx.MockTransport(handler))
    assert tasks.request(client, "GET", "/a", allow_404=True) is None
    with pytest.raises(tasks.PermanentError):
        tasks.request(client, "GET", "/b")
    with pytest.raises(tasks.TransientError):
        tasks.request(client, "GET", "/c")

    def offline(_):
        raise httpx.ConnectError("offline")

    with pytest.raises(tasks.TransientError):
        tasks.request(httpx.Client(base_url="http://x", transport=httpx.MockTransport(offline)), "GET", "/")


def test_smtp_failure_is_transient(orders, worker, auth, monkeypatch):
    oid = orders.post("/orders", headers=auth("cliente"), json={"items": [{"product_id": COFFEE, "quantity": 1}]}).json()["id"]
    h = {"X-Internal-Token": "token-interno-de-teste"}
    orders.post(f"/internal/orders/{oid}/events", headers=h, json={"type": "confirmed"})

    def broken(*_):
        raise OSError("smtp fora do ar")

    monkeypatch.setattr(worker.mailer, "send", broken)
    with pytest.raises(tasks.TransientError):
        tasks.send_confirmation_email.run(oid)


def test_skips_orders_in_other_states(orders, worker, auth):
    oid = orders.post("/orders", headers=auth("cliente"), json={"items": [{"product_id": COFFEE, "quantity": 1}]}).json()["id"]
    assert tasks.cancel_order.run(oid) == {"order": oid, "skipped": "PENDING"}
    assert tasks.send_confirmation_email.run(oid) == {"order": oid, "sent": False}
    assert tasks.issue_invoice.run(oid) == {"order": oid, "invoice": None}
