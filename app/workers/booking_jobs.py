from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models.booking import ACTIVE_STATUSES, Booking
from app.db.models.enums import BookingStatus, SpotStatus
from app.db.models.spot import ParkingSpot
from app.db.session import async_session_factory
from app.utils.timeutil import to_utc, utcnow

logger = logging.getLogger(__name__)


async def _recompute_spot(db, spot_id: int) -> None:
    spot = await db.get(ParkingSpot, spot_id)
    if spot is None or spot.status in (SpotStatus.unavailable, SpotStatus.occupied):
        return
    now = utcnow()
    covering = (await db.execute(select(Booking).where(Booking.spot_id == spot_id, Booking.status.in_(ACTIVE_STATUSES), Booking.start_time <= now, Booking.end_time > now))).scalars().first()
    spot.status = SpotStatus.held if covering else SpotStatus.available


async def expire_holds() -> int:
    try:
        async with async_session_factory() as db:
            now = utcnow()
            rows = (await db.execute(select(Booking).where(Booking.status == BookingStatus.held, Booking.hold_expires_at < now))).scalars().all()
            spot_ids = set()
            for b in rows:
                b.status = BookingStatus.expired
                spot_ids.add(b.spot_id)
            for sid in spot_ids:
                await _recompute_spot(db, sid)
            await db.commit()
            logger.info("expire_holds: %s", len(rows))
            return len(rows)
    except Exception:
        logger.exception("expire_holds failed")
        return 0


async def mark_no_shows() -> int:
    try:
        s = get_settings()
        async with async_session_factory() as db:
            now = utcnow()
            rows = (await db.execute(select(Booking).where(Booking.status == BookingStatus.confirmed, Booking.checked_in_at.is_(None)))).scalars().all()
            count = 0
            for b in rows:
                if to_utc(b.start_time) + timedelta(minutes=s.NO_SHOW_MINUTES) < now:
                    b.status = BookingStatus.no_show
                    count += 1
                    await _recompute_spot(db, b.spot_id)
            await db.commit()
            logger.info("mark_no_shows: %s", count)
            return count
    except Exception:
        logger.exception("mark_no_shows failed")
        return 0


async def auto_complete() -> int:
    try:
        s = get_settings()
        async with async_session_factory() as db:
            now = utcnow()
            rows = (await db.execute(select(Booking).where(Booking.status == BookingStatus.active))).scalars().all()
            count = 0
            for b in rows:
                if to_utc(b.end_time) + timedelta(minutes=s.ARRIVAL_GRACE_MINUTES) < now:
                    b.status = BookingStatus.completed
                    b.checked_out_at = now
                    spot = await db.get(ParkingSpot, b.spot_id)
                    if spot and spot.status == SpotStatus.occupied:
                        spot.status = SpotStatus.available
                    count += 1
            await db.commit()
            logger.info("auto_complete: %s", count)
            return count
    except Exception:
        logger.exception("auto_complete failed")
        return 0
