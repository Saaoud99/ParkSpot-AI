from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.pricing import CityEvent, PricingSnapshot
from app.utils.timeutil import utcnow


async def latest_valid(db: AsyncSession, zone_key: str) -> PricingSnapshot | None:
    now = utcnow()
    return (await db.execute(select(PricingSnapshot).where(PricingSnapshot.zone_key == zone_key, PricingSnapshot.valid_until > now).order_by(PricingSnapshot.computed_at.desc()).limit(1))).scalar_one_or_none()


async def latest_list(db: AsyncSession, zone_key: str | None = None, limit: int = 20) -> list[PricingSnapshot]:
    stmt = select(PricingSnapshot).order_by(PricingSnapshot.computed_at.desc()).limit(limit)
    if zone_key:
        stmt = stmt.where(PricingSnapshot.zone_key == zone_key)
    return list((await db.execute(stmt)).scalars().all())


async def create(db: AsyncSession, snap: PricingSnapshot) -> PricingSnapshot:
    db.add(snap)
    await db.flush()
    return snap


async def list_events(db: AsyncSession) -> list[CityEvent]:
    return list((await db.execute(select(CityEvent).order_by(CityEvent.starts_at))).scalars().all())


async def create_event(db: AsyncSession, event: CityEvent) -> CityEvent:
    db.add(event)
    await db.flush()
    return event
