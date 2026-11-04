from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from argo.common.demo import DEMO_PASSWORD, demo_id
from argo.common.security import decode_access_token
from argo.common.utils import utcnow

INTERNAL = {"X-Internal-Token": "token-interno-de-teste"}


def login(client, email="cliente@argo.dev", password=DEMO_PASSWORD, agent="Navegador A"):
    headers = {"User-Agent": agent, "X-Real-IP": "10.1.2.3"}
    return client.post("/auth/login", json={"email": email, "password": password}, headers=headers)


def bearer(pair):
    return {"Authorization": f"Bearer {pair['access_token']}"}


def test_sessions_are_listed_and_marked(identity):
    first = login(identity, agent="Firefox no Linux").json()
    second = login(identity, agent="Chrome no Windows").json()
    assert decode_access_token(first["access_token"]).session_id
    rows = identity.get("/auth/sessions", headers=bearer(first)).json()
    assert len(rows) == 2
    current = [r for r in rows if r["current"]]
    assert len(current) == 1 and current[0]["user_agent"] == "Firefox no Linux"
    assert current[0]["ip_address"] == "10.1.2.3"
    renewed = identity.post(
        "/auth/refresh", json={"refresh_token": second["refresh_token"]}, headers={"User-Agent": "Chrome no Windows"}
    ).json()
    rows = identity.get("/auth/sessions", headers=bearer(renewed)).json()
    assert len(rows) == 2
    mine = next(r for r in rows if r["current"])
    assert mine["user_agent"] == "Chrome no Windows"
    assert mine["started_at"] <= mine["last_used_at"]


def test_revoke_one_session_and_the_others(identity):
    a = login(identity).json()
    b = login(identity).json()
    c = login(identity).json()
    sid_b = decode_access_token(b["access_token"]).session_id
    assert identity.delete(f"/auth/sessions/{sid_b}", headers=bearer(a)).status_code == 204
    assert identity.post("/auth/refresh", json={"refresh_token": b["refresh_token"]}).status_code == 401
    assert identity.delete("/auth/sessions/nao-existe", headers=bearer(a)).status_code == 404

    seller = login(identity, "vendedor@argo.dev").json()
    sid_a = decode_access_token(a["access_token"]).session_id
    assert identity.delete(f"/auth/sessions/{sid_a}", headers=bearer(seller)).status_code == 404

    r = identity.post("/auth/sessions/revoke-others", headers=bearer(a))
    assert r.json() == {"revoked": 1}
    assert identity.post("/auth/refresh", json={"refresh_token": c["refresh_token"]}).status_code == 401
    assert identity.post("/auth/refresh", json={"refresh_token": a["refresh_token"]}).status_code == 200


def test_profile_name_can_be_changed(identity):
    pair = login(identity).json()
    r = identity.patch("/auth/me", headers=bearer(pair), json={"name": "  Cliente   Nova  "})
    assert r.status_code == 200 and r.json()["name"] == "Cliente Nova"
    assert identity.patch("/auth/me", headers=bearer(pair), json={"name": "x"}).status_code == 422
    renewed = identity.post("/auth/refresh", json={"refresh_token": pair["refresh_token"]}).json()
    assert decode_access_token(renewed["access_token"]).name == "Cliente Nova"


def test_admin_resets_password_and_unlocks(identity):
    admin = login(identity, "admin@argo.dev").json()
    customer = login(identity).json()
    for _ in range(5):
        login(identity, password="Errada123")
    assert login(identity).status_code == 423
    locked = identity.get("/users", headers=bearer(admin), params={"locked": "true"}).json()
    assert [u["email"] for u in locked["items"]] == ["cliente@argo.dev"]
    assert locked["items"][0]["locked_until"]

    uid = demo_id("cliente")
    r = identity.post(f"/users/{uid}/unlock", headers=bearer(admin))
    assert r.status_code == 200 and r.json()["locked_until"] is None
    assert login(identity).status_code == 200

    assert identity.post(f"/users/{uid}/password", headers=bearer(admin), json={"password": "curta"}).status_code == 422
    r = identity.post(f"/users/{uid}/password", headers=bearer(admin), json={"password": "Trocada123"})
    assert r.status_code == 200
    assert identity.post("/auth/refresh", json={"refresh_token": customer["refresh_token"]}).status_code == 401
    assert login(identity, password="Trocada123").status_code == 200
    denied = identity.post(f"/users/{uid}/password", headers=bearer(customer), json={"password": "Trocada123"})
    assert denied.status_code in (401, 403)
    assert identity.post("/users/nao-existe/unlock", headers=bearer(admin)).status_code == 404


def test_users_filter_by_situation(identity):
    admin = login(identity, "admin@argo.dev").json()
    uid = demo_id("c1")
    identity.patch(f"/users/{uid}", headers=bearer(admin), json={"active": False})
    inactive = identity.get("/users", headers=bearer(admin), params={"active": "false"}).json()
    assert [u["id"] for u in inactive["items"]] == [uid]
    active = identity.get("/users", headers=bearer(admin), params={"active": "true", "size": 100}).json()
    assert uid not in {u["id"] for u in active["items"]}
    assert identity.get("/users", headers=bearer(admin), params={"role": "ROOT"}).status_code == 422


def test_cleanup_removes_old_tokens(identity):
    from argo.identity.models import RefreshToken

    pair = login(identity).json()
    identity.post("/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    old = utcnow() - timedelta(days=60)
    RefreshToken.objects.filter(revoked_at__isnull=False).update(revoked_at=old)
    assert identity.post("/internal/tokens/cleanup").status_code == 403
    r = identity.post("/internal/tokens/cleanup", headers=INTERNAL)
    assert r.json() == {"deleted": 1}
    assert RefreshToken.objects.count() == 1

    RefreshToken.objects.update(expires_at=old)
    out = StringIO()
    call_command("cleanup_tokens", stdout=out)
    assert "1 refresh token(s) removido(s)" in out.getvalue()


def test_create_admin_command(identity):
    out = StringIO()
    call_command("create_admin", email="nova.admin@argo.dev", name="Nova Admin", password="Admin12345", no_input=True, stdout=out)
    assert "criado" in out.getvalue()
    assert login(identity, "nova.admin@argo.dev", "Admin12345").json()["user"]["role"] == "ADMIN"

    call_command("create_admin", email="vendedor@argo.dev", no_input=True, stdout=out)
    assert login(identity, "vendedor@argo.dev").json()["user"]["role"] == "ADMIN"

    call_command("create_admin", email="atelie@argo.dev", password="Outra1234", no_input=True, if_missing=True, stdout=out)
    assert "já existe" in out.getvalue()
    assert login(identity, "atelie@argo.dev").json()["user"]["role"] == "SELLER"

    call_command("create_admin", email="atelie@argo.dev", password="Outra1234", reset_password=True, no_input=True, stdout=out)
    assert login(identity, "atelie@argo.dev", "Outra1234").status_code == 200

    with pytest.raises(CommandError):
        call_command("create_admin", email="sem.senha@argo.dev", no_input=True, stdout=out)
    with pytest.raises(CommandError):
        call_command("create_admin", email="fraca@argo.dev", password="fraca", no_input=True, stdout=out)
    with pytest.raises(CommandError):
        call_command("create_admin", no_input=True, stdout=out)
