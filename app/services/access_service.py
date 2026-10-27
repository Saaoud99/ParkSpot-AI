from __future__ import annotations

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.security import decode_access_pass
from app.db.models.booking import Booking
from app.db.models.camera import AccessEvent
from app.db.models.enums import AccessDecision, AccessSource, BookingStatus, SpotStatus
from app.db.models.user import User
from app.repositories import booking_repo, camera_repo, spot_repo
from app.utils.timeutil import to_utc, utcnow
from app.vision.plates import normalize_plate, plates_match


async def _grant(db: AsyncSession, booking: Booking, source: AccessSource, plate: str | None, camera_id: str | None, vconf: float, pconf: float, detected: str | None) -> dict:
    booking.status = BookingStatus.active
    booking.checked_in_at = utcnow()
    spot = await spot_repo.get(db, booking.spot_id)
    if spot:
        spot.status = SpotStatus.occupied
    ev = AccessEvent(spot_id=booking.spot_id, booking_id=booking.id, camera_id=camera_id, detected_plate=detected, matched_plate=booking.vehicle_plate, decision=AccessDecision.granted, vehicle_confidence=vconf, plate_confidence=pconf, source=source)
    await camera_repo.create_event(db, ev)
    return {"decision": "granted", "booking_id": booking.id, "spot_status": "occupied", "message": "Access granted."}


async def handle_detection(db: AsyncSession, camera_id: str, present: bool, plate: str | None, vconf: float = 0.99, pconf: float = 0.98, source: AccessSource = AccessSource.simulated) -> dict:
    camera = await camera_repo.get_camera(db, camera_id)
    if camera is None:
        raise NotFoundError("camera not found")
    spot = await spot_repo.get(db, camera.spot_id)
    if spot is None:
        raise NotFoundError("spot not found")
    now = utcnow()
    camera.last_frame_at = now
    normalized = normalize_plate(plate) if plate else None
    if not present:
        camera.consecutive_empty_frames += 1
        s = get_settings()
        decision = AccessDecision.no_vehicle
        message = "No vehicle detected."
        booking_id = None
        if spot.status == SpotStatus.occupied and camera.consecutive_empty_frames >= s.DEPARTURE_EMPTY_FRAMES:
            # Complete the active booking on departure.
            from sqlalchemy import select

            active = (await db.execute(select(Booking).where(Booking.spot_id == spot.id, Booking.status == BookingStatus.active))).scalar_one_or_none()
            if active:
                active.status = BookingStatus.completed
                active.checked_out_at = now
                booking_id = active.id
            spot.status = SpotStatus.available
            decision = AccessDecision.departure
            message = "Departure detected."
        ev = AccessEvent(spot_id=spot.id, booking_id=booking_id, camera_id=camera_id, detected_plate=None, matched_plate=None, decision=decision, vehicle_confidence=vconf, plate_confidence=0.0, source=source)
        await camera_repo.create_event(db, ev)
        await db.commit()
        return {"camera_id": camera_id, "spot_id": spot.id, "decision": decision.value, "detected_plate": None, "matched_booking_id": booking_id, "vehicle_confidence": vconf, "plate_confidence": 0.0, "spot_status": spot.status.value, "message": message}
    camera.consecutive_empty_frames = 0
    camera.last_detected_plate = normalized
    booking = await booking_repo.find_by_plate_window(db, spot.id, normalized or "", now) if normalized else None
    if booking and normalized and plates_match(booking.vehicle_plate, normalized):
        result = await _grant(db, booking, source, normalized, camera_id, vconf, pconf, normalized)
        await db.commit()
        return {"camera_id": camera_id, "spot_id": spot.id, "detected_plate": normalized, "matched_booking_id": result["booking_id"], "vehicle_confidence": vconf, "plate_confidence": pconf, **result}
    ev = AccessEvent(spot_id=spot.id, booking_id=None, camera_id=camera_id, detected_plate=normalized, matched_plate=None, decision=AccessDecision.denied, vehicle_confidence=vconf, plate_confidence=pconf, source=source)
    await camera_repo.create_event(db, ev)
    await db.commit()
    return {"camera_id": camera_id, "spot_id": spot.id, "decision": "denied", "detected_plate": normalized, "matched_booking_id": None, "vehicle_confidence": vconf, "plate_confidence": pconf, "spot_status": spot.status.value, "message": "No matching booking for plate."}


async def verify_qr(db: AsyncSession, user: User, token: str) -> dict:
    payload = decode_access_pass(token)
    booking = await booking_repo.get(db, int(payload["bid"]))
    if booking is None:
        raise NotFoundError("booking not found")
    if booking.spot and booking.spot.host_id != user.id and user.role.value != "admin":
        raise ForbiddenError("forbidden")
    now = utcnow()
    if booking.status not in (BookingStatus.confirmed, BookingStatus.active):
        return {"valid": False, "booking_id": booking.id, "spot_id": booking.spot_id, "plate": booking.vehicle_plate, "decision": "denied", "message": f"booking is {booking.status.value}"}
    grace = timedelta(minutes=get_settings().ARRIVAL_GRACE_MINUTES)
    if not (to_utc(booking.start_time) - grace <= now <= to_utc(booking.end_time) + grace):
        return {"valid": False, "booking_id": booking.id, "spot_id": booking.spot_id, "plate": booking.vehicle_plate, "decision": "denied", "message": "outside access window"}
    result = await _grant(db, booking, AccessSource.qr, booking.vehicle_plate, None, 1.0, 1.0, booking.vehicle_plate)
    await db.commit()
    return {"valid": True, "booking_id": booking.id, "spot_id": booking.spot_id, "plate": booking.vehicle_plate, "decision": result["decision"], "message": result["message"]}
