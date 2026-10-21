from argo.common.demo import DEMO_PASSWORD


def login(client, email="cliente@argo.dev", password=DEMO_PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


def bearer(pair):
    return {"Authorization": f"Bearer {pair['access_token']}"}


def test_login_returns_token_pair(identity):
    r = login(identity)
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 900
    assert body["user"]["role"] == "CUSTOMER"
    assert "password_hash" not in body["user"]
    me = identity.get("/auth/me", headers=bearer(body))
    assert me.json()["email"] == "cliente@argo.dev"


def test_login_is_case_insensitive_and_generic_on_error(identity):
    assert login(identity, "CLIENTE@argo.dev").status_code == 200
    wrong = login(identity, password="Errada123")
    unknown = login(identity, "ninguem@argo.dev")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["message"] == unknown.json()["message"] == "E-mail ou senha incorretos."


def test_five_wrong_passwords_lock_the_account(identity):
    for _ in range(5):
        assert login(identity, password="Errada123").status_code == 401
    r = login(identity)
    assert r.status_code == 423
    assert r.json()["code"] == "locked"


def test_register_customer_and_seller(identity):
    r = identity.post(
        "/auth/register", json={"name": "  Nova   Loja ", "email": "nova@argo.dev", "password": "Senha1234", "role": "SELLER"}
    )
    assert r.status_code == 201
    assert r.json()["user"]["name"] == "Nova Loja"
    assert r.json()["user"]["role"] == "SELLER"
    dup = identity.post("/auth/register", json={"name": "Outra", "email": "NOVA@argo.dev", "password": "Senha1234"})
    assert dup.status_code == 409


def test_register_cannot_create_admin_and_checks_password(identity):
    r = identity.post("/auth/register", json={"name": "Hacker", "email": "h@argo.dev", "password": "Senha1234", "role": "ADMIN"})
    assert r.status_code == 422
    r = identity.post("/auth/register", json={"name": "Fraca", "email": "f@argo.dev", "password": "abc"})
    assert r.status_code == 422
    assert "password" in r.json()["fields"]


def test_refresh_rotates_and_detects_reuse(identity):
    first = login(identity).json()
    second = identity.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert second.status_code == 200
    second = second.json()
    assert second["refresh_token"] != first["refresh_token"]

    reuse = identity.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert reuse.status_code == 401
    assert identity.post("/auth/refresh", json={"refresh_token": second["refresh_token"]}).status_code == 401


def test_refresh_with_unknown_token(identity):
    assert identity.post("/auth/refresh", json={"refresh_token": "x" * 40}).status_code == 401


def test_logout_revokes_refresh(identity):
    pair = login(identity).json()
    assert identity.post("/auth/logout", json={"refresh_token": pair["refresh_token"]}).status_code == 204
    assert identity.post("/auth/refresh", json={"refresh_token": pair["refresh_token"]}).status_code == 401


def test_change_password(identity):
    pair = login(identity).json()
    bad = identity.put("/auth/me/password", headers=bearer(pair), json={"current_password": "x", "new_password": "NovaSenha1"})
    assert bad.status_code == 400
    ok = identity.put(
        "/auth/me/password", headers=bearer(pair), json={"current_password": DEMO_PASSWORD, "new_password": "NovaSenha1"}
    )
    assert ok.status_code == 204
    assert login(identity).status_code == 401
    assert login(identity, password="NovaSenha1").status_code == 200

    assert identity.post("/auth/refresh", json={"refresh_token": pair["refresh_token"]}).status_code == 401


def test_users_admin_only(identity):
    customer = login(identity).json()
    assert identity.get("/users", headers=bearer(customer)).status_code == 403
    admin = login(identity, "admin@argo.dev").json()
    r = identity.get("/users", headers=bearer(admin), params={"role": "SELLER"})
    assert r.status_code == 200
    assert {u["email"] for u in r.json()["items"]} == {"vendedor@argo.dev", "atelie@argo.dev"}
    r = identity.get("/users", headers=bearer(admin), params={"q": "aurora"})
    assert r.json()["total"] == 1


def test_admin_creates_promotes_and_blocks(identity):
    admin = login(identity, "admin@argo.dev").json()
    h = bearer(admin)
    r = identity.post(
        "/users", headers=h, json={"name": "Gerente", "email": "gerente@argo.dev", "password": "Gerente123", "role": "ADMIN"}
    )
    assert r.status_code == 201
    customer_id = login(identity).json()["user"]["id"]
    r = identity.patch(f"/users/{customer_id}", headers=h, json={"role": "SELLER", "name": "Cliente  Promovido"})
    assert r.json()["role"] == "SELLER" and r.json()["name"] == "Cliente Promovido"
    pair = login(identity).json()
    identity.patch(f"/users/{customer_id}", headers=h, json={"active": False})
    assert login(identity).status_code == 403
    assert identity.post("/auth/refresh", json={"refresh_token": pair["refresh_token"]}).status_code == 401
    assert identity.patch("/users/nao-existe", headers=h, json={"active": False}).status_code == 404


def test_admin_cannot_lock_himself_out(identity):
    admin = login(identity, "admin@argo.dev").json()
    r = identity.patch(f"/users/{admin['user']['id']}", headers=bearer(admin), json={"active": False})
    assert r.status_code == 400
