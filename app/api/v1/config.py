from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["config"])


@router.get("/config/public")
async def public_config() -> dict:
    s = get_settings()
    return {
        "mapbox_access_token": s.MAPBOX_ACCESS_TOKEN,
        "demo_center": {"lat": s.DEMO_CENTER_LAT, "lng": s.DEMO_CENTER_LNG},
        "currency": s.CURRENCY,
        "vision_mode": s.VISION_MODE,
    }
