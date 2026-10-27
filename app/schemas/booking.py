from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.enums import BookingStatus, PricingSource
from app.schemas.navigation import NavigationOut
from app.schemas.spot import SpotOut


class HoldIn(BaseModel):
    spot_id: int
    start: datetime
    end: datetime
    vehicle_id: int | None = None


class ConfirmIn(BaseModel):
    payment_method: str = "mock_card"


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    driver_id: int
    spot_id: int
    vehicle_id: int | None = None
    vehicle_plate: str
    start_time: datetime
    end_time: datetime
    status: BookingStatus
    hold_expires_at: datetime | None = None
    hours: Decimal
    base_price_per_hour: Decimal
    multiplier: Decimal
    base_price: Decimal
    subtotal: Decimal
    platform_fee: Decimal
    total_price: Decimal
    currency: str
    pricing_source: PricingSource
    checked_in_at: datetime | None = None
    checked_out_at: datetime | None = None
    cancelled_at: datetime | None = None
    created_at: datetime
    spot: SpotOut | None = None
    qr_url: str | None = None
    qr_token: str | None = None
    navigation: NavigationOut | None = None
