from datetime import timedelta

from app.vision.plates import normalize_plate, plates_match
from tests.conftest import auth, iso_utc, make_user


def test_normalize_and_match():
    assert normalize_plate(" demo-1234 ") == "DEMO1234"
    assert plates_match("DEMO1234", "DEM01234")  # O->0 confusion, distance <=1 path
    assert plates_match("ABC123", "ABC123")
    assert not plates_match("ABC123", "XYZ999")


async def test_simulated_arrival_grants(client):
    host = await make_user(client, "vh@test.com", "host")
    driver = await make_user(client, "vd@test.com", "driver")
    await client.post("/api/v1/vehicles", headers=auth(driver), json={"plate": "DEMO1234"})
    r = await client.post("/api/v1/spots", headers=auth(host), json={
        "title": "Cam Spot", "address": "1 St", "latitude": 37.7749, "longitude": -122.4194,
        "spot_type": "driveway", "base_price_per_hour": "5.00"})
    spot_id = r.json()["id"]
    # Create camera directly in DB (no public camera-create endpoint in spec).
    from app.db.models.camera import Camera
    from tests.conftest import TestSession

    async with TestSession() as db:
        db.add(Camera(id="cam-001", spot_id=spot_id))
        await db.commit()
    from app.utils.timeutil import utcnow

    from datetime import UTC

    start = (utcnow() - timedelta(minutes=1)).astimezone(UTC)
    end = (utcnow() + timedelta(hours=2)).astimezone(UTC)
    r = await client.post("/api/v1/bookings/hold", headers=auth(driver), json={"spot_id": spot_id, "start": iso_utc(start), "end": iso_utc(end)})
    assert r.status_code == 201, r.text
    bid = r.json()["id"]
    r = await client.post(f"/api/v1/bookings/{bid}/confirm", headers=auth(driver), json={"payment_method": "mock_card"})
    assert r.status_code == 200, r.text
    r = await client.post("/api/v1/vision/simulate", headers=auth(host), json={"camera_id": "cam-001", "event": "arrival", "plate": "DEMO1234"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["decision"] == "granted", body
    assert body["spot_status"] == "occupied"
    assert body["matched_booking_id"] == bid
    r = await client.get(f"/api/v1/bookings/{bid}", headers=auth(driver))
    assert r.json()["status"] == "active"
