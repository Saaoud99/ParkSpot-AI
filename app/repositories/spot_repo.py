from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.booking import ACTIVE_STATUSES, Booking
from app.db.models.enums import BookingStatus
from app.db.models.spot import AvailabilityWindow, ParkingSpot
from app.utils.geo import bbox_for_radius


async def get(db: AsyncSession, spot_id: int) -> ParkingSpot | None:
    return (await db.execute(select(ParkingSpot).options(selectinload(ParkingSpot.availability_windows), selectinload(ParkingSpot.camera), selectinload(ParkingSpot.host)).where(ParkingSpot.id == spot_id))).scalar_one_or_none()


async def create(db: AsyncSession, spot: ParkingSpot) -> ParkingSpot:
    db.add(spot)
    await db.flush()
    return spot


async def delete(db: AsyncSession, spot: ParkingSpot) -> None:
    await db.delete(spot)
    await db.flush()


async def list_for_host(db: AsyncSession, host_id: int) -> list[ParkingSpot]:
    return list((await db.execute(select(ParkingSpot).options(selectinload(ParkingSpot.camera)).where(ParkingSpot.host_id == host_id).order_by(ParkingSpot.id))).scalars().all())


async def search_candidates(db: AsyncSession, lat: float, lng: float, radius_km: float) -> list[ParkingSpot]:
    min_lat, max_lat, min_lng, max_lng = bbox_for_radius(lat, lng, radius_km)
    return list((await db.execute(select(ParkingSpot).options(selectinload(ParkingSpot.availability_windows)).where(
        ParkingSpot.latitude.between(min_lat, max_lat), ParkingSpot.longitude.between(min_lng, max_lng),
        ParkingSpot.is_published.is_(True)))).scalars().all())


async def overlapping_booking(db: AsyncSession, spot_id: int, start: datetime, end: datetime) -> Booking | None:
    stmt = select(Booking).where(
        Booking.spot_id == spot_id, Booking.status.in_(ACTIVE_STATUSES),
        Booking.start_time < end, Booking.end_time > start)
    return (await db.execute(stmt)).scalar_one_or_none()


async def has_active_booking(db: AsyncSession, spot_id: int) -> bool:
    row = (await db.execute(select(func.count(Booking.id)).where(Booking.spot_id == spot_id, Booking.status.in_((BookingStatus.held, BookingStatus.confirmed, BookingStatus.active))))).scalar_one()
    return row > 0


async def replace_windows(db: AsyncSession, spot_id: int, windows: list[AvailabilityWindow]) -> list[AvailabilityWindow]:
    existing = list((await db.execute(select(AvailabilityWindow).where(AvailabilityWindow.spot_id == spot_id))).scalars().all())
    for w in existing:
        await db.delete(w)
    await db.flush()
    for w in windows:
        db.add(w)
    await db.flush()
    return windows


async def list_zones(db: AsyncSession) -> list[str]:
    return list((await db.execute(select(ParkingSpot.zone_key).where(ParkingSpot.is_published.is_(True)).distinct())).scalars().all())


async def spots_in_zone(db: AsyncSession, zone_key: str) -> list[ParkingSpot]:
    return list((await db.execute(select(ParkingSpot).where(ParkingSpot.zone_key == zone_key, ParkingSpot.is_published.is_(True)))).scalars().all())


async def count_all(db: AsyncSession) -> int:
    return (await db.execute(select(func.count(ParkingSpot.id)))).scalar_one()
