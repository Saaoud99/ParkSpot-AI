from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.db.models.booking import Booking
from app.db.models.camera import Camera
from app.db.models.enums import BookingStatus, SpotStatus, UserRole
from app.db.models.pricing import CityEvent
from app.db.models.spot import ParkingSpot
from app.db.models.user import User
from app.db.session import get_db
from app.repositories import pricing_repo, user_repo
from app.schemas.admin import CityEventIn, CityEventOut
from app.schemas.auth import UserOut
from app.schemas.common import Page
from app.utils.money import q2
from app.utils.timeutil import to_utc

router = APIRouter(prefix="/admin", tags=["admin"])
AdminDep = Depends(require_role(UserRole.admin))


@router.get("/stats")
async def stats(user: User = AdminDep, db: AsyncSession = Depends(get_db)):
    users = (await db.execute(select(func.count(User.id)))).scalar_one()
    hosts = (await db.execute(select(func.count(User.id)).where(User.role == UserRole.host))).scalar_one()
    spots = (await db.execute(select(func.count(ParkingSpot.id)))).scalar_one()
    cameras = (await db.execute(select(func.count(Camera.id)))).scalar_one()
    by_status_rows = (await db.execute(select(Booking.status, func.count(Booking.id)).group_by(Booking.status))).all()
    by_status = {k.value: v for k, v in by_status_rows}
    revenue = (await db.execute(select(func.coalesce(func.sum(Booking.total_price), 0)).where(Booking.status.in_((BookingStatus.confirmed, BookingStatus.active, BookingStatus.completed))))).scalar_one()
    fees = (await db.execute(select(func.coalesce(func.sum(Booking.platform_fee), 0)).where(Booking.status.in_((BookingStatus.confirmed, BookingStatus.active, BookingStatus.completed))))).scalar_one()
    occupied = (await db.execute(select(func.count(ParkingSpot.id)).where(ParkingSpot.status == SpotStatus.occupied))).scalar_one()
    return {"users": users, "hosts": hosts, "spots": spots, "cameras": cameras, "bookings_by_status": by_status,
            "revenue_total": str(q2(Decimal(str(revenue)))), "platform_fees_total": str(q2(Decimal(str(fees)))),
            "occupancy_rate": (occupied / spots if spots else 0.0)}


@router.get("/users")
async def list_users(limit: int = Query(20, le=100), offset: int = 0, user: User = AdminDep, db: AsyncSession = Depends(get_db)):
    rows, total = await user_repo.list_users(db, limit, offset)
    return Page(items=[UserOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset)


@router.get("/events", response_model=list[CityEventOut])
async def list_events(user: User = AdminDep, db: AsyncSession = Depends(get_db)):
    return await pricing_repo.list_events(db)


@router.post("/events", response_model=CityEventOut, status_code=201)
async def create_event(data: CityEventIn, user: User = AdminDep, db: AsyncSession = Depends(get_db)):
    ev = CityEvent(name=data.name, latitude=data.latitude, longitude=data.longitude, radius_km=data.radius_km,
                   starts_at=to_utc(data.starts_at), ends_at=to_utc(data.ends_at), expected_attendance=data.expected_attendance)
    await pricing_repo.create_event(db, ev)
    await db.commit()
    await db.refresh(ev)
    return ev
