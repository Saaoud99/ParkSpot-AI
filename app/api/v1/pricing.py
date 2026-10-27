from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.db.models.enums import UserRole
from app.db.models.user import User
from app.db.session import get_db
from app.repositories import pricing_repo, spot_repo
from app.core.exceptions import NotFoundError
from app.schemas.pricing import PriceQuote, PricingSnapshotOut
from app.services import pricing_service
from app.utils.timeutil import parse_iso

router = APIRouter(prefix="/pricing", tags=["pricing"])


@router.get("/quote", response_model=PriceQuote)
async def quote(spot_id: int, start: str, end: str, db: AsyncSession = Depends(get_db)):
    spot = await spot_repo.get(db, spot_id)
    if spot is None:
        raise NotFoundError("spot not found")
    return await pricing_service.quote(db, spot, parse_iso(start), parse_iso(end))


@router.get("/snapshots", response_model=list[PricingSnapshotOut])
async def snapshots(zone_key: str | None = None, spot_id: int | None = None, db: AsyncSession = Depends(get_db)):
    zk = zone_key
    if spot_id is not None:
        spot = await spot_repo.get(db, spot_id)
        if spot is None:
            raise NotFoundError("spot not found")
        zk = spot.zone_key
    return await pricing_repo.latest_list(db, zk, 20)


@router.post("/recompute")
async def recompute(user: User = Depends(require_role(UserRole.admin)), db: AsyncSession = Depends(get_db)):
    from app.workers.pricing_jobs import refresh_all_zones

    return await refresh_all_zones()
