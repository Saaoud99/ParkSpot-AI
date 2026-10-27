from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.db.models.enums import PricingSource


class PricingSnapshot(Base, TimestampMixin):
    __tablename__ = "pricing_snapshots"
    __table_args__ = (Index("ix_snapshot_zone_time", "zone_key", "computed_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    zone_key: Mapped[str] = mapped_column(String(24), index=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    multiplier: Mapped[Decimal] = mapped_column(Numeric(4, 2))
    demand_score: Mapped[float] = mapped_column(Float, default=0.0)
    weather_factor: Mapped[float] = mapped_column(Float, default=0.0)
    event_factor: Mapped[float] = mapped_column(Float, default=0.0)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[PricingSource] = mapped_column(Enum(PricingSource, native_enum=False, length=24), default=PricingSource.heuristic)
    model_name: Mapped[str | None] = mapped_column(String(80), nullable=True)


class CityEvent(Base, TimestampMixin):
    __tablename__ = "city_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    radius_km: Mapped[float] = mapped_column(Float, default=1.5)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expected_attendance: Mapped[int | None] = mapped_column(Integer, nullable=True)
