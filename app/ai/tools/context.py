from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.user import User


@dataclass(slots=True)
class ToolContext:
    db: AsyncSession
    user: User
    settings: Settings
    now: datetime
    timezone: str = "UTC"
    location: tuple[float, float] | None = None
