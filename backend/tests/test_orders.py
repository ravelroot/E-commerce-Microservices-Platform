from argo.common.demo import demo_id

COFFEE = demo_id("p01")
OLIVE = demo_id("p04")
NOTEBOOK = demo_id("p09")
MARKERS = demo_id("p16")


def checkout(orders, auth, items, who="cliente"):
    return orders.post("/orders", headers=auth(who), json={"items": items})


def test_checkout_is_accepted_and_enqueued(orders, auth, dispatcher):
    r = checkout(
        orders,
        auth,
        [{"product_id": COFFEE, "quantity": 2}, {"product_id": NOTEBOOK, "quantity": 1}, {"product_id": COFFEE, "quantity": 1}],
    )
    assert r.status_code == 202
    order = r.json()
    assert order["status"] == "PENDING"
    assert order["code"] == f"AR-{order['id']:06d}"
    assert order["total_cents"] == 3 * 6290 + 3490
    assert order["items_count"] == 4
    assert len(order["items"]) == 2
    assert order["history"][0]["status"] == "PENDING"
    assert dispatcher.processed == [order["id"]]


def test_checkout_validations(orders, auth, dispatcher):
    assert checkout(orders, auth, [{"product_id": COFFEE, "quantity": 1}], who="vendedor").status_code == 403
    r = checkout(orders, auth, [{"product_id": "nao-existe", "quantity": 1}])
    assert r.status_code == 422 and "items.0" in r.json()["fields"]
    r = checkout(orders, auth, [{"product_id": OLIVE, "quantity": 5}])
    assert r.status_code == 409 and "Azeite" in r.json()["message"]
    r = checkout(orders, auth, [{"product_id": MARKERS, "quantity": 1}])
    assert r.status_code == 409
    assert checkout(orders, auth, []).status_code == 422
    assert checkout(orders, auth, [{"product_id": COFFEE, "quantity": 0}]).status_code == 422
    assert dispatcher.processed == []


def test_catalog_unavailable_returns_503(orders, auth):
    import httpx

    from argo.orders.clients import set_catalog

    def boom(_):
        raise httpx.ConnectError("sem rede")

    set_catalog(httpx.Client(base_url="http://catalog", transport=httpx.MockTransport(boom)))
    r = checkout(orders, auth, [{"product_id": COFFEE, "quantity": 1}])
    assert r.status_code == 503 and r.json()["code"] == "service_unavailable"
    set_catalog(httpx.Client(base_url="http://catalog", transport=httpx.MockTransport(lambda _: httpx.Response(500))))
    assert checkout(orders, auth, [{"product_id": COFFEE, "quantity": 1}]).status_code == 503


def test_visibility_by_role(orders, auth):
    a = checkout(orders, auth, [{"product_id": COFFEE, "quantity": 1}]).json()
    b = checkout(orders, auth, [{"product_id": NOTEBOOK, "quantity": 1}], who="c1").json()

    assert [o["id"] for o in orders.get("/orders", headers=auth("cliente")).json()["items"]] == [a["id"]]
    assert [o["id"] for o in orders.get("/orders", headers=auth("vendedor")).json()["items"]] == [a["id"]]
    assert [o["id"] for o in orders.get("/orders", headers=auth("vendedor2")).json()["items"]] == [b["id"]]
    assert orders.get("/orders", headers=auth("admin")).json()["total"] == 2

    assert orders.get(f"/orders/{b['id']}", headers=auth("cliente")).status_code == 404
    assert orders.get(f"/orders/{b['id']}", headers=auth("vendedor2")).status_code == 200
    assert orders.get("/orders/999", headers=auth("admin")).status_code == 404


def test_list_filters(orders, auth):
    a = checkout(orders, auth, [{"product_id": COFFEE, "quantity": 1}]).json()
    checkout(orders, auth, [{"product_id": NOTEBOOK, "quantity": 1}], who="c2")
    h = auth("admin")
    assert orders.get("/orders", headers=h, params={"q": a["code"]}).json()["total"] == 1
    assert orders.get("/orders", headers=h, params={"q": "caio"}).json()["total"] == 1
    assert orders.get("/orders", headers=h, params={"status": "PENDING"}).json()["total"] == 2
    assert orders.get("/orders", headers=h, params={"status": "SHIPPED"}).json()["total"] == 0


