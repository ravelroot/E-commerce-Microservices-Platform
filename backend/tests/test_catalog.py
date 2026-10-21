import asyncio
import json

import pytest

from argo.catalog.views import sse_stream
from argo.common.demo import demo_id

INTERNAL = {"X-Internal-Token": "token-interno-de-teste"}
COFFEE = demo_id("p01")
OLIVE = demo_id("p04")
NOTEBOOK = demo_id("p09")


def test_list_search_filter_and_sort(catalog, auth):
    h = auth("cliente")
    r = catalog.get("/products", headers=h, params={"size": 100})
    assert r.status_code == 200
    assert r.json()["total"] == 16
    r = catalog.get("/products", headers=h, params={"q": "grãos"})
    assert {p["sku"] for p in r.json()["items"]} == {"AUR-CAF-01"}
    r = catalog.get("/products", headers=h, params={"category": "Papelaria", "sort": "price_desc"})
    prices = [p["price_cents"] for p in r.json()["items"]]
    assert prices == sorted(prices, reverse=True) and len(prices) == 4
    r = catalog.get("/products", headers=h, params={"low_stock": True, "sort": "stock"})
    assert [p["stock"] for p in r.json()["items"]] == [0, 2, 3, 4]
    r = catalog.get("/products", headers=h, params={"seller_id": demo_id("vendedor2"), "sort": "newest"})
    assert r.json()["total"] == 8


def test_categories_and_detail(catalog, auth):
    h = auth("cliente")
    cats = catalog.get("/products/categories", headers=h).json()
    assert {"name": "Mercearia", "products": 5} in cats
    assert catalog.get(f"/products/{COFFEE}", headers=h).json()["name"].startswith("Café")
    assert catalog.get("/products/nao-existe", headers=h).status_code == 404


def test_customer_cannot_create_products(catalog, auth):
    body = {"sku": "x-1", "name": "Produto", "category": "Casa", "price_cents": 1000}
    assert catalog.post("/products", headers=auth("cliente"), json=body).status_code == 403


def test_seller_creates_product_with_initial_stock(catalog, auth):
    h = auth("vendedor")
    body = {"sku": "aur-new-1", "name": " Xícara  dupla ", "category": "Casa", "price_cents": 3990, "stock": 12}
    r = catalog.post("/products", headers=h, json=body)
    assert r.status_code == 201
    p = r.json()
    assert p["sku"] == "AUR-NEW-1" and p["name"] == "Xícara dupla" and p["stock"] == 12
    assert p["seller_id"] == demo_id("vendedor") and p["seller_name"] == "Loja Aurora"
    moves = catalog.get(f"/products/{p['id']}/movements", headers=h).json()
    assert moves["items"][0]["kind"] == "IN" and moves["items"][0]["reason"] == "Estoque inicial"
    assert catalog.post("/products", headers=h, json=body).status_code == 409
    mine = catalog.get("/products", headers=h, params={"mine": True}).json()
    assert mine["total"] == 9


def test_product_without_initial_stock(catalog, auth):
    body = {"sku": "ADM-1", "name": "Kit", "category": "Casa", "price_cents": 100}
    r = catalog.post("/products", headers=auth("admin"), json=body)
    assert r.json()["stock"] == 0


def test_only_owner_or_admin_can_edit(catalog, auth):
    r = catalog.put(f"/products/{NOTEBOOK}", headers=auth("vendedor"), json={"price_cents": 1})
    assert r.status_code == 403
    r = catalog.put(f"/products/{NOTEBOOK}", headers=auth("vendedor2"), json={"price_cents": 3990, "name": "Caderno  A5"})
    assert r.status_code == 200 and r.json()["price_cents"] == 3990 and r.json()["name"] == "Caderno A5"
    r = catalog.put(f"/products/{NOTEBOOK}", headers=auth("admin"), json={"category": "Escritório"})
    assert r.json()["category"] == "Escritório"


def test_optimistic_version_conflict(catalog, auth):
    h = auth("vendedor")
    version = catalog.get(f"/products/{COFFEE}", headers=h).json()["version"]
    assert catalog.put(f"/products/{COFFEE}", headers=h, json={"price_cents": 7000, "version": version}).status_code == 200
    r = catalog.put(f"/products/{COFFEE}", headers=h, json={"price_cents": 7100, "version": version})
    assert r.status_code == 409 and r.json()["code"] == "version_conflict"


def test_deactivate_hides_from_store(catalog, auth):
    h = auth("vendedor")
    assert catalog.delete(f"/products/{COFFEE}", headers=h).status_code == 204
    assert catalog.get(f"/products/{COFFEE}", headers=auth("cliente")).status_code == 404
    assert catalog.get(f"/products/{COFFEE}", headers=h).json()["active"] is False
    mine = catalog.get("/products", headers=h, params={"mine": True, "include_inactive": True}).json()
    assert mine["total"] == 8
    store = catalog.get("/products", headers=auth("cliente"), params={"include_inactive": True}).json()
    assert store["total"] == 15


