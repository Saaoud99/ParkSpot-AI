from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.enums import PricingSource
from app.db.models.spot import ParkingSpot
from app.repositories import pricing_repo
from app.utils.money import q2
from app.utils.timeutil import round_up_quarter_hours


async def current_multiplier(db: AsyncSession, zone_key: str) -> tuple[Decimal, PricingSource, str | None]:
    snap = await pricing_repo.latest_valid(db, zone_key)
    if snap is None:
        return Decimal("1.00"), PricingSource.heuristic, None
    return Decimal(snap.multiplier), snap.source, snap.reasoning


async def quote(db: AsyncSession, spot: ParkingSpot, start: datetime, end: datetime) -> dict:
    s = get_settings()
    hours = Decimal(str(round_up_quarter_hours(end - start)))
    if spot.dynamic_pricing_enabled:
        multiplier, source, reasoning = await current_multiplier(db, spot.zone_key)
    else:
        multiplier, source, reasoning = Decimal("1.00"), PricingSource.static, None
    max_allowed = min(s.PRICING_MAX_MULTIPLIER, Decimal(spot.max_multiplier))
    multiplier = max(s.PRICING_MIN_MULTIPLIER, min(multiplier, max_allowed)) if spot.dynamic_pricing_enabled else Decimal("1.00")
    multiplier = q2(multiplier)
    base_price = q2(Decimal(spot.base_price_per_hour) * hours)
    subtotal = q2(base_price * multiplier)
    platform_fee = q2(subtotal * s.PLATFORM_FEE_PCT)
    total = q2(subtotal + platform_fee)
    return {
        "spot_id": spot.id, "start": start, "end": end, "hours": hours,
        "base_price_per_hour": q2(spot.base_price_per_hour), "multiplier": multiplier,
        "base_price": base_price, "subtotal": subtotal, "platform_fee": platform_fee, "total": total,
        "currency": spot.currency, "pricing_source": source, "reasoning": reasoning,
        "price_per_hour_now": q2(Decimal(spot.base_price_per_hour) * multiplier),
    }
