from __future__ import annotations

import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)
_scheduler = None


def start_scheduler() -> None:
    global _scheduler
    s = get_settings()
    if s.ENV == "test":
        return
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        from app.workers.booking_jobs import auto_complete, expire_holds, mark_no_shows
        from app.workers.pricing_jobs import refresh_all_zones

        _scheduler = AsyncIOScheduler()
        _scheduler.add_job(expire_holds, "interval", seconds=60, id="expire_holds")
        _scheduler.add_job(mark_no_shows, "interval", minutes=5, id="mark_no_shows")
        _scheduler.add_job(auto_complete, "interval", minutes=5, id="auto_complete")
        _scheduler.add_job(refresh_all_zones, "interval", minutes=s.PRICING_REFRESH_MINUTES, id="refresh_pricing")
        _scheduler.start()
        logger.info("scheduler started")
    except Exception:
        logger.exception("scheduler failed to start")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
