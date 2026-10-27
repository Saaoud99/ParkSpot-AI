from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SimulateIn(BaseModel):
    camera_id: str
    event: str = Field(pattern="^(arrival|departure)$")
    plate: str | None = None


class AccessDecisionOut(BaseModel):
    camera_id: str | None = None
    spot_id: int
    decision: str
    detected_plate: str | None = None
    matched_booking_id: int | None = None
    vehicle_confidence: float = 0.0
    plate_confidence: float = 0.0
    spot_status: str
    message: str


class AccessEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    spot_id: int
    booking_id: int | None = None
    camera_id: str | None = None
    detected_plate: str | None = None
    matched_plate: str | None = None
    decision: str
    vehicle_confidence: float
    plate_confidence: float
    source: str
    created_at: datetime


class VerifyQrIn(BaseModel):
    token: str