def test_stock_adjustments(catalog, auth, bus):
    h = auth("vendedor")
    r = catalog.post(f"/products/{OLIVE}/stock", headers=h, json={"kind": "IN", "quantity": 10, "reason": "Reposição"})
    assert r.json()["stock"] == 14
    r = catalog.post(f"/products/{OLIVE}/stock", headers=h, json={"kind": "OUT", "quantity": 4})
    assert r.json()["stock"] == 10
    r = catalog.post(f"/products/{OLIVE}/stock", headers=h, json={"kind": "COUNT", "quantity": 7})
    assert r.json()["stock"] == 7
    r = catalog.post(f"/products/{OLIVE}/stock", headers=h, json={"kind": "OUT", "quantity": 99})
    assert r.status_code == 409
    r = catalog.post(f"/products/{OLIVE}/stock", headers=h, json={"kind": "IN", "quantity": 0})
    assert r.status_code == 422
    kinds = [m["kind"] for m in catalog.get(f"/products/{OLIVE}/movements", headers=h).json()["items"]]
    assert kinds == ["COUNT", "OUT", "IN", "IN"]
    events = [e for _, e in bus.published]
    assert [e["stock"] for e in events] == [14, 10, 7]
    assert events[-1]["delta"] == -3 and events[-1]["low"] is False


def test_stock_summary_is_scoped(catalog, auth):
    seller = catalog.get("/stock/summary", headers=auth("vendedor")).json()
    admin = catalog.get("/stock/summary", headers=auth("admin")).json()
    assert seller["products"] == 8 and admin["products"] == 16
    assert admin["out_of_stock"] == 1
    assert admin["units"] > seller["units"]
    assert catalog.get("/stock/summary", headers=auth("cliente")).status_code == 403


def test_internal_lookup(catalog):
    r = catalog.post("/internal/products/lookup", headers=INTERNAL, json={"ids": [COFFEE, "x"]})
    assert [p["sku"] for p in r.json()] == ["AUR-CAF-01"]


def test_commit_is_all_or_nothing_and_idempotent(catalog, auth):
    bad = {"order_id": 7, "items": [{"product_id": COFFEE, "quantity": 2}, {"product_id": OLIVE, "quantity": 50}]}
    r = catalog.post("/internal/stock/commit", headers=INTERNAL, json=bad).json()
    assert r["ok"] is False and r["shortages"][0]["available"] == 4
    assert catalog.get(f"/products/{COFFEE}", headers=auth("cliente")).json()["stock"] == 48

    good = {"order_id": 8, "items": [{"product_id": COFFEE, "quantity": 2}, {"product_id": COFFEE, "quantity": 1}]}
    assert catalog.post("/internal/stock/commit", headers=INTERNAL, json=good).json() == {
        "ok": True,
        "already_processed": False,
        "shortages": [],
    }
    again = catalog.post("/internal/stock/commit", headers=INTERNAL, json=good).json()
    assert again["already_processed"] is True
    assert catalog.get(f"/products/{COFFEE}", headers=auth("cliente")).json()["stock"] == 45

    rel = catalog.post("/internal/stock/release", headers=INTERNAL, json={"order_id": 8}).json()
    assert rel == {"released": 1}
    assert catalog.post("/internal/stock/release", headers=INTERNAL, json={"order_id": 8}).json() == {"released": 0}
    assert catalog.post("/internal/stock/release", headers=INTERNAL, json={"order_id": 999}).json() == {"released": 0}
    assert catalog.get(f"/products/{COFFEE}", headers=auth("cliente")).json()["stock"] == 48


def test_commit_rejects_unknown_and_inactive(catalog, auth):
    catalog.delete(f"/products/{COFFEE}", headers=auth("vendedor"))
    body = {"order_id": 9, "items": [{"product_id": COFFEE, "quantity": 1}, {"product_id": "sumiu", "quantity": 1}]}
    r = catalog.post("/internal/stock/commit", headers=INTERNAL, json=body).json()
    assert {s["name"] for s in r["shortages"]} == {"Café especial em grãos 500 g", "Produto removido"}


def test_stream_requires_auth(catalog):
    assert catalog.get("/stock/stream").status_code == 401


async def _events(items):
    for item in items:
        yield item
        await asyncio.sleep(0)


@pytest.mark.nodb
@pytest.mark.anyio
async def test_sse_stream_formats_events():
    chunks = [c async for c in sse_stream(_events([{"stock": 3, "name": "Café"}]))]
    assert chunks[0].startswith("event: ready")
    assert chunks[1].startswith("event: stock")
    assert json.loads(chunks[1].split("data: ")[1]) == {"stock": 3, "name": "Café"}
    assert len(chunks) == 2


@pytest.mark.nodb
@pytest.mark.anyio
async def test_sse_stream_heartbeat_keeps_the_subscription():
    queue: asyncio.Queue = asyncio.Queue()
    closed = []

    async def slow():
        try:
            while True:
                yield await queue.get()
        finally:
            closed.append(True)

    stream = sse_stream(slow(), heartbeat=0.01)
    assert await anext(stream) == "event: ready\ndata: {}\n\n"
    assert await anext(stream) == ": ping\n\n"
    assert await anext(stream) == ": ping\n\n"
    queue.put_nowait({"stock": 1})
    assert (await anext(stream)).startswith("event: stock")
    await stream.aclose()
    assert closed == [True]


def test_stream_rejects_invalid_token(catalog):
    r = catalog.get("/stock/stream", headers={"Authorization": "Bearer x"})
    assert r.status_code == 401 and r.json()["code"] == "unauthorized"
    assert catalog.post("/stock/stream").status_code == 405


def test_validation_messages_in_portuguese(catalog, auth):
    body = {"sku": "x 1", "name": "Kit", "category": "Casa", "price_cents": 0}
    r = catalog.post("/products", headers=auth("vendedor"), json=body)
    assert r.status_code == 422 and r.json()["message"] == "Confira os campos destacados."
    assert r.json()["fields"]["price_cents"] == "Informe um valor maior ou igual a 1."
    assert "sku" in r.json()["fields"]
