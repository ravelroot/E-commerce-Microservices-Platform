from datetime import timedelta

import jwt
import pytest

from argo.common.errors import ApiError
from argo.common.events import MemoryEventBus
from argo.common.pagination import page_bounds, pages
from argo.common.security import Principal, Role, create_access_token, decode_access_token
from argo.common.utils import utcnow


def principal(role=Role.CUSTOMER) -> Principal:
    return Principal(id="u-1", role=role, name="Teste", email="teste@argo.dev")


@pytest.mark.nodb
def test_access_token_round_trip(settings):
    token, ttl = create_access_token(principal(Role.SELLER))
    assert ttl == settings.ARGO_ACCESS_TOKEN_MINUTES * 60
    decoded = decode_access_token(token)
    assert decoded == principal(Role.SELLER)
    assert not decoded.is_admin


@pytest.mark.nodb
def test_token_with_wrong_secret_is_rejected():
    token, _ = create_access_token(principal())
    with pytest.raises(ApiError) as exc:
        decode_access_token(token, secret="outro-segredo-qualquer-com-tamanho-suficiente")
    assert exc.value.status == 401


@pytest.mark.nodb
def test_expired_token_is_rejected():
    token, _ = create_access_token(principal(), minutes=-1)
    with pytest.raises(ApiError) as exc:
        decode_access_token(token)
    assert "expirou" in exc.value.message


@pytest.mark.nodb
@pytest.mark.parametrize(
    "claims",
    [
        {"type": "refresh", "role": "ADMIN"},
        {"type": "access", "role": "ROOT"},
    ],
)
def test_token_type_and_role_are_checked(settings, claims):
    now = utcnow()
    token = jwt.encode(
        {
            "iss": settings.ARGO_JWT_ISSUER,
            "sub": "x",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            **claims,
        },
        settings.ARGO_JWT_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(ApiError):
        decode_access_token(token)


def test_missing_and_malformed_bearer(catalog):
    r = catalog.get("/products")
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"
    r = catalog.get("/products", headers={"Authorization": "Bearer nao-e-um-jwt"})
    assert r.status_code == 401
    assert r.json()["code"] == "unauthorized"
    assert r.headers["www-authenticate"] == "Bearer"


def test_internal_routes_require_shared_secret(catalog):
    r = catalog.post("/internal/products/lookup", json={"ids": ["x"]})
    assert r.status_code == 403
    r = catalog.post("/internal/products/lookup", json={"ids": ["x"]}, headers={"X-Internal-Token": "errado"})
    assert r.status_code == 403


def test_health_and_request_id(catalog):
    r = catalog.get("/health", headers={"X-Request-ID": "abc123"})
    assert r.json() == {"status": "ok", "service": "catalog", "version": "1.1.0"}
    assert r.headers["x-request-id"] == "abc123"


def test_unknown_route_uses_standard_error(catalog):
    r = catalog.get("/nao-existe")
    assert r.status_code == 404
    assert set(r.json()) == {"code", "message", "fields"}


def test_invalid_json_and_wrong_method(catalog, auth):
    r = catalog.post("/products", headers={**auth("vendedor"), "Content-Type": "application/json"}, content=b"{x")
    assert r.status_code == 422 and r.json()["code"] == "validation_error"
    r = catalog.patch("/products", headers=auth("vendedor"), json={})
    assert r.status_code == 405 and r.json()["code"] == "method_not_allowed"


def test_openapi_documents_every_service(identity, catalog, orders):
    for client, path in ((identity, "/auth/login"), (catalog, "/stock/stream"), (orders, "/orders")):
        doc = client.get("/openapi.json").json()
        assert doc["openapi"].startswith("3.")
        assert path in doc["paths"]
        assert "bearer" in doc["components"]["securitySchemes"]


@pytest.mark.nodb
def test_page_helpers():
    assert page_bounds(0, 500) == (1, 100)
    assert pages(21, 10) == 3


@pytest.mark.nodb
@pytest.mark.anyio
async def test_memory_bus_delivers_to_subscribers():
    bus = MemoryEventBus()
    sub = bus.subscribe("c")
    import asyncio

    task = asyncio.ensure_future(sub.__anext__())
    await asyncio.sleep(0)
    bus.publish("c", {"a": 1})
    assert await asyncio.wait_for(task, 1) == {"a": 1}
    await sub.aclose()
    assert bus.published == [("c", {"a": 1})]
