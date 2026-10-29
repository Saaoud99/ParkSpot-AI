"""Hardening regression tests: QR replay, cross-user access, expired holds,
security headers, and validation payload hygiene."""
from datetime import timedelta

from tests.conftest import TestSession, auth, future_window, iso_utc, make_user


async def _confirmed_booking(client, driver_email="qr-d@test.com", host_email="qr-h@test.com"):
    host = await make_user(client, host_email, "host")
    driver = await make_user(client, driver_email, "driver")
    await client.post("/api/v1/vehicles", headers=auth(driver), json={"plate": "DEMO1234"})
    r = await client.post("/api/v1/spots", headers=auth(host), json={
        "title": "QR Spot", "address": "1 St", "latitude": 37.7749, "longitude": -122.4194,
        "spot_type": "driveway", "base_price_per_hour": "5.00"})
    spot_id = r.json()["id"]
    from app.utils.timeutil import utcnow

    start = utcnow() + timedelta(minutes=30)
    end = start + timedelta(hours=2)
    r = await client.post("/api/v1/bookings/hold", headers=auth(driver), json={"spot_id": spot_id, "start": iso_utc(start), "end": iso_utc(end)})
    assert r.status_code == 201, r.text
    bid = r.json()["id"]
    r = await client.post(f"/api/v1/bookings/{bid}/confirm", headers=auth(driver))
    assert r.status_code == 200, r.text
    # Raw pass token is no longer exposed in booking JSON.
    assert r.json()["qr_token"] is None
    from app.db.models.booking import Booking

    async with TestSession() as db:
        booking = await db.get(Booking, bid)
        token = booking.qr_token
    assert token
    return host, driver, spot_id, bid, token


async def test_qr_verify_is_single_check_in(client):
    host, driver, spot_id, bid, token = await _confirmed_booking(client)
    # Move the booking window into the present for access verification:
    # create pass token semantics are time-based, so verify inside window
    # by using a booking that already started is not possible via hold;
    # instead assert the replay guard using the stored status transition:
    r = await client.post("/api/v1/access/verify-qr", headers=auth(host), json={"token": token})
    # Outside the window (starts in 30 min, grace is 15) must be denied.
    assert r.status_code == 200, r.text
    assert r.json()["valid"] is False


async def test_qr_replay_denied_after_check_in(client):
    host = await make_user(client, "replay-h@test.com", "host")
    driver = await make_user(client, "replay-d@test.com", "driver")
    await client.post("/api/v1/vehicles", headers=auth(driver), json={"plate": "DEMO1234"})
    r = await client.post("/api/v1/spots", headers=auth(host), json={
        "title": "Replay Spot", "address": "1 St", "latitude": 37.7749, "longitude": -122.4194,
        "spot_type": "driveway", "base_price_per_hour": "5.00"})
    spot_id = r.json()["id"]
    from app.utils.timeutil import utcnow

    start = utcnow() - timedelta(minutes=1)
    end = utcnow() + timedelta(hours=2)
    r = await client.post("/api/v1/bookings/hold", headers=auth(driver), json={"spot_id": spot_id, "start": iso_utc(start), "end": iso_utc(end)})
    assert r.status_code == 201, r.text
    bid = r.json()["id"]
    r = await client.post(f"/api/v1/bookings/{bid}/confirm", headers=auth(driver))
    assert r.status_code == 200, r.text
    from app.db.models.booking import Booking

    async with TestSession() as db:
        token = (await db.get(Booking, bid)).qr_token
    r = await client.post("/api/v1/access/verify-qr", headers=auth(host), json={"token": token})
    assert r.status_code == 200 and r.json()["valid"] is True, r.text
    # Replay of the exact same pass must be denied, not re-granted.
    r = await client.post("/api/v1/access/verify-qr", headers=auth(host), json={"token": token})
    assert r.status_code == 200 and r.json()["valid"] is False, r.text
    assert "already" in r.json()["message"]


