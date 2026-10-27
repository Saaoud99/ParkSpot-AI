from tests.conftest import auth, make_user


async def test_register_login_me(client):
    token = await make_user(client, "a@test.com")
    r = await client.get("/api/v1/auth/me", headers=auth(token))
    assert r.status_code == 200
    assert r.json()["email"] == "a@test.com"


async def test_register_admin_rejected(client):
    r = await client.post("/api/v1/auth/register", json={"email": "x@test.com", "password": "password123", "full_name": "X", "role": "admin"})
    assert r.status_code == 422


async def test_duplicate_email_409(client):
    await make_user(client, "dup@test.com")
    r = await client.post("/api/v1/auth/register", json={"email": "dup@test.com", "password": "password123", "full_name": "D", "role": "driver"})
    assert r.status_code == 409
    assert r.json()["code"] == "email_taken"


async def test_login_bad_password(client):
    await make_user(client, "b@test.com")
    r = await client.post("/api/v1/auth/login", json={"email": "b@test.com", "password": "wrongpass1"})
    assert r.status_code == 401
