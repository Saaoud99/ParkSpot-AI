from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.db.models.enums import AccessDecision, AccessSource, CameraMode


class Camera(Base, TimestampMixin):
    __tablename__ = "cameras"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    spot_id: Mapped[int] = mapped_column(ForeignKey("parking_spots.id", ondelete="CASCADE"), unique=True)
    mode: Mapped[CameraMode] = mapped_column(Enum(CameraMode, native_enum=False, length=24), default=CameraMode.simulate)
    roi: Mapped[list | None] = mapped_column(JSON, nullable=True)
    consecutive_empty_frames: Mapped[int] = mapped_column(default=0)
    last_frame_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_detected_plate: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    spot = relationship("ParkingSpot", back_populates="camera")


class AccessEvent(Base, TimestampMixin):
    __tablename__ = "access_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    spot_id: Mapped[int] = mapped_column(ForeignKey("parking_spots.id", ondelete="CASCADE"), index=True)
    booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id", ondelete="SET NULL"), nullable=True)
    camera_id: Mapped[str | None] = mapped_column(ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True)
    detected_plate: Mapped[str | None] = mapped_column(String(16), nullable=True)
    matched_plate: Mapped[str | None] = mapped_column(String(16), nullable=True)
    decision: Mapped[AccessDecision] = mapped_column(Enum(AccessDecision, native_enum=False, length=24))
    vehicle_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    plate_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[AccessSource] = mapped_column(Enum(AccessSource, native_enum=False, length=24), default=AccessSource.camera)
