from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CityEventIn(BaseModel):
    name: str
    latitude: float
    longitude: float
    radius_km: float = 1.5
    starts_at: datetime
    ends_at: datetime
    expected_attendance: int | None = None


class CityEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    latitude: float
    longitude: float
    radius_km: float
    starts_at: datetime
    ends_at: datetime
    expected_attendance: int | None = None


class AdminStats(BaseModel):
    users: int
    hosts: int
    spots: int
    cameras: int
    bookings_by_status: dict[str, int]
    revenue_total: str
    platform_fees_total: str
    occupancy_rate: float
