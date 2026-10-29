from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationAppError
from app.core.security import create_access_pass_token
from app.db.models.booking import Booking
from app.db.models.enums import BookingStatus, SpotStatus, UserRole
from app.db.models.user import User
from app.repositories import booking_repo, spot_repo, vehicle_repo
from app.schemas.booking import HoldIn
from app.services import payment_service, pricing_service, spot_service
from app.services.navigation_service import build_navigation
from app.utils.qr import render_qr_png
from app.utils.timeutil import to_utc, utcnow


def validate_window(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    start, end = to_utc(start), to_utc(end)
    s = get_settings()
    now = utcnow()
    if start < now - timedelta(minutes=5):
        raise ValidationAppError("start must not be in the past")
    if (end - start) < timedelta(minutes=s.MIN_BOOKING_MINUTES):
        raise ValidationAppError(f"booking must be at least {s.MIN_BOOKING_MINUTES} minutes")
    if (end - start) > timedelta(hours=72):
        raise ValidationAppError("booking must be at most 72 hours")
    return start, end


async def _refresh_spot_status(db: AsyncSession, spot_id: int) -> None:
    spot = await spot_repo.get(db, spot_id)
    if spot is None or spot.status in (SpotStatus.unavailable, SpotStatus.occupied):
        return
    now = utcnow()
    from sqlalchemy import select

    from app.db.models.booking import ACTIVE_STATUSES

    covering = (await db.execute(select(Booking).where(Booking.spot_id == spot_id, Booking.status.in_(ACTIVE_STATUSES), Booking.start_time <= now, Booking.end_time > now))).scalars().first()
    spot.status = SpotStatus.held if covering else SpotStatus.available


_hold_locks: dict[int, asyncio.Lock] = {}


def _spot_lock(spot_id: int) -> asyncio.Lock:
    return _hold_locks.setdefault(spot_id, asyncio.Lock())


async def hold(db: AsyncSession, user: User, data: HoldIn) -> Booking:
    # Serialize hold creation per facility within this process so the
    # check → insert → recount sequence cannot interleave with a competing
    # hold and oversell authorized capacity on the single-process/SQLite
    # deployment. (Multi-process production needs the same guard as a
    # database row lock on the facility row — Postgres SELECT … FOR UPDATE.)
    async with _spot_lock(data.spot_id):
        return await _hold_locked(db, user, data)


async def _hold_locked(db: AsyncSession, user: User, data: HoldIn) -> Booking:
    start, end = validate_window(data.start, data.end)
    spot = await spot_repo.get(db, data.spot_id)
    if spot is None:
        raise NotFoundError("spot not found")
    if not await spot_service.is_available(db, spot, start, end):
        raise ConflictError("spot unavailable for selected time", code="spot_unavailable")
    vehicle = None
    if data.vehicle_id is not None:
        vehicle = await vehicle_repo.get(db, data.vehicle_id)
        if vehicle is None or vehicle.user_id != user.id:
            raise ForbiddenError("forbidden")
    else:
        vehicles = await vehicle_repo.list_for_user(db, user.id)
        vehicle = next((v for v in vehicles if v.is_default), vehicles[0] if vehicles else None)
        if vehicle is None:
            raise ValidationAppError("no vehicle on file", code="no_vehicle")
    quote = await pricing_service.quote(db, spot, start, end)
    s = get_settings()
    booking = Booking(
        driver_id=user.id, spot_id=spot.id, vehicle_id=vehicle.id, vehicle_plate=vehicle.plate,
        start_time=start, end_time=end, status=BookingStatus.held,
        hold_expires_at=utcnow() + timedelta(minutes=s.HOLD_TTL_MINUTES),
        hours=quote["hours"], base_price_per_hour=quote["base_price_per_hour"], multiplier=quote["multiplier"],
        base_price=quote["base_price"], subtotal=quote["subtotal"], platform_fee=quote["platform_fee"],
        total_price=quote["total"], currency=quote["currency"], pricing_source=quote["pricing_source"],
    )
    await booking_repo.create(db, booking)
    # Capacity guard (revalidated at submit time, per §6): after inserting,
    # recount overlapping live reservations inside this transaction. If a
    # concurrent hold took the last authorized space first, this hold must
    # not commit — rolling back prevents overbooking beyond the partner
    # agreement's authorized capacity.
    taken = await spot_repo.overlapping_count(db, spot.id, start, end)
    if taken > spot.authorized_capacity:
        await db.rollback()
        raise ConflictError("spot unavailable for selected time", code="spot_unavailable")
    await _refresh_spot_status(db, spot.id)
    await db.commit()
    await db.refresh(booking)
    return await get_for_user(db, booking.id, user)


async def confirm(db: AsyncSession, user: User, booking_id: int) -> Booking:
    booking = await booking_repo.get(db, booking_id)
    if booking is None:
        raise NotFoundError("booking not found")
    if booking.driver_id != user.id and user.role != UserRole.admin:
        raise ForbiddenError("forbidden")
    if booking.status != BookingStatus.held:
        raise ConflictError(f"cannot confirm booking in status {booking.status.value}", code="invalid_state")
    if booking.hold_expires_at and to_utc(booking.hold_expires_at) < utcnow():
        booking.status = BookingStatus.expired
        await _refresh_spot_status(db, booking.spot_id)
        await db.commit()
        raise ConflictError("hold expired", code="hold_expired")
    await payment_service.charge(db, booking)
    booking.status = BookingStatus.confirmed
    booking.qr_token = create_access_pass_token(booking.id, booking.vehicle_plate, booking.spot_id, to_utc(booking.start_time), to_utc(booking.end_time))
    await _refresh_spot_status(db, booking.spot_id)
    await db.commit()
    return await get_for_user(db, booking.id, user)


async def cancel(db: AsyncSession, user: User, booking_id: int) -> Booking:
    booking = await booking_repo.get(db, booking_id)
    if booking is None:
        raise NotFoundError("booking not found")
    if booking.driver_id != user.id and user.role != UserRole.admin:
        raise ForbiddenError("forbidden")
    if booking.status not in (BookingStatus.held, BookingStatus.confirmed):
        raise ConflictError(f"cannot cancel booking in status {booking.status.value}", code="invalid_state")
    if booking.payment:
        await payment_service.refund(db, booking)
    booking.status = BookingStatus.cancelled
    booking.cancelled_at = utcnow()
    # Revoke the access pass immediately: a cancelled booking's QR must
    # never open a gate, even inside its original validity window.
    booking.qr_token = None
    spot = await spot_repo.get(db, booking.spot_id)
    if spot and spot.status == SpotStatus.held:
        spot.status = SpotStatus.available
    await _refresh_spot_status(db, booking.spot_id)
    await db.commit()
    return await get_for_user(db, booking.id, user)


async def get_for_user(db: AsyncSession, booking_id: int, user: User) -> Booking:
    booking = await booking_repo.get(db, booking_id)
    if booking is None:
        raise NotFoundError("booking not found")
    if user.role == UserRole.admin or booking.driver_id == user.id:
        return booking
    if booking.spot and booking.spot.host_id == user.id:
        return booking
    raise ForbiddenError("forbidden")


def serialize(booking: Booking, user: User) -> dict:
    from app.schemas.booking import BookingOut

    is_owner = booking.driver_id == user.id
    data = BookingOut.model_validate(booking).model_dump()
    data["spot"] = booking.spot
    data["qr_url"] = f"/api/v1/bookings/{booking.id}/qr" if is_owner and booking.qr_token else None
    # Never return the raw access-pass token in JSON: the QR *image* is
    # fetched from qr_url with the driver's auth, so the bearer-like pass
    # token itself doesn't need to leak into API payloads / logs.
    data["qr_token"] = None
    data["navigation"] = build_navigation(booking.spot) if booking.spot else None
    return data


async def qr_png(db: AsyncSession, user: User, booking_id: int) -> bytes:
    booking = await get_for_user(db, booking_id, user)
    if booking.driver_id != user.id:
        raise ForbiddenError("forbidden")
    if not booking.qr_token:
        raise NotFoundError("qr not available")
    return await asyncio.to_thread(render_qr_png, booking.qr_token)
