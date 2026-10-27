from __future__ import annotations

import logging

from app.ai.pricing_agent import compute_zone
from app.db.models.enums import PricingSource
from app.db.session import async_session_factory
from app.repositories import spot_repo

logger = logging.getLogger(__name__)


async def refresh_all_zones() -> dict:
    zones_updated = llama_count = heuristic_count = 0
    try:
        async with async_session_factory() as db:
            zones = await spot_repo.list_zones(db)
            for zone in zones:
                snap = await compute_zone(db, zone)
                zones_updated += 1
                if snap.source == PricingSource.llama:
                    llama_count += 1
                else:
                    heuristic_count += 1
            await db.commit()
    except Exception:
        logger.exception("refresh_all_zones failed")
    return {"zones_updated": zones_updated, "llama_count": llama_count, "heuristic_count": heuristic_count}
