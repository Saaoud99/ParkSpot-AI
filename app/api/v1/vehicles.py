from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.vehicle import VehicleIn, VehicleOut
from app.services import vehicle_service

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.get("", response_model=list[VehicleOut])
async def list_vehicles(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await vehicle_service.list_vehicles(db, user)


@router.post("", response_model=VehicleOut, status_code=201)
async def create_vehicle(data: VehicleIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await vehicle_service.create_vehicle(db, user, data)


@router.delete("/{vehicle_id}", status_code=204)
async def delete_vehicle(vehicle_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await vehicle_service.delete_vehicle(db, user, vehicle_id)
    return Response(status_code=204)
