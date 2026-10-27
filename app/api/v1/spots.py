from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_optional_user, require_role
from app.db.models.enums import UserRole
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.spot import (
    AvailabilityWindowIn,
    AvailabilityWindowOut,
    HostSpotOut,
    SpotCreate,
    SpotDetailOut,
    SpotOut,
    SpotSearchResult,
    SpotUpdate,
)
from app.services import geocode_service, spot_service
from app.utils.timeutil import parse_iso, utcnow

router = APIRouter(prefix="/spots", tags=["spots"])


@router.get("/geocode")
async def geocode(q: str = Query(..., min_length=1), lat: float | None = None, lng: float | None = None):
    """Resolve a destination name to coordinates (Mapbox, landmark fallback). Additive endpoint for the discovery UI."""
    proximity = (lat, lng) if lat is not None and lng is not None else None
    return await geocode_service.geocode(q, proximity)


@router.get("/search", response_model=list[SpotSearchResult])
async def search_spots(
    lat: float = Query(...), lng: float = Query(...), radius_km: float = Query(2, le=25),
    start: str | None = None, end: str | None = None, covered: bool | None = None, ev: bool | None = None,
    spot_type: str | None = None, max_price_per_hour: Decimal | None = None, limit: int = Query(20, le=50),
    db: AsyncSession = Depends(get_db), user: User | None = Depends(get_optional_user),
):
    now = utcnow()
    start_dt = parse_iso(start) if start else now + timedelta(minutes=30)
    end_dt = parse_iso(end) if end else start_dt + timedelta(hours=2)
    return await spot_service.search(db, lat, lng, radius_km, start_dt, end_dt, covered, ev, spot_type, max_price_per_hour, limit)


@router.get("/mine", response_model=list[HostSpotOut])
async def my_spots(user: User = Depends(require_role(UserRole.host)), db: AsyncSession = Depends(get_db)):
    return await spot_service.host_spots(db, user)


@router.get("/{spot_id}", response_model=SpotDetailOut)
async def get_spot(spot_id: int, db: AsyncSession = Depends(get_db)):
    spot = await spot_service.get_spot(db, spot_id)
    data = spot_service._spot_dict(spot)
    return {**data, "host_name": spot.host.full_name if spot.host else "", "availability_windows": spot.availability_windows, "camera_id": spot.camera.id if spot.camera else None}


@router.post("", response_model=SpotOut, status_code=201)
async def create_spot(data: SpotCreate, user: User = Depends(require_role(UserRole.host)), db: AsyncSession = Depends(get_db)):
    return await spot_service.create_spot(db, user, data)


@router.patch("/{spot_id}", response_model=SpotOut)
async def update_spot(spot_id: int, data: SpotUpdate, user: User = Depends(require_role(UserRole.host)), db: AsyncSession = Depends(get_db)):
    return await spot_service.update_spot(db, user, spot_id, data)


@router.delete("/{spot_id}", status_code=204)
async def delete_spot(spot_id: int, user: User = Depends(require_role(UserRole.host)), db: AsyncSession = Depends(get_db)):
    await spot_service.delete_spot(db, user, spot_id)
    return Response(status_code=204)


@router.put("/{spot_id}/availability", response_model=list[AvailabilityWindowOut])
async def set_availability(spot_id: int, windows: list[AvailabilityWindowIn], user: User = Depends(require_role(UserRole.host)), db: AsyncSession = Depends(get_db)):
    return await spot_service.replace_availability(db, user, spot_id, windows)
