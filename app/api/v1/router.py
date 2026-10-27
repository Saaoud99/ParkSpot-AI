from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import access, admin, auth, bookings, chat, config, navigation, pricing, spots, users, vehicles, vision

router = APIRouter(prefix="/api/v1")
router.include_router(config.router)
router.include_router(auth.router)
router.include_router(users.router)
router.include_router(vehicles.router)
router.include_router(spots.router)
router.include_router(pricing.router)
router.include_router(bookings.router)
router.include_router(navigation.router)
router.include_router(chat.router)
router.include_router(admin.router)
router.include_router(vision.router)
router.include_router(access.router)
