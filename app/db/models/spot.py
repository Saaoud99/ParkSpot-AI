from __future__ import annotations

from datetime import time
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Enum, Float, ForeignKey, Index, Numeric, SmallInteger, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.db.models.enums import SpotStatus, SpotType, VehicleSize


class ParkingSpot(Base, TimestampMixin):
    __tablename__ = "parking_spots"
    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_spot_lat"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_spot_lng"),
        CheckConstraint("base_price_per_hour >= 0", name="ck_spot_price"),
        Index("ix_spot_lat_lng", "latitude", "longitude"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    host_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    zone_key: Mapped[str] = mapped_column(String(24), index=True)
    spot_type: Mapped[SpotType] = mapped_column(Enum(SpotType, native_enum=False, length=24))
    is_covered: Mapped[bool] = mapped_column(Boolean, default=False)
    has_ev_charging: Mapped[bool] = mapped_column(Boolean, default=False)
    max_vehicle_size: Mapped[VehicleSize] = mapped_column(Enum(VehicleSize, native_enum=False, length=24), default=VehicleSize.standard)
    base_price_per_hour: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    dynamic_pricing_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    max_multiplier: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("2.00"))
    status: Mapped[SpotStatus] = mapped_column(Enum(SpotStatus, native_enum=False, length=24), default=SpotStatus.available, index=True)
    access_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)

    host = relationship("User", back_populates="spots")
    availability_windows = relationship("AvailabilityWindow", back_populates="spot", cascade="all, delete-orphan")
    bookings = relationship("Booking", back_populates="spot", cascade="all, delete-orphan")
    camera = relationship("Camera", back_populates="spot", uselist=False, cascade="all, delete-orphan")


class AvailabilityWindow(Base, TimestampMixin):
    __tablename__ = "availability_windows"

    id: Mapped[int] = mapped_column(primary_key=True)
    spot_id: Mapped[int] = mapped_column(ForeignKey("parking_spots.id", ondelete="CASCADE"), index=True)
    day_of_week: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    spot = relationship("ParkingSpot", back_populates="availability_windows")
