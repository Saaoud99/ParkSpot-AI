from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.enums import SpotStatus, SpotType, VehicleSize


class AvailabilityWindowIn(BaseModel):
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    start_time: time
    end_time: time


class AvailabilityWindowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    spot_id: int
    day_of_week: int | None = None
    start_time: time
    end_time: time


class SpotCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str | None = None
    address: str = Field(min_length=1, max_length=255)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    spot_type: SpotType
    is_covered: bool = False
    has_ev_charging: bool = False
    max_vehicle_size: VehicleSize = VehicleSize.standard
    base_price_per_hour: Decimal = Field(ge=0)
    total_capacity: int = Field(default=1, ge=0, le=100000)
    authorized_capacity: int = Field(default=1, ge=0, le=100000)
    dynamic_pricing_enabled: bool = True
    max_multiplier: Decimal = Decimal("2.00")
    access_instructions: str | None = None


class SpotUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    address: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    spot_type: SpotType | None = None
    is_covered: bool | None = None
    has_ev_charging: bool | None = None
    max_vehicle_size: VehicleSize | None = None
    base_price_per_hour: Decimal | None = Field(default=None, ge=0)
    total_capacity: int | None = Field(default=None, ge=0, le=100000)
    authorized_capacity: int | None = Field(default=None, ge=0, le=100000)
    dynamic_pricing_enabled: bool | None = None
    max_multiplier: Decimal | None = None
    access_instructions: str | None = None
    status: SpotStatus | None = None
    is_published: bool | None = None


class SpotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    host_id: int
    title: str
    description: str | None = None
    address: str
    latitude: float
    longitude: float
    zone_key: str
    spot_type: SpotType
    is_covered: bool
    has_ev_charging: bool
    max_vehicle_size: VehicleSize
    base_price_per_hour: Decimal
    total_capacity: int = 1
    authorized_capacity: int = 1
    currency: str
    dynamic_pricing_enabled: bool
    max_multiplier: Decimal
    status: SpotStatus
    access_instructions: str | None = None
    is_published: bool
    created_at: datetime


class SpotDetailOut(SpotOut):
    host_name: str = ""
    availability_windows: list[AvailabilityWindowOut] = []
    camera_id: str | None = None


class HostSpotOut(SpotOut):
    upcoming_bookings_count: int = 0
    earnings_total: Decimal = Decimal("0")
    camera_id: str | None = None


class SpotSearchResult(SpotOut):
    distance_km: float
    multiplier: Decimal
    price_per_hour_now: Decimal
    estimated_total: Decimal
    spaces_available: int = 0
    is_available: bool = True
