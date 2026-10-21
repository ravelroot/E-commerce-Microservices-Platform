"""Infraestrutura dos testes (pytest-django).

Os três serviços rodam no mesmo processo, cada um com o seu banco SQLite (argo/settings_test.py).
Cada fixture de serviço é um cliente httpx que chama a aplicação WSGI do Django de verdade, com
middleware, autenticação, roteamento e tratamento de erros, como o gateway faria.
"""

from __future__ import annotations

import itertools
import json
from collections.abc import Iterator

import httpx
import pytest

INTERNAL = "token-interno-de-teste"


def pytest_collection_modifyitems(items):
    for item in items:
        if "nodb" not in item.keywords:
            item.add_marker(pytest.mark.django_db(transaction=True, databases="__all__"))


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def wsgi():
    from argo.wsgi import application

    return application


def client(wsgi, service: str, **headers) -> httpx.Client:
    return httpx.Client(
        transport=httpx.WSGITransport(app=wsgi),
        base_url=f"http://testserver/api/{service}",
        headers=headers,
    )


@pytest.fixture
def bus():
    from argo.common.events import MemoryEventBus, set_bus

    b = MemoryEventBus()
    set_bus(b)
    yield b
    set_bus(None)


@pytest.fixture
def dispatcher():
    from argo.orders.dispatch import RecordingDispatcher, set_dispatcher

    d = RecordingDispatcher()
    set_dispatcher(d)
    yield d
    set_dispatcher(None)


@pytest.fixture(autouse=True)
def seeded(request):
    """Identidade e catálogo começam cada teste com os dados de demonstração (pedidos começam vazios)."""
    if "nodb" in request.keywords:
        yield
        return
    request.getfixturevalue("transactional_db")
    request.getfixturevalue("bus")
    request.getfixturevalue("dispatcher")
    from argo.catalog.seed import seed as seed_catalog
    from argo.identity.seed import seed as seed_identity

    seed_identity()
    seed_catalog()
    yield


def token_for(key: str) -> str:
    from argo.common.demo import demo_id, demo_user
    from argo.common.security import Principal, Role, create_access_token

    u = demo_user(key)
    principal = Principal(id=demo_id(key), role=Role(u["role"]), name=u["name"], email=u["email"])
    return create_access_token(principal)[0]


@pytest.fixture
def auth():
    def _headers(key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token_for(key)}"}

    return _headers


@pytest.fixture
def identity(wsgi) -> Iterator[httpx.Client]:
    with client(wsgi, "identity") as c:
        yield c


@pytest.fixture
def catalog(wsgi) -> Iterator[httpx.Client]:
    with client(wsgi, "catalog") as c:
        yield c


@pytest.fixture
def orders(wsgi, catalog) -> Iterator[httpx.Client]:
    from argo.orders.clients import set_catalog

    set_catalog(client(wsgi, "catalog", **{"X-Internal-Token": INTERNAL}))
    with client(wsgi, "orders") as c:
        yield c
    set_catalog(None)


class FakeBilling:
    """Faz o papel do serviço de faturamento (Java) nos testes do worker."""

    def __init__(self) -> None:
        self.invoices: dict[int, dict] = {}
        self.canceled: list[int] = []
        self.fail_next = 0
        self._seq = itertools.count(1)

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.fail_next:
            self.fail_next -= 1
            return httpx.Response(503)
        if request.headers.get("X-Internal-Token") != INTERNAL:
            return httpx.Response(403)
        path = request.url.path
        if path.endswith("/internal/invoices"):
            body = json.loads(request.content)
            inv = self.invoices.get(body["orderId"])
            if inv is None:
                inv = {"number": f"NF-2026-{next(self._seq):06d}", "orderId": body["orderId"], "body": body}
                self.invoices[body["orderId"]] = inv
            return httpx.Response(201, json=inv)
        if path.endswith("/cancel"):
            order_id = int(path.split("/")[-2])
            if order_id not in self.invoices:
                return httpx.Response(404, json={"code": "not_found"})
            self.canceled.append(order_id)
            return httpx.Response(200, json={"status": "CANCELED"})
        return httpx.Response(404)


@pytest.fixture
def worker(wsgi, orders, catalog, dispatcher):
    from argo.worker import tasks
    from argo.worker.mailer import DjangoMailer

    billing = FakeBilling()
    mailer = DjangoMailer()
    tasks.services.configure(
        catalog=client(wsgi, "catalog", **{"X-Internal-Token": INTERNAL}),
        orders=client(wsgi, "orders", **{"X-Internal-Token": INTERNAL}),
        billing=httpx.Client(
            base_url="http://billing/api/billing",
            transport=httpx.MockTransport(billing.handler),
            headers={"X-Internal-Token": INTERNAL},
        ),
        mailer=mailer,
    )

    class Ctx:
        pass

    ctx = Ctx()
    ctx.billing, ctx.mailer, ctx.dispatcher = billing, mailer, dispatcher

    def drain():
        while dispatcher.processed or dispatcher.canceled:
            if dispatcher.processed:
                tasks.process_order.apply(args=[dispatcher.processed.pop(0)]).get()
            if dispatcher.canceled:
                tasks.cancel_order.apply(args=[dispatcher.canceled.pop(0)]).get()

    ctx.drain = drain
    yield ctx
    tasks.services.configure()