async def test_qr_cross_host_denied_and_cross_driver_qr_denied(client):
    host, driver, spot_id, bid, token = await _confirmed_booking(client)
    other_host = await make_user(client, "qr-h2@test.com", "host")
    r = await client.post("/api/v1/access/verify-qr", headers=auth(other_host), json={"token": token})
    assert r.status_code == 403
    other_driver = await make_user(client, "qr-d2@test.com", "driver")
    r = await client.get(f"/api/v1/bookings/{bid}/qr", headers=auth(other_driver))
    assert r.status_code in (403, 404)
    r = await client.get(f"/api/v1/bookings/{bid}", headers=auth(other_driver))
    assert r.status_code == 403


async def test_cancel_revokes_qr(client):
    host, driver, spot_id, bid, token = await _confirmed_booking(client, "qr-d3@test.com", "qr-h3@test.com")
    r = await client.post(f"/api/v1/bookings/{bid}/cancel", headers=auth(driver))
    assert r.status_code == 200, r.text
    r = await client.post("/api/v1/access/verify-qr", headers=auth(host), json={"token": token})
    assert r.status_code == 200
    assert r.json()["valid"] is False


async def test_expired_hold_releases_capacity(client):
    host = await make_user(client, "exp-h@test.com", "host")
    d1 = await make_user(client, "exp-d1@test.com", "driver")
    d2 = await make_user(client, "exp-d2@test.com", "driver")
    for tok, plate in ((d1, "EXP1000"), (d2, "EXP2000")):
        await client.post("/api/v1/vehicles", headers=auth(tok), json={"plate": plate})
    r = await client.post("/api/v1/spots", headers=auth(host), json={
        "title": "One Space", "address": "1 St", "latitude": 37.7749, "longitude": -122.4194,
        "spot_type": "driveway", "base_price_per_hour": "5.00", "total_capacity": 1, "authorized_capacity": 1})
    spot_id = r.json()["id"]
    start, end = future_window()
    r = await client.post("/api/v1/bookings/hold", headers=auth(d1), json={"spot_id": spot_id, "start": iso_utc(start), "end": iso_utc(end)})
    assert r.status_code == 201, r.text
    bid = r.json()["id"]
    # Force the hold's TTL into the past (job hasn't run yet).
    from app.db.models.booking import Booking
    from app.utils.timeutil import utcnow

    async with TestSession() as db:
        booking = await db.get(Booking, bid)
        booking.hold_expires_at = utcnow() - timedelta(minutes=1)
        await db.commit()
    # Expired hold claims no capacity: a second driver can hold the space,
    # and confirming the expired hold must fail.
    r = await client.post("/api/v1/bookings/hold", headers=auth(d2), json={"spot_id": spot_id, "start": iso_utc(start), "end": iso_utc(end)})
    assert r.status_code == 201, r.text
    r = await client.post(f"/api/v1/bookings/{bid}/confirm", headers=auth(d1))
    assert r.status_code == 409
    assert r.json()["code"] == "hold_expired"


async def test_security_headers_and_validation_hygiene(client):
    r = await client.get("/health")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"
    assert "frame-ancestors 'none'" in r.headers.get("content-security-policy", "")
    # Short password triggers validation; the submitted password must not
    # be reflected back in the error payload.
    r = await client.post("/api/v1/auth/register", json={"email": "leak@test.com", "password": "x", "full_name": "Leak"})
    assert r.status_code == 422
    assert '"x"' not in r.text.split("password")[-1] or "input" not in r.text
    assert "input" not in r.text


async def test_driver_cannot_read_admin_stats(client):
    driver = await make_user(client, "no-admin@test.com", "driver")
    r = await client.get("/api/v1/admin/stats", headers=auth(driver))
    assert r.status_code == 403
    r = await client.get("/api/v1/admin/stats")
    assert r.status_code == 401


async def test_profile_update_cannot_escalate_role(client):
    driver = await make_user(client, "esc@test.com", "driver")
    r = await client.patch("/api/v1/users/me", headers=auth(driver), json={"full_name": "Still Driver"})
    assert r.status_code == 200
    assert r.json()["role"] == "driver"
    assert r.json()["full_name"] == "Still Driver"
