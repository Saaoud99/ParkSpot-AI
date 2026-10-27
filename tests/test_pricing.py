from datetime import timedelta

from tests.conftest import auth, future_window, make_user


async def _setup_spot(client):
    host = await make_user(client, "hp@test.com", "host")
    r = await client.post("/api/v1/spots", headers=auth(host), json={
        "title": "Priced", "address": "1 St", "latitude": 37.7749, "longitude": -122.4194,
        "spot_type": "garage", "is_covered": True, "has_ev_charging": False, "base_price_per_hour": "10.00"})
    return r.json()["id"]


async def test_quote_math(client):
    spot_id = await _setup_spot(client)
    start, end = future_window()
    r = await client.get("/api/v1/pricing/quote", params={"spot_id": spot_id, "start": start.isoformat(), "end": end.isoformat()})
    assert r.status_code == 200, r.text
    q = r.json()
    assert float(q["hours"]) == 2.0
    assert float(q["base_price"]) == 20.0
    assert float(q["total"]) == 22.40  # 20 * 1.0 + 12% fee


async def test_quarter_hour_rounding(client):
    spot_id = await _setup_spot(client)
    start, _ = future_window()
    end = start + timedelta(minutes=70)
    r = await client.get("/api/v1/pricing/quote", params={"spot_id": spot_id, "start": start.isoformat(), "end": end.isoformat()})
    assert float(r.json()["hours"]) == 1.25
