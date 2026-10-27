from __future__ import annotations

import asyncio

import numpy as np
from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import camera_auth, get_current_user, require_role
from app.core.config import get_settings
from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.models.enums import UserRole
from app.db.models.user import User
from app.db.session import get_db
from app.repositories import camera_repo, spot_repo
from app.schemas.vision import AccessDecisionOut, AccessEventOut, SimulateIn
from app.vision.pipeline import process_frame
from app.vision.registry import vision_status

router = APIRouter(prefix="/vision", tags=["vision"])


async def _check_camera_owner(db: AsyncSession, user: User, camera_id: str) -> None:
    camera = await camera_repo.get_camera(db, camera_id)
    if camera is None:
        raise NotFoundError("camera not found")
    if user.role == UserRole.admin:
        return
    spot = await spot_repo.get(db, camera.spot_id)
    if spot is None or spot.host_id != user.id:
        raise ForbiddenError("forbidden")


@router.post("/frames", response_model=AccessDecisionOut)
async def frames(
    camera_id: str = Form(...), simulated_present: bool = Form(True), simulated_plate: str | None = Form(None),
    image: UploadFile | None = File(None), auth_user: User | None = Depends(camera_auth), db: AsyncSession = Depends(get_db),
):
    camera = await camera_repo.get_camera(db, camera_id)
    if camera is None:
        raise NotFoundError("camera not found")
    image_rgb = None
    if image is not None:
        data = await image.read()
        if data:
            def _decode(raw: bytes):  # type: ignore[no-untyped-def]
                from PIL import Image
                import io

                return np.array(Image.open(io.BytesIO(raw)).convert("RGB"))

            image_rgb = await asyncio.to_thread(_decode, data)
    return await process_frame(db, camera, image_rgb, simulated_present, simulated_plate)


@router.post("/simulate", response_model=AccessDecisionOut)
async def simulate(data: SimulateIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _check_camera_owner(db, user, data.camera_id)
    camera = await camera_repo.get_camera(db, data.camera_id)
    present = data.event == "arrival"
    plate = data.plate
    if not present:
        # Departure needs DEPARTURE_EMPTY_FRAMES empty frames; simulate them instantly.
        camera.consecutive_empty_frames = max(0, get_settings().DEPARTURE_EMPTY_FRAMES - 1)
        await db.commit()
    return await process_frame(db, camera, None, present, plate)


@router.get("/events", response_model=list[AccessEventOut])
async def events(spot_id: int | None = None, limit: int = 50, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role != UserRole.admin:
        if spot_id is None:
            raise ForbiddenError("forbidden")
        spot = await spot_repo.get(db, spot_id)
        if spot is None:
            raise NotFoundError("spot not found")
        if spot.host_id != user.id:
            raise ForbiddenError("forbidden")
    rows = await camera_repo.list_events(db, spot_id, limit)
    return [{"id": e.id, "spot_id": e.spot_id, "booking_id": e.booking_id, "camera_id": e.camera_id, "detected_plate": e.detected_plate,
             "matched_plate": e.matched_plate, "decision": e.decision.value, "vehicle_confidence": e.vehicle_confidence,
             "plate_confidence": e.plate_confidence, "source": e.source.value, "created_at": e.created_at} for e in rows]


@router.get("/status")
async def status(user: User = Depends(require_role(UserRole.admin))):
    return vision_status()
