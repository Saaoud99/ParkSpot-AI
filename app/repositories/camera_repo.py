from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.camera import AccessEvent, Camera


async def get_camera(db: AsyncSession, camera_id: str) -> Camera | None:
    return await db.get(Camera, camera_id)


async def create_camera(db: AsyncSession, camera: Camera) -> Camera:
    db.add(camera)
    await db.flush()
    return camera


async def create_event(db: AsyncSession, event: AccessEvent) -> AccessEvent:
    db.add(event)
    await db.flush()
    return event


async def list_events(db: AsyncSession, spot_id: int | None, limit: int = 50) -> list[AccessEvent]:
    stmt = select(AccessEvent).order_by(AccessEvent.created_at.desc()).limit(limit)
    if spot_id is not None:
        stmt = stmt.where(AccessEvent.spot_id == spot_id)
    return list((await db.execute(stmt)).scalars().all())
