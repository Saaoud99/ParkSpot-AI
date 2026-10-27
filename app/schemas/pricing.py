from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.db.models.enums import PricingSource


class PriceQuote(BaseModel):
    spot_id: int
    start: datetime
    end: datetime
    hours: Decimal
    base_price_per_hour: Decimal
    multiplier: Decimal
    base_price: Decimal
    subtotal: Decimal
    platform_fee: Decimal
    total: Decimal
    currency: str
    pricing_source: PricingSource
    reasoning: str | None = None
    price_per_hour_now: Decimal | None = None


class PricingSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    zone_key: str
    computed_at: datetime
    valid_until: datetime
    multiplier: Decimal
    demand_score: float
    weather_factor: float
    event_factor: float
    reasoning: str | None = None
    source: PricingSource
    model_name: str | None = None
