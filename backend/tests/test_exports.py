import csv
import io
from datetime import timedelta

from argo.common.demo import demo_id
from argo.common.utils import utcnow

COFFEE = demo_id("p01")
NOTEBOOK = demo_id("p09")
INTERNAL = {"X-Internal-Token": "token-interno-de-teste"}


def rows(response):
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"].startswith("attachment;")
    text = response.content.decode("utf-8")
    assert text.startswith("﻿")
    return list(csv.reader(io.StringIO(text.lstrip("﻿")), delimiter=";"))


def test_price_and_stock_filters(catalog, auth):
    h = auth("cliente")
    r = catalog.get("/products", headers=h, params={"min_price": 5000, "max_price": 6000, "size": 100})
    assert {p["sku"] for p in r.json()["items"]} == {"AUR-AZE-04", "NOR-VEL-05"}
    r = catalog.get("/products", headers=h, params={"in_stock": "true", "size": 100})
    assert r.json()["total"] == 15
    r = catalog.get("/products", headers=h, params={"min_price": 9000, "max_price": 100})
    assert r.status_code == 422 and "max_price" in r.json()["fields"]


def test_stock_feed_is_scoped(catalog, auth):
    catalog.post(f"/products/{COFFEE}/stock", headers=auth("vendedor"), json={"kind": "IN", "quantity": 3, "reason": "Reposição"})
    mine = catalog.get("/stock/movements", headers=auth("vendedor"), params={"size": 100}).json()
    assert mine["total"] == 9
    first = mine["items"][0]
    assert first["product_id"] == COFFEE and first["delta"] == 3 and first["stock"] == 51 and first["reason"] == "Reposição"
    assert first["product_name"].startswith("Café") and first["low"] is False
    assert all(i["seller_id"] == demo_id("vendedor") for i in mine["items"])
    admin = catalog.get("/stock/movements", headers=auth("admin"), params={"size": 100}).json()
    assert admin["total"] == 16
    only_in = catalog.get("/stock/movements", headers=auth("admin"), params={"kind": "IN", "product_id": COFFEE}).json()
    assert only_in["total"] == 2
    assert catalog.get("/stock/movements", headers=auth("cliente")).status_code == 403
    assert catalog.get("/stock/movements", headers=auth("admin"), params={"kind": "X"}).status_code == 422


def test_products_export(catalog, auth):
    data = rows(catalog.get("/products/export", headers=auth("vendedor")))
    assert data[0][:5] == ["SKU", "Nome", "Categoria", "Loja", "Preço (R$)"]
    assert len(data) == 9
    coffee = next(r for r in data if r[0] == "AUR-CAF-01")
    assert coffee[4] == "62,90" and coffee[5] == "48" and coffee[7] == "3019,20" and coffee[8] == "sim"
    as_csv = {**auth("admin"), "Accept": "text/csv"}
    everything = rows(catalog.get("/products/export", headers=as_csv, params={"category": "Casa"}))
    assert len(everything) == 6
    assert catalog.get("/products/export", headers=auth("cliente")).status_code == 403
    bad = catalog.get("/products/export", headers={**auth("admin"), "Accept": "text/csv"}, params={"sort": "x"})
    assert bad.status_code == 422 and bad.json()["code"] == "validation_error"


def checkout(orders, auth, quantity=1, key=None, who="cliente"):
    headers = {**auth(who), **({"Idempotency-Key": key} if key else {})}
    return orders.post("/orders", headers=headers, json={"items": [{"product_id": COFFEE, "quantity": quantity}]})


def test_checkout_with_idempotency_key(orders, auth, dispatcher):
    first = checkout(orders, auth, key="pedido-abc-123")
    again = checkout(orders, auth, quantity=5, key="pedido-abc-123")
    assert first.status_code == again.status_code == 202
    assert again.json()["id"] == first.json()["id"]
    assert again.headers["idempotent-replayed"] == "true"
    assert again.json()["total_cents"] == 6290
    assert dispatcher.processed == [first.json()["id"]]
    other = checkout(orders, auth, key="pedido-abc-123", who="c1")
    assert other.status_code == 202 and other.json()["id"] != first.json()["id"]
    assert checkout(orders, auth, key="curta").status_code == 422
    assert checkout(orders, auth).json()["id"] not in (first.json()["id"], other.json()["id"])


