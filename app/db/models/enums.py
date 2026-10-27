from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    driver = "driver"
    host = "host"
    admin = "admin"


class SpotType(str, enum.Enum):
    driveway = "driveway"
    garage = "garage"
    lot = "lot"
    street = "street"


class VehicleSize(str, enum.Enum):
    compact = "compact"
    standard = "standard"
    large = "large"
    oversized = "oversized"


class SpotStatus(str, enum.Enum):
    available = "available"
    held = "held"
    occupied = "occupied"
    unavailable = "unavailable"


class BookingStatus(str, enum.Enum):
    held = "held"
    confirmed = "confirmed"
    active = "active"
    completed = "completed"
    cancelled = "cancelled"
    expired = "expired"
    no_show = "no_show"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    succeeded = "succeeded"
    refunded = "refunded"
    failed = "failed"


class PricingSource(str, enum.Enum):
    llama = "llama"
    heuristic = "heuristic"
    static = "static"


class CameraMode(str, enum.Enum):
    simulate = "simulate"
    real = "real"


class AccessDecision(str, enum.Enum):
    granted = "granted"
    denied = "denied"
    departure = "departure"
    no_vehicle = "no_vehicle"


class AccessSource(str, enum.Enum):
    camera = "camera"
    qr = "qr"
    simulated = "simulated"


class ChatRole(str, enum.Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"
