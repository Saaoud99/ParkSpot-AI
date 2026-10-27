from tests.conftest import auth, future_window, make_user


async def _host_spot(client, token):
    r = await client.post("/api/v1/spots", headers=auth(token), json={
        "title": "Test Driveway", "address": "1 Main St", "latitude": 37.7749, "longitude": -122.4194,
        "spot_type": "driveway", "is_covered": True, "has_ev_charging": False, "base_price_per_hour": "5.00"})
    assert r.status_code == 201, r.text
    return r.json()


async def test_host_creates_and_search_finds(client):
    host = await make_user(client, "h@test.com", "host")
    spot = await _host_spot(client, host)
    start, end = future_window()
    r = await client.get("/api/v1/spots/search", params={"lat": 37.7749, "lng": -122.4194, "radius_km": 2, "start": start.isoformat(), "end": end.isoformat()})
    assert r.status_code == 200
    ids = [s["id"] for s in r.json()]
    assert spot["id"] in ids
    assert r.json()[0]["distance_km"] < 1


async def test_driver_cannot_create_spot(client):
    driver = await make_user(client, "d@test.com", "driver")
    r = await client.post("/api/v1/spots", headers=auth(driver), json={
        "title": "X", "address": "1 St", "latitude": 37.77, "longitude": -122.41, "spot_type": "driveway", "base_price_per_hour": "5"})
    assert r.status_code == 403
