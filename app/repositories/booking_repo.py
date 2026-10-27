from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.booking import Booking
from app.db.models.enums import BookingStatus


async def get(db: AsyncSession, booking_id: int) -> Booking | None:
    return (await db.execute(select(Booking).options(selectinload(Booking.spot), selectinload(Booking.payment)).where(Booking.id == booking_id))).scalar_one_or_none()


async def create(db: AsyncSession, booking: Booking) -> Booking:
    db.add(booking)
    await db.flush()
    return booking


async def list_for_driver(db: AsyncSession, driver_id: int, status: str | None, limit: int, offset: int) -> tuple[list[Booking], int]:
    stmt = select(Booking).options(selectinload(Booking.spot)).where(Booking.driver_id == driver_id)
    count_stmt = select(func.count(Booking.id)).where(Booking.driver_id == driver_id)
    if status:
        stmt = stmt.where(Booking.status == status)
        count_stmt = count_stmt.where(Booking.status == status)
    total = (await db.execute(count_stmt)).scalar_one()
    rows = (await db.execute(stmt.order_by(Booking.created_at.desc()).limit(limit).offset(offset))).scalars().all()
    return list(rows), total


async def list_for_host(db: AsyncSession, host_id: int, spot_id: int | None, limit: int, offset: int) -> tuple[list[Booking], int]:
    from app.db.models.spot import ParkingSpot

    stmt = select(Booking).options(selectinload(Booking.spot)).join(ParkingSpot, Booking.spot_id == ParkingSpot.id).where(ParkingSpot.host_id == host_id)
    count_stmt = select(func.count(Booking.id)).join(ParkingSpot, Booking.spot_id == ParkingSpot.id).where(ParkingSpot.host_id == host_id)
    if spot_id:
        stmt = stmt.where(Booking.spot_id == spot_id)
        count_stmt = count_stmt.where(Booking.spot_id == spot_id)
    total = (await db.execute(count_stmt)).scalar_one()
    rows = (await db.execute(stmt.order_by(Booking.created_at.desc()).limit(limit).offset(offset))).scalars().all()
    return list(rows), total


async def find_by_plate_window(db: AsyncSession, spot_id: int, plate: str, at: datetime) -> Booking | None:
    rows = (await db.execute(select(Booking).where(
        Booking.spot_id == spot_id, Booking.status.in_((BookingStatus.confirmed, BookingStatus.active)),
        Booking.start_time <= at, Booking.end_time >= at).order_by(Booking.start_time))).scalars().all()
    from app.vision.plates import plates_match

    for b in rows:
        if plates_match(b.vehicle_plate, plate):
            return b
    return None


async def count_by_status(db: AsyncSession) -> dict[str, int]:
    rows = (await db.execute(select(Booking.status, func.count(Booking.id)).group_by(Booking.status))).all()
    return {str(k.value if hasattr(k, "value") else k): v for k, v in rows}
