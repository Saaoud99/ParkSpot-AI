from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VehicleIn(BaseModel):
    plate: str = Field(min_length=1, max_length=16)
    make: str | None = Field(default=None, max_length=60)
    model: str | None = Field(default=None, max_length=60)
    color: str | None = Field(default=None, max_length=60)
    is_default: bool = False


class VehicleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    plate: str
    make: str | None = None
    model: str | None = None
    color: str | None = None
    is_default: bool
    created_at: datetime
