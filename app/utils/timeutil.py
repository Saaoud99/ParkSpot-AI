from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from app.core.exceptions import ValidationAppError


def utcnow() -> datetime:
    return datetime.now(UTC)


def to_utc(dt: datetime) -> datetime:
    # Datetimes round-tripped through SQLite lose tzinfo even for
    # DateTime(timezone=True) columns; stored values are always UTC,
    # so re-attach UTC instead of rejecting them. API payloads are
    # already parsed timezone-aware by Pydantic before reaching here.
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def parse_iso(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationAppError(f"invalid datetime: {value}") from exc
    return to_utc(dt)


def round_up_quarter_hours(delta: timedelta) -> float:
    minutes = delta.total_seconds() / 60.0
    return math.ceil(minutes / 15.0) * 0.25
