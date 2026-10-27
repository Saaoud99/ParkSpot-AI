from __future__ import annotations

import functools
from decimal import Decimal
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "ParkSpot AI"
    APP_VERSION: str = "0.1.0"
    ENV: Literal["dev", "test", "prod"] = "dev"
    DEBUG: bool = True
    SECRET_KEY: str = "dev-secret-key-change-me-please-32chars!!"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    DATABASE_URL: str = "sqlite+aiosqlite:///./parkspot.db"
    CORS_ORIGINS: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000"]
    CURRENCY: str = "USD"
    PLATFORM_FEE_PCT: Decimal = Decimal("0.12")
    HOLD_TTL_MINUTES: int = 10
    ARRIVAL_GRACE_MINUTES: int = 15
    NO_SHOW_MINUTES: int = 30
    MIN_BOOKING_MINUTES: int = 60
    LLAMA_BASE_URL: str = "https://api.llama.com/compat/v1/"
    LLAMA_API_KEY: str = ""
    LLAMA_MODEL: str = "Llama-3.3-70B-Instruct"
    LLAMA_TIMEOUT_SECONDS: float = 30.0
    LLAMA_MAX_TOOL_ROUNDS: int = 6
    LLAMA_TEMPERATURE: float = 0.2
    PRICING_REFRESH_MINUTES: int = 15
    PRICING_MIN_MULTIPLIER: Decimal = Decimal("0.70")
    PRICING_MAX_MULTIPLIER: Decimal = Decimal("2.50")
    PRICING_SNAPSHOT_TTL_MINUTES: int = 30
    WEATHER_ENABLED: bool = True
    MAPBOX_ACCESS_TOKEN: str = ""
    DEMO_CENTER_LAT: float = 37.7749
    DEMO_CENTER_LNG: float = -122.4194
    VISION_MODE: Literal["simulate", "real"] = "simulate"
    VISION_DEVICE: str = "cpu"
    SAM2_MODEL_ID: str = "facebook/sam2.1-hiera-small"
    VEHICLE_AREA_THRESHOLD: float = 0.25
    VEHICLE_SCORE_THRESHOLD: float = 0.50
    EASYOCR_LANGS: list[str] = ["en"]
    DEPARTURE_EMPTY_FRAMES: int = 2
    CAMERA_SHARED_KEY: str = ""

    @field_validator("SECRET_KEY")
    @classmethod
    def _secret_min_length(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v


@functools.lru_cache
def get_settings() -> Settings:
    return Settings()
