from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.db.models.enums import BookingStatus, SpotStatus, UserRole
from app.db.models.spot import AvailabilityWindow, ParkingSpot
from app.db.models.user import User
from app.repositories import spot_repo
from app.schemas.spot import AvailabilityWindowIn, SpotCreate, SpotUpdate
from app.utils.geo import zone_key_for
from app.utils.money import q2
from app.utils.timeutil import utcnow


def _check_owner(spot: ParkingSpot, user: User) -> None:
    if user.role != UserRole.admin and spot.host_id != user.id:
        raise ForbiddenError("forbidden")


async def create_spot(db: AsyncSession, user: User, data: SpotCreate) -> ParkingSpot:
    s = get_settings()
    spot = ParkingSpot(
        host_id=user.id, title=data.title, description=data.description, address=data.address,
        latitude=data.latitude, longitude=data.longitude, zone_key=zone_key_for(data.latitude, data.longitude),
        spot_type=data.spot_type, is_covered=data.is_covered, has_ev_charging=data.has_ev_charging,
        max_vehicle_size=data.max_vehicle_size, base_price_per_hour=q2(data.base_price_per_hour),
        currency=s.CURRENCY, dynamic_pricing_enabled=data.dynamic_pricing_enabled,
        max_multiplier=data.max_multiplier, access_instructions=data.access_instructions,
    )
    await spot_repo.create(db, spot)
    await db.commit()
    await db.refresh(spot)
    return spot


async def update_spot(db: AsyncSession, user: User, spot_id: int, data: SpotUpdate) -> ParkingSpot:
    spot = await spot_repo.get(db, spot_id)
    if spot is None:
        raise NotFoundError("spot not found")
    _check_owner(spot, user)
    updates = data.model_dump(exclude_unset=True)
    # Host may only set available/unavailable directly; held/occupied are system-set.
    if "status" in updates and updates["status"] not in (SpotStatus.available, SpotStatus.unavailable) and user.role != UserRole.admin:
        updates.pop("status")
    for k, v in updates.items():
        setattr(spot, k, v)
    spot.zone_key = zone_key_for(spot.latitude, spot.longitude)
    await db.commit()
    await db.refresh(spot)
    return spot


async def delete_spot(db: AsyncSession, user: User, spot_id: int) -> None:
    spot = await spot_repo.get(db, spot_id)
    if spot is None:
        raise NotFoundError("spot not found")
    _check_owner(spot, user)
    if await spot_repo.has_active_booking(db, spot_id):
        raise ConflictError("spot has active bookings", code="spot_has_active_bookings")
    await spot_repo.delete(db, spot)
    await db.commit()


async def get_spot(db: AsyncSession, spot_id: int) -> ParkingSpot:
    spot = await spot_repo.get(db, spot_id)
    if spot is None:
        raise NotFoundError("spot not found")
    return spot


async def replace_availability(db: AsyncSession, user: User, spot_id: int, windows_in: list[AvailabilityWindowIn]) -> list[AvailabilityWindow]:
    spot = await get_spot(db, spot_id)
    _check_owner(spot, user)
    windows = [AvailabilityWindow(spot_id=spot_id, day_of_week=w.day_of_week, start_time=w.start_time, end_time=w.end_time) for w in windows_in]
    result = await spot_repo.replace_windows(db, spot_id, windows)
    await db.commit()
    for w in result:
        await db.refresh(w)
    return result


def is_within_windows(spot: ParkingSpot, start: datetime, end: datetime) -> bool:
    if not spot.availability_windows:
        return True
    # Check every 15-minute slice.
    cur = start
    while cur < end:
        dow = cur.weekday()
        t = cur.time()
        ok = False
        for w in spot.availability_windows:
            if w.day_of_week is not None and w.day_of_week != dow:
                continue
            if w.start_time <= w.end_time:
                if w.start_time <= t < w.end_time or (t == w.start_time):
                    ok = True
                    break
            else:  # overnight window
                if t >= w.start_time or t < w.end_time:
                    ok = True
                    break
        if not ok:
            return False
        cur += timedelta(minutes=15)
    return True


async def is_available(db: AsyncSession, spot: ParkingSpot, start: datetime, end: datetime) -> bool:
    if not spot.is_published or spot.status == SpotStatus.unavailable:
        return False
    if not is_within_windows(spot, start, end):
        return False
    return await spot_repo.overlapping_booking(db, spot.id, start, end) is None


async def search(
    db: AsyncSession, lat: float, lng: float, radius_km: float, start: datetime, end: datetime,
    covered: bool | None = None, ev: bool | None = None, spot_type: str | None = None,
    max_price_per_hour: Decimal | None = None, limit: int = 20,
) -> list[dict]:
    from app.services import pricing_service
    from app.utils.geo import haversine_km
    from app.utils.timeutil import round_up_quarter_hours

    candidates = await spot_repo.search_candidates(db, lat, lng, radius_km)
    hours = Decimal(str(round_up_quarter_hours(end - start)))
    results: list[dict] = []
    for spot in candidates:
        dist = haversine_km(lat, lng, spot.latitude, spot.longitude)
        if dist > radius_km:
            continue
        if covered is not None and spot.is_covered != covered:
            continue
        if ev is not None and spot.has_ev_charging != ev:
            continue
        if spot_type is not None and spot.spot_type.value != spot_type:
            continue
        if not await is_available(db, spot, start, end):
            continue
        quote = await pricing_service.quote(db, spot, start, end)
        if max_price_per_hour is not None and quote["price_per_hour_now"] > max_price_per_hour:
            continue
        results.append({**_spot_dict(spot), "distance_km": round(dist, 3), "multiplier": quote["multiplier"],
                        "price_per_hour_now": quote["price_per_hour_now"], "estimated_total": quote["total"], "is_available": True})
    results.sort(key=lambda r: r["distance_km"])
    return results[:limit]


def _spot_dict(spot: ParkingSpot) -> dict:
    return {
        "id": spot.id, "host_id": spot.host_id, "title": spot.title, "description": spot.description,
        "address": spot.address, "latitude": spot.latitude, "longitude": spot.longitude, "zone_key": spot.zone_key,
        "spot_type": spot.spot_type, "is_covered": spot.is_covered, "has_ev_charging": spot.has_ev_charging,
        "max_vehicle_size": spot.max_vehicle_size, "base_price_per_hour": spot.base_price_per_hour,
        "currency": spot.currency, "dynamic_pricing_enabled": spot.dynamic_pricing_enabled,
        "max_multiplier": spot.max_multiplier, "status": spot.status, "access_instructions": spot.access_instructions,
        "is_published": spot.is_published, "created_at": spot.created_at,
    }


async def host_spots(db: AsyncSession, user: User) -> list[dict]:
    from sqlalchemy import func, select

    from app.db.models.booking import Booking

    spots = await spot_repo.list_for_host(db, user.id)
    out: list[dict] = []
    now = utcnow()
    for spot in spots:
        count = (await db.execute(select(func.count(Booking.id)).where(Booking.spot_id == spot.id, Booking.start_time >= now, Booking.status.in_((BookingStatus.held, BookingStatus.confirmed, BookingStatus.active))))).scalar_one()
        earnings = (await db.execute(select(func.coalesce(func.sum(Booking.total_price), 0)).where(Booking.spot_id == spot.id, Booking.status.in_((BookingStatus.confirmed, BookingStatus.active, BookingStatus.completed))))).scalar_one()
        out.append({**_spot_dict(spot), "upcoming_bookings_count": count, "earnings_total": q2(Decimal(str(earnings))), "camera_id": spot.camera.id if spot.camera else None})
    return out