def test_orders_filters_sort_and_export(orders, auth, dispatcher):
    from argo.orders.models import Order

    a = checkout(orders, auth, quantity=1).json()["id"]
    b = checkout(orders, auth, quantity=3).json()["id"]
    Order.objects.filter(pk=a).update(created_at=utcnow() - timedelta(days=10))
    h = auth("cliente")
    recent = orders.get("/orders", headers=h, params={"date_from": (utcnow() - timedelta(days=2)).date().isoformat()}).json()
    assert [o["id"] for o in recent["items"]] == [b]
    old_day = (utcnow() - timedelta(days=10)).date()
    window = {"date_from": (old_day - timedelta(days=1)).isoformat(), "date_to": (old_day + timedelta(days=1)).isoformat()}
    old = orders.get("/orders", headers=h, params=window)
    assert [o["id"] for o in old.json()["items"]] == [a]
    by_total = orders.get("/orders", headers=h, params={"sort": "total_asc"}).json()
    assert [o["id"] for o in by_total["items"]] == [a, b]
    bad = orders.get("/orders", headers=h, params={"date_from": "2026-05-10", "date_to": "2026-05-01"})
    assert bad.status_code == 422 and "date_to" in bad.json()["fields"]

    data = rows(orders.get("/orders/export", headers=h, params={"sort": "oldest"}))
    assert data[0][0] == "Pedido" and len(data) == 3
    assert data[1][0] == f"AR-{a:06d}" and data[1][4] == "Processando" and data[1][6] == "62,90"
    assert len(rows(orders.get("/orders/export", headers=auth("vendedor2")))) == 1
    assert len(rows(orders.get("/orders/export", headers=auth("admin")))) == 3


def test_stats_compare_with_previous_period(orders, auth, dispatcher):
    from argo.orders.models import Order

    now = checkout(orders, auth, quantity=2).json()["id"]
    before = checkout(orders, auth, quantity=1).json()["id"]
    Order.objects.filter(pk__in=[now, before]).update(status="CONFIRMED")
    Order.objects.filter(pk=before).update(created_at=utcnow() - timedelta(days=10))
    stats = orders.get("/orders/stats", headers=auth("admin"), params={"days": 7}).json()
    assert stats["revenue_cents"] == 2 * 6290
    assert stats["previous"] == {"revenue_cents": 6290, "orders": 1, "average_ticket_cents": 6290}
    seller2 = orders.get("/orders/stats", headers=auth("vendedor2"), params={"days": 7}).json()
    assert seller2["previous"]["revenue_cents"] == 0


def test_status_change_notifies_customer(orders, auth, dispatcher):
    from argo.orders.models import Order

    oid = checkout(orders, auth).json()["id"]
    Order.objects.filter(pk=oid).update(status="CONFIRMED")
    r = orders.patch(f"/orders/{oid}/status", headers=auth("vendedor"), json={"status": "SHIPPED", "note": "BR123BR"})
    assert r.status_code == 200
    assert dispatcher.notified == [(oid, "SHIPPED")]
    orders.patch(f"/orders/{oid}/status", headers=auth("vendedor"), json={"status": "DELIVERED"})
    assert dispatcher.notified[-1] == (oid, "DELIVERED")


def test_recover_lists_stale_orders(orders, auth, dispatcher):
    from argo.orders.models import Order

    stale = checkout(orders, auth).json()["id"]
    fresh = checkout(orders, auth).json()["id"]
    confirmed = checkout(orders, auth).json()["id"]
    ancient = checkout(orders, auth).json()["id"]
    old = utcnow() - timedelta(minutes=30)
    Order.objects.filter(pk=stale).update(created_at=old)
    Order.objects.filter(pk=confirmed).update(status="CONFIRMED", created_at=old, updated_at=old)
    Order.objects.filter(pk=ancient).update(created_at=utcnow() - timedelta(days=3))
    assert orders.post("/internal/orders/recover").status_code == 403
    found = orders.post("/internal/orders/recover", headers=INTERNAL).json()
    assert found == {"pending": [stale], "missing_email": [confirmed], "missing_invoice": [confirmed]}
    assert fresh not in found["pending"]
