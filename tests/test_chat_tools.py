from tests.conftest import auth, future_window, make_user


async def test_chat_degraded_without_llama(client, monkeypatch):
    # No LLAMA_API_KEY in test env -> agent call fails -> degraded friendly reply, still 200.
    monkeypatch.setenv("LLAMA_API_KEY", "")
    driver = await make_user(client, "c@test.com", "driver")
    r = await client.post("/api/v1/chat", headers=auth(driver), json={"message": "find parking near downtown"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "session_id" in body
    assert isinstance(body["reply"], str) and body["reply"]


async def test_tool_search_direct(client):
    host = await make_user(client, "ct@test.com", "host")
    await client.post("/api/v1/spots", headers=auth(host), json={
        "title": "Chat Spot", "address": "1 St", "latitude": 37.7749, "longitude": -122.4194,
        "spot_type": "driveway", "is_covered": True, "has_ev_charging": False, "base_price_per_hour": "5.00"})
    # Exercise execute_tool via API-level search instead of DB-bound context (covered by test_spots).
    start, end = future_window()
    r = await client.get("/api/v1/spots/search", params={"lat": 37.7749, "lng": -122.4194, "start": start.isoformat(), "end": end.isoformat(), "covered": True})
    assert r.status_code == 200
    assert any(s["title"] == "Chat Spot" for s in r.json())
