from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.vehicle import Vehicle


async def list_for_user(db: AsyncSession, user_id: int) -> list[Vehicle]:
    return list((await db.execute(select(Vehicle).where(Vehicle.user_id == user_id).order_by(Vehicle.id))).scalars().all())


async def get(db: AsyncSession, vehicle_id: int) -> Vehicle | None:
    return await db.get(Vehicle, vehicle_id)


async def get_by_plate(db: AsyncSession, user_id: int, plate: str) -> Vehicle | None:
    return (await db.execute(select(Vehicle).where(Vehicle.user_id == user_id, Vehicle.plate == plate))).scalar_one_or_none()


async def create(db: AsyncSession, vehicle: Vehicle) -> Vehicle:
    db.add(vehicle)
    await db.flush()
    return vehicle


async def clear_defaults(db: AsyncSession, user_id: int) -> None:
    await db.execute(update(Vehicle).where(Vehicle.user_id == user_id).values(is_default=False))


async def delete(db: AsyncSession, vehicle: Vehicle) -> None:
    await db.delete(vehicle)
    await db.flush()
