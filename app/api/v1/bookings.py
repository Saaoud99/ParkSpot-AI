from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.db.models.enums import UserRole
from app.db.models.user import User
from app.db.session import get_db
from app.repositories import booking_repo
from app.schemas.booking import ConfirmIn, HoldIn
from app.schemas.common import Page
from app.services import booking_service

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("/hold", status_code=201)
async def hold(data: HoldIn, user: User = Depends(require_role(UserRole.driver)), db: AsyncSession = Depends(get_db)):
    booking = await booking_service.hold(db, user, data)
    return booking_service.serialize(booking, user)


@router.get("/host")
async def host_bookings(spot_id: int | None = None, limit: int = Query(20, le=100), offset: int = 0, user: User = Depends(require_role(UserRole.host)), db: AsyncSession = Depends(get_db)):
    rows, total = await booking_repo.list_for_host(db, user.id, spot_id, limit, offset)
    return Page(items=[booking_service.serialize(b, user) for b in rows], total=total, limit=limit, offset=offset)


@router.get("")
async def my_bookings(status: str | None = None, limit: int = Query(20, le=100), offset: int = 0, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows, total = await booking_repo.list_for_driver(db, user.id, status, limit, offset)
    return Page(items=[booking_service.serialize(b, user) for b in rows], total=total, limit=limit, offset=offset)


@router.get("/{booking_id}")
async def get_booking(booking_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    booking = await booking_service.get_for_user(db, booking_id, user)
    return booking_service.serialize(booking, user)


@router.post("/{booking_id}/confirm")
async def confirm(booking_id: int, data: ConfirmIn | None = None, user: User = Depends(require_role(UserRole.driver)), db: AsyncSession = Depends(get_db)):
    booking = await booking_service.confirm(db, user, booking_id)
    return booking_service.serialize(booking, user)


@router.post("/{booking_id}/cancel")
async def cancel(booking_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    booking = await booking_service.cancel(db, user, booking_id)
    return booking_service.serialize(booking, user)


@router.get("/{booking_id}/qr")
async def qr(booking_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    png = await booking_service.qr_png(db, user, booking_id)
    return Response(content=png, media_type="image/png")
