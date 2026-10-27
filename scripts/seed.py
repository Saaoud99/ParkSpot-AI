from __future__ import annotations

import asyncio
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.security import hash_password
from app.db.base import Base
import app.db.models  # noqa: F401  (register every table for create_all)
from app.db.models.camera import Camera
from app.db.models.enums import CameraMode, SpotType, UserRole, VehicleSize
from app.db.models.pricing import CityEvent
from app.db.models.spot import ParkingSpot
from app.db.models.user import User
from app.db.models.vehicle import Vehicle
from app.db.session import async_session_factory, engine
from app.utils.geo import zone_key_for
from app.utils.timeutil import utcnow

# Demo fixtures only (development): title, address, dLat, dLng, type, covered, EV, $/hr,
# total facility capacity, capacity authorized for ParkSpot under the (demo) agreement.
SPOTS = [
    ("Downtown Covered Garage", "100 Main St", 0.002, 0.002, SpotType.garage, True, True, "5.00", 120, 25),
    ("Mission Driveway", "200 Mission St", 0.01, -0.005, SpotType.driveway, False, False, "3.50", 1, 1),
    ("SoMa Small Lot", "300 Folsom St", -0.008, 0.01, SpotType.lot, False, True, "4.00", 40, 10),
    ("Union Square Driveway", "400 Post St", 0.013, -0.012, SpotType.driveway, True, False, "6.00", 2, 2),
    ("Wharf Street Spot", "500 Bay St", 0.033, 0.002, SpotType.street, False, False, "4.50", 1, 1),
    ("Downtown Open Lot", "150 Howard St", -0.003, -0.003, SpotType.lot, False, False, "3.00", 60, 15),
]


async def seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    from app.core.config import get_settings

    s = get_settings()
    async with async_session_factory() as db:
        existing = (await db.execute(select(User).where(User.email == "driver@demo.test"))).scalar_one_or_none()
        if existing:
            print("already seeded")
            return
        hashed = await asyncio.to_thread(hash_password, "demo1234")
        driver = User(email="driver@demo.test", hashed_password=hashed, full_name="Demo Driver", role=UserRole.driver)
        host = User(email="host@demo.test", hashed_password=hashed, full_name="Demo Host", role=UserRole.host)
        admin = User(email="admin@demo.test", hashed_password=hashed, full_name="Demo Admin", role=UserRole.admin)
        db.add_all([driver, host, admin])
        await db.flush()
        db.add(Vehicle(user_id=driver.id, plate="DEMO1234", make="Tesla", model="Model 3", color="white", is_default=True))
        spots: list[ParkingSpot] = []
        for i, (title, addr, dlat, dlng, stype, covered, ev, price, total_cap, auth_cap) in enumerate(SPOTS, 1):
            lat, lng = s.DEMO_CENTER_LAT + dlat, s.DEMO_CENTER_LNG + dlng
            spot = ParkingSpot(host_id=host.id, title=title, description=f"{title} near downtown", address=addr, latitude=lat, longitude=lng,
                               zone_key=zone_key_for(lat, lng), spot_type=stype, is_covered=covered, has_ev_charging=ev,
                               max_vehicle_size=VehicleSize.standard, base_price_per_hour=Decimal(price),
                               total_capacity=total_cap, authorized_capacity=auth_cap, currency=s.CURRENCY,
                               access_instructions="Enter via side gate; code in booking message." if i == 1 else "Park in marked bay.")
            db.add(spot)
            spots.append(spot)
        await db.flush()
        for i, spot in enumerate(spots, 1):
            db.add(Camera(id=f"cam-{i:03d}", spot_id=spot.id, mode=CameraMode.simulate))
        now = utcnow()
        db.add(CityEvent(name="Downtown Concert", latitude=s.DEMO_CENTER_LAT, longitude=s.DEMO_CENTER_LNG, radius_km=2.0,
                         starts_at=now + timedelta(hours=2), ends_at=now + timedelta(hours=8), expected_attendance=10000))
        await db.commit()
        print(f"seeded: driver={driver.id} host={host.id} admin={admin.id} spots={[sp.id for sp in spots]} cameras=cam-001..cam-006")


if __name__ == "__main__":
    asyncio.run(seed())