def test_cancel_rules(orders, auth, dispatcher):
    order = checkout(orders, auth, [{"product_id": COFFEE, "quantity": 1}]).json()
    oid = order["id"]
    assert orders.post(f"/orders/{oid}/cancel", headers=auth("vendedor")).status_code == 403
    assert orders.post(f"/orders/{oid}/cancel", headers=auth("c1")).status_code == 404
    r = orders.post(f"/orders/{oid}/cancel", headers=auth("cliente"), json={"reason": "Comprei por engano"})
    assert r.status_code == 200 and r.json()["status"] == "CANCELED"
    assert r.json()["history"][-1]["note"] == "Comprei por engano"
    assert dispatcher.canceled == [oid]
    assert orders.post(f"/orders/{oid}/cancel", headers=auth("cliente")).status_code == 409


def test_status_transitions(orders, auth):
    oid = checkout(orders, auth, [{"product_id": COFFEE, "quantity": 1}]).json()["id"]
    h = auth("vendedor")
    r = orders.patch(f"/orders/{oid}/status", headers=h, json={"status": "SHIPPED"})
    assert r.status_code == 409
    orders.post(
        f"/internal/orders/{oid}/events", headers={"X-Internal-Token": "token-interno-de-teste"}, json={"type": "confirmed"}
    )
    assert orders.patch(f"/orders/{oid}/status", headers=auth("vendedor2"), json={"status": "SHIPPED"}).status_code == 404
    assert orders.patch(f"/orders/{oid}/status", headers=auth("cliente"), json={"status": "SHIPPED"}).status_code == 403
    r = orders.patch(f"/orders/{oid}/status", headers=h, json={"status": "SHIPPED", "note": "Rastreio BR1"})
    assert r.json()["status"] == "SHIPPED" and r.json()["history"][-1]["note"] == "Rastreio BR1"
    r = orders.patch(f"/orders/{oid}/status", headers=auth("admin"), json={"status": "DELIVERED"})
    assert r.json()["status"] == "DELIVERED"
    assert [h["status"] for h in r.json()["history"]] == ["PENDING", "CONFIRMED", "SHIPPED", "DELIVERED"]


def test_internal_events_are_idempotent(orders, auth):
    oid = checkout(orders, auth, [{"product_id": COFFEE, "quantity": 1}]).json()["id"]
    h = {"X-Internal-Token": "token-interno-de-teste"}
    for _ in range(2):
        orders.post(f"/internal/orders/{oid}/events", headers=h, json={"type": "confirmed"})
        orders.post(f"/internal/orders/{oid}/events", headers=h, json={"type": "invoiced", "invoice_number": "NF-1"})
        orders.post(f"/internal/orders/{oid}/events", headers=h, json={"type": "email_sent"})
    body = orders.get(f"/internal/orders/{oid}", headers=h).json()
    assert body["status"] == "CONFIRMED" and body["invoice_number"] == "NF-1" and body["email_sent_at"]
    assert len(body["history"]) == 3
    assert orders.post("/internal/orders/999/events", headers=h, json={"type": "confirmed"}).status_code == 404


def test_stats(orders, auth):
    h = {"X-Internal-Token": "token-interno-de-teste"}
    a = checkout(orders, auth, [{"product_id": COFFEE, "quantity": 2}, {"product_id": NOTEBOOK, "quantity": 1}]).json()["id"]
    checkout(orders, auth, [{"product_id": NOTEBOOK, "quantity": 1}], who="c1")
    orders.post(f"/internal/orders/{a}/events", headers=h, json={"type": "confirmed"})

    admin = orders.get("/orders/stats", headers=auth("admin"), params={"days": 7}).json()
    assert admin["revenue_cents"] == 2 * 6290 + 3490
    assert admin["orders"] == 1 and admin["processing"] == 1
    assert admin["by_status"]["CONFIRMED"] == 1
    assert len(admin["daily"]) == 7 and admin["daily"][-1]["revenue_cents"] == admin["revenue_cents"]
    assert admin["top_products"][0]["name"].startswith("Café")

    seller = orders.get("/orders/stats", headers=auth("vendedor2")).json()
    assert seller["revenue_cents"] == 3490
    customer = orders.get("/orders/stats", headers=auth("c1")).json()
    assert customer["revenue_cents"] == 0 and customer["average_ticket_cents"] == 0


def test_seeded_history(orders, auth):
    from argo.orders.seed import seed

    assert seed() is True and seed() is False
    h = auth("admin")
    assert orders.get("/orders", headers=h).json()["total"] == 64
    stats = orders.get("/orders/stats", headers=h).json()
    assert stats["revenue_cents"] > 0 and stats["by_status"]["PENDING"] == 0


def test_query_validation(orders, auth):
    h = auth("admin")
    assert orders.get("/orders", headers=h, params={"status": "SUMIU"}).status_code == 422
    assert orders.get("/orders/stats", headers=h, params={"days": 0}).status_code == 422
    assert orders.get("/orders/abc", headers=h).status_code == 404
