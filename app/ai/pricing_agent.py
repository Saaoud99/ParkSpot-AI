from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

import httpx
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llama_client import chat_json
from app.ai.prompts import PRICING_SYSTEM_PROMPT
from app.core.config import get_settings
from app.db.models.booking import Booking
from app.db.models.enums import BookingStatus, PricingSource, SpotStatus
from app.db.models.pricing import CityEvent, PricingSnapshot
from app.repositories import pricing_repo, spot_repo
from app.utils.geo import haversine_km
from app.utils.money import q2
from app.utils.timeutil import utcnow


class PricingDecision(BaseModel):
    model_config = ConfigDict(extra="ignore")
    multiplier: Decimal
    demand_score: float
    reasoning: str


@dataclass(slots=True)
class ZoneContext:
    zone_key: str
    supply: int = 0
    bookings_next_24h: int = 0
    occupancy_now: float = 0.0
    avg_lead_time_hours: float = 0.0
    hour_local: int = 0
    weekday: int = 0
    weather_factor: float = 0.0
    event_factor: float = 0.0
    lat: float = 0.0
    lng: float = 0.0

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}  # type: ignore


async def _weather_factor(lat: float, lng: float) -> float:
    s = get_settings()
    if not s.WEATHER_ENABLED:
        return 0.0
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("https://api.open-meteo.com/v1/forecast", params={
                "latitude": lat, "longitude": lng, "hourly": "temperature_2m,precipitation_probability", "forecast_days": 1})
            resp.raise_for_status()
            probs = resp.json().get("hourly", {}).get("precipitation_probability", [])[:6]
            vals = [p for p in probs if p is not None]
            return max(vals) / 100.0 if vals else 0.0
    except Exception:
        return 0.0


async def build_zone_context(db: AsyncSession, zone_key: str) -> ZoneContext:
    spots = await spot_repo.spots_in_zone(db, zone_key)
    supply = len(spots)
    lat = spots[0].latitude if spots else get_settings().DEMO_CENTER_LAT
    lng = spots[0].longitude if spots else get_settings().DEMO_CENTER_LNG
    now = utcnow()
    occupied = sum(1 for sp in spots if sp.status == SpotStatus.occupied)
    bookings_next = (await db.execute(select(func.count(Booking.id)).where(
        Booking.spot_id.in_([s.id for s in spots]) if spots else Booking.spot_id == -1,
        Booking.start_time >= now, Booking.start_time < now + timedelta(hours=24),
        Booking.status.in_((BookingStatus.held, BookingStatus.confirmed, BookingStatus.active))))).scalar_one() if spots else 0
    recent = (await db.execute(select(Booking).where(Booking.created_at >= now - timedelta(days=7)).limit(200))).scalars().all()
    leads = [(b.start_time - b.created_at).total_seconds() / 3600 for b in recent if b.start_time and b.created_at]
    avg_lead = sum(leads) / len(leads) if leads else 0.0
    events = (await db.execute(select(CityEvent).where(CityEvent.ends_at >= now, CityEvent.starts_at <= now + timedelta(hours=12)))).scalars().all()
    event_factor = 0.0
    for ev in events:
        if haversine_km(lat, lng, ev.latitude, ev.longitude) <= ev.radius_km:
            event_factor += (ev.expected_attendance or 0) / 20000
    event_factor = min(1.0, event_factor)
    weather = await _weather_factor(lat, lng)
    return ZoneContext(zone_key=zone_key, supply=supply, bookings_next_24h=int(bookings_next),
                       occupancy_now=(occupied / supply if supply else 0.0), avg_lead_time_hours=round(avg_lead, 2),
                       hour_local=now.hour, weekday=now.weekday(), weather_factor=weather, event_factor=event_factor, lat=lat, lng=lng)


def heuristic_multiplier(ctx: ZoneContext) -> tuple[Decimal, float, str]:
    s = get_settings()
    rush = ctx.hour_local in (7, 8, 9, 16, 17, 18)
    demand = 0.5 * ctx.occupancy_now + 0.3 * min(1.0, ctx.bookings_next_24h / max(1, ctx.supply)) + 0.2 * (1 if rush else 0)
    night = 0.2 if 0 <= ctx.hour_local < 6 else 0.0
    mult = 1.0 + 0.6 * demand + 0.25 * ctx.weather_factor + 0.4 * ctx.event_factor - night
    mult = max(float(s.PRICING_MIN_MULTIPLIER), min(float(s.PRICING_MAX_MULTIPLIER), mult))
    reasoning = f"heuristic: demand={demand:.2f} weather={ctx.weather_factor:.2f} event={ctx.event_factor:.2f}"
    return q2(Decimal(str(mult))), demand, reasoning


async def compute_zone(db: AsyncSession, zone_key: str) -> PricingSnapshot:
    s = get_settings()
    ctx = await build_zone_context(db, zone_key)
    now = utcnow()
    source = PricingSource.heuristic
    model_name = None
    if s.LLAMA_API_KEY:
        try:
            data = await chat_json(PRICING_SYSTEM_PROMPT.format(min_mult=s.PRICING_MIN_MULTIPLIER, max_mult=s.PRICING_MAX_MULTIPLIER), json.dumps(ctx.to_dict()))
            decision = PricingDecision(**data)
            multiplier = max(s.PRICING_MIN_MULTIPLIER, min(s.PRICING_MAX_MULTIPLIER, decision.multiplier))
            demand, reasoning = decision.demand_score, decision.reasoning
            source, model_name = PricingSource.llama, s.LLAMA_MODEL
        except Exception:
            multiplier, demand, reasoning = heuristic_multiplier(ctx)
    else:
        multiplier, demand, reasoning = heuristic_multiplier(ctx)
    snap = PricingSnapshot(zone_key=zone_key, computed_at=now, valid_until=now + timedelta(minutes=s.PRICING_SNAPSHOT_TTL_MINUTES),
                           multiplier=q2(multiplier), demand_score=float(demand), weather_factor=ctx.weather_factor,
                           event_factor=ctx.event_factor, reasoning=reasoning, source=source, model_name=model_name)
    await pricing_repo.create(db, snap)
    return snap
