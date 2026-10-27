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


async def test_authorized_capacity_allows_up_to_limit(client):
    # Facility with 10 physical spaces but only 2 authorized for ParkSpot:
    # two overlapping holds succeed, the third is rejected (no overbooking).
    host = await make_user(client, "hc@test.com", "host")
    r = await client.post("/api/v1/spots", headers=auth(host), json={
        "title": "Garage", "address": "2 St", "latitude": 37.7749, "longitude": -122.4194,
        "spot_type": "garage", "base_price_per_hour": "5.00", "total_capacity": 10, "authorized_capacity": 2})
    assert r.status_code == 201, r.text
    spot_id = r.json()["id"]
    start, end = future_window()
    drivers = []
    for i in range(3):
        d = await make_user(client, f"cap{i}@test.com", "driver")
        await client.post("/api/v1/vehicles", headers=auth(d), json={"plate": f"CAP{i}123"})
        drivers.append(d)
    for d in drivers[:2]:
        r = await client.post("/api/v1/bookings/hold", headers=auth(d), json={"spot_id": spot_id, "start": iso_utc(start), "end": iso_utc(end)})
        assert r.status_code == 201, r.text
    r = await client.post("/api/v1/bookings/hold", headers=auth(drivers[2]), json={"spot_id": spot_id, "start": iso_utc(start), "end": iso_utc(end)})
    assert r.status_code == 409
    assert r.json()["code"] == "spot_unavailable"
    # Search honestly reports zero ParkSpot spaces left for that window.
    r = await client.get("/api/v1/spots/search", params={"lat": 37.7749, "lng": -122.4194, "radius_km": 2, "start": iso_utc(start), "end": iso_utc(end)})
    assert spot_id not in [s["id"] for s in r.json()]


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
