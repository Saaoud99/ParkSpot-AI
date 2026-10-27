from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.booking import BookingOut
from app.schemas.spot import SpotSearchResult


class ChatLocation(BaseModel):
    lat: float
    lng: float


class ChatIn(BaseModel):
    message: str = Field(min_length=1)
    session_id: int | None = None
    location: ChatLocation | None = None
    timezone: str = "UTC"


class ToolActionOut(BaseModel):
    tool: str
    arguments: dict = {}
    ok: bool
    summary: str


class ChatResponse(BaseModel):
    session_id: int
    reply: str
    actions: list[ToolActionOut] = []
    spots: list | None = None
    booking: BookingOut | None = None
    degraded: bool = False


class ChatSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    title: str | None = None
    created_at: datetime


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    session_id: int
    role: str
    content: str
    created_at: datetime
