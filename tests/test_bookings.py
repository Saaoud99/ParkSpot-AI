from tests.conftest import auth, future_window, iso_utc, make_user


async def _booking_setup(client):
    host = await make_user(client, "hb@test.com", "host")
    driver = await make_user(client, "db@test.com", "driver")
    r = await client.post("/api/v1/vehicles", headers=auth(driver), json={"plate": "demo1234"})
    assert r.status_code == 201, r.text
    r = await client.post("/api/v1/spots", headers=auth(host), json={
        "title": "Bookable", "address": "1 St", "latitude": 37.7749, "longitude": -122.4194,
        "spot_type": "driveway", "is_covered": False, "has_ev_charging": False, "base_price_per_hour": "5.00"})
    spot_id = r.json()["id"]
    return driver, spot_id


async def test_hold_confirm_qr(client):
    driver, spot_id = await _booking_setup(client)
    start, end = future_window()
    r = await client.post("/api/v1/bookings/hold", headers=auth(driver), json={"spot_id": spot_id, "start": iso_utc(start), "end": iso_utc(end)})
    assert r.status_code == 201, r.text
    bid = r.json()["id"]
    assert r.json()["status"] == "held"
    r = await client.post(f"/api/v1/bookings/{bid}/confirm", headers=auth(driver), json={"payment_method": "mock_card"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "confirmed"
    assert r.json()["qr_url"]
    r = await client.get(f"/api/v1/bookings/{bid}/qr", headers=auth(driver))
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/png")


async def test_overlap_409(client):
    driver, spot_id = await _booking_setup(client)
    start, end = future_window()
    r = await client.post("/api/v1/bookings/hold", headers=auth(driver), json={"spot_id": spot_id, "start": iso_utc(start), "end": iso_utc(end)})
    assert r.status_code == 201
    r = await client.post("/api/v1/bookings/hold", headers=auth(driver), json={"spot_id": spot_id, "start": iso_utc(start), "end": iso_utc(end)})
    assert r.status_code == 409
    assert r.json()["code"] == "spot_unavailable"


async def test_no_vehicle_422(client):
    host = await make_user(client, "hv@test.com", "host")
    driver = await make_user(client, "nv@test.com", "driver")
    r = await client.post("/api/v1/spots", headers=auth(host), json={
        "title": "S", "address": "1 St", "latitude": 37.7749, "longitude": -122.4194,
        "spot_type": "driveway", "base_price_per_hour": "5.00"})
    start, end = future_window()
    r = await client.post("/api/v1/bookings/hold", headers=auth(driver), json={"spot_id": r.json()["id"], "start": iso_utc(start), "end": iso_utc(end)})
    assert r.status_code == 422
    assert r.json()["code"] == "no_vehicle"
