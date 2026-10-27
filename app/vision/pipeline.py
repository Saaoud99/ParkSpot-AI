from __future__ import annotations

import asyncio

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.camera import Camera
from app.db.models.enums import AccessSource
from app.services import access_service
from app.vision.registry import get_detector, get_plate_reader
from app.vision.simulator import SimulatedDetector, SimulatedPlateReader


def _roi_for(camera: Camera, width: int, height: int) -> tuple[int, int, int, int]:
    if camera.roi and len(camera.roi) == 4:
        x1, y1, x2, y2 = camera.roi
        return int(x1 * width), int(y1 * height), int(x2 * width), int(y2 * height)
    # Central 60%.
    return int(width * 0.2), int(height * 0.2), int(width * 0.8), int(height * 0.8)


async def process_frame(db: AsyncSession, camera: Camera, image_rgb: np.ndarray | None = None, simulated_present: bool = True, simulated_plate: str | None = None) -> dict:
    s = get_settings()
    if s.VISION_MODE == "simulate":
        detector = SimulatedDetector(simulated_present)
        reader = SimulatedPlateReader(simulated_plate)
        height, width = (image_rgb.shape[0], image_rgb.shape[1]) if image_rgb is not None else (480, 640)
        img = image_rgb if image_rgb is not None else np.zeros((height, width, 3), dtype=np.uint8)
        roi = _roi_for(camera, width, height)
        detection = await asyncio.to_thread(detector.detect, img, roi)
        reading = await asyncio.to_thread(reader.read, img, detection.bbox or roi) if detection.present else None
        return await access_service.handle_detection(db, camera.id, detection.present, reading.text if reading else None, detection.confidence, reading.confidence if reading else 0.0, AccessSource.simulated)
    height, width = (image_rgb.shape[0], image_rgb.shape[1]) if image_rgb is not None else (480, 640)
    img = image_rgb if image_rgb is not None else np.zeros((height, width, 3), dtype=np.uint8)
    roi = _roi_for(camera, width, height)
    detector = get_detector()
    reader = get_plate_reader()
    detection = await asyncio.to_thread(detector.detect, img, roi)
    reading = await asyncio.to_thread(reader.read, img, detection.bbox or roi) if detection.present else None
    return await access_service.handle_detection(db, camera.id, detection.present, reading.text if reading else simulated_plate, detection.confidence, reading.confidence if reading else 0.0, AccessSource.camera)
