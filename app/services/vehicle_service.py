from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models.user import User
from app.db.models.vehicle import Vehicle
from app.repositories import vehicle_repo
from app.schemas.vehicle import VehicleIn
from app.vision.plates import normalize_plate


async def list_vehicles(db: AsyncSession, user: User) -> list[Vehicle]:
    return await vehicle_repo.list_for_user(db, user.id)


async def create_vehicle(db: AsyncSession, user: User, data: VehicleIn) -> Vehicle:
    plate = normalize_plate(data.plate)
    if not plate:
        raise ConflictError("invalid plate", code="invalid_plate")
    if await vehicle_repo.get_by_plate(db, user.id, plate):
        raise ConflictError("vehicle already exists", code="vehicle_exists")
    existing = await vehicle_repo.list_for_user(db, user.id)
    make_default = data.is_default or len(existing) == 0
    if make_default:
        await vehicle_repo.clear_defaults(db, user.id)
    vehicle = Vehicle(user_id=user.id, plate=plate, make=data.make, model=data.model, color=data.color, is_default=make_default)
    await vehicle_repo.create(db, vehicle)
    await db.commit()
    await db.refresh(vehicle)
    return vehicle


async def delete_vehicle(db: AsyncSession, user: User, vehicle_id: int) -> None:
    vehicle = await vehicle_repo.get(db, vehicle_id)
    if vehicle is None or vehicle.user_id != user.id:
        raise NotFoundError("vehicle not found")
    was_default = vehicle.is_default
    await vehicle_repo.delete(db, vehicle)
    if was_default:
        remaining = await vehicle_repo.list_for_user(db, user.id)
        if remaining:
            remaining[0].is_default = True
    await db.commit()
