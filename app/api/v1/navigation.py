from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.navigation import NavigationOut
from app.services import booking_service
from app.services.navigation_service import build_navigation

router = APIRouter(prefix="/navigation", tags=["navigation"])


@router.get("/{booking_id}", response_model=NavigationOut)
async def navigation(booking_id: int, origin_lat: float | None = None, origin_lng: float | None = None, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    booking = await booking_service.get_for_user(db, booking_id, user)
    return build_navigation(booking.spot, origin_lat, origin_lng)
