"""Environment-driven settings for the Meta integration.

No secret has a default. Missing credentials disable the corresponding
feature with a clear error instead of falling back to fake responses.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv() -> None:
    """Load `.env` into os.environ without overriding real environment vars.

    Minimal parser so the backend works with a plain
    ``uvicorn app.meta.api:app`` even when the shell never sourced `.env`.
    Values are never logged or returned anywhere.
    """
    candidates = [Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"]
    for path in candidates:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.removeprefix("export ").partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
        break


def _bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _clean(value: str | None) -> str | None:
    """Normalize an env value; template placeholders count as unset.

    A copied-but-never-filled .env (``sk-REPLACE_ME``, ``YOUR_PROJECT``)
    must disable the feature honestly instead of making the status report
    "configured" while every real call fails with a placeholder key.
    """
    if value is None:
        return None
    v = value.strip()
    if not v or "REPLACE_ME" in v or "YOUR_PROJECT" in v:
        return None
    return v


def _env(name: str) -> str | None:
    return _clean(os.environ.get(name))


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    # --- Muse Spark / Meta model API (OpenAI-compatible chat completions) ---
    # META_BASE_URL + MODEL_API_KEY follow the Meta Model API configuration
    # supplied for this project (default: https://api.meta.ai/v1).
    # MUSE_SPARK_MODEL must be the exact model identifier from Meta's docs
    # for your account. There is intentionally NO hardcoded chat model id:
    # inventing one would mean claiming an integration that may not exist.
    meta_model_api_key: str | None = None
    meta_base_url: str = "https://api.meta.ai/v1"
    muse_spark_model: str | None = None

    # --- SAM 3.1 vision (self-hosted inference service) ---
    # Meta publishes SAM 3/3.1 as open weights (facebookresearch/sam3,
    # Hugging Face facebook/sam3); there is no Meta-hosted SAM cloud API
    # key. SAM_SERVICE_URL must point at YOUR deployment of those weights
    # (see README). SAM_MODEL names the checkpoint that deployment serves.
    sam_service_url: str | None = None
    sam_model: str | None = None
    sam_service_api_key: str | None = None

    # --- Muse Voice Transcribe (optional, disabled by default) ---
    muse_voice_enabled: bool = False
    meta_voice_api_key: str | None = None
    meta_voice_base_url: str | None = None
    muse_voice_model: str | None = None
    muse_voice_max_seconds: int = 30
    muse_voice_max_upload_mb: int = 10

    # --- GPS nearby search ---
    nearby_default_radius_km: float = 5.0
    nearby_max_radius_km: float = 50.0

    # --- Inventory / auth source of truth (existing Supabase project) ---
    supabase_url: str | None = None
    supabase_publishable_key: str | None = None

    # --- Hardening knobs ---
    provider_timeout_s: float = 30.0
    provider_max_retries: int = 2
    max_image_bytes: int = 5 * 1024 * 1024
    ocr_min_confidence: float = 0.6
    rate_limit_per_minute: int = 30

    @classmethod
    def from_env(cls) -> "Settings":
        _load_dotenv()
        return cls(
            meta_model_api_key=_env("META_MODEL_API_KEY") or _env("MODEL_API_KEY"),
            meta_base_url=(_env("META_BASE_URL") or "https://api.meta.ai/v1").rstrip("/"),
            muse_spark_model=_env("MUSE_SPARK_MODEL"),
            sam_service_url=(_env("SAM_SERVICE_URL") or "").rstrip("/") or None,
            sam_model=_env("SAM_MODEL"),
            sam_service_api_key=_env("SAM_SERVICE_API_KEY"),
            muse_voice_enabled=_bool("MUSE_VOICE_ENABLED", False),
            meta_voice_api_key=_env("META_VOICE_API_KEY") or _env("MODEL_API_KEY"),
            meta_voice_base_url=(_env("META_VOICE_BASE_URL") or "https://api.meta.ai/v1").rstrip("/"),
            muse_voice_model=_env("MUSE_VOICE_MODEL") or "muse-voice-transcribe-1.0",
            muse_voice_max_seconds=max(5, min(600, _int("MUSE_VOICE_MAX_SECONDS", 30))),
            muse_voice_max_upload_mb=max(1, min(32, _int("MUSE_VOICE_MAX_UPLOAD_MB", 10))),
            nearby_default_radius_km=_float("NEARBY_SEARCH_DEFAULT_RADIUS_KM", 5.0),
            nearby_max_radius_km=_float("NEARBY_SEARCH_MAX_RADIUS_KM", 50.0),
            supabase_url=(_env("SUPABASE_URL") or "").rstrip("/") or None,
            supabase_publishable_key=_env("SUPABASE_PUBLISHABLE_KEY"),
            provider_timeout_s=_float("META_TIMEOUT_S", 30.0),
            provider_max_retries=_int("META_MAX_RETRIES", 2),
            ocr_min_confidence=_float("OCR_MIN_CONFIDENCE", 0.6),
            rate_limit_per_minute=_int("META_RATE_LIMIT_PER_MINUTE", 30),
        )

    @property
    def muse_configured(self) -> bool:
        return bool(self.meta_model_api_key and self.muse_spark_model)

    @property
    def audio_upload_limit_bytes(self) -> int:
        """Single source of truth for the voice upload cap.

        The API read bound and the service size check both derive from
        ``muse_voice_max_upload_mb`` so they can never drift apart.
        """
        return self.muse_voice_max_upload_mb * 1024 * 1024

    @property
    def sam_configured(self) -> bool:
        # A model id or other token pasted here is not a service: SAM lives
        # behind an http(s) inference URL or it is not configured at all.
        return bool(self.sam_service_url and self.sam_service_url.startswith(("http://", "https://")))

    @property
    def voice_configured(self) -> bool:
        return bool(self.muse_voice_enabled and self.meta_voice_api_key and self.meta_voice_base_url and self.muse_voice_model)

    def public_status(self) -> dict:
        """Feature flags safe to expose to the frontend (never secrets —
        key presence is reported as a boolean only, to aid setup)."""
        return {
            "assistant": "meta" if self.muse_configured else "grounded_fallback",
            "vision_sam": "configured" if self.sam_configured else "unconfigured",
            "voice": "enabled" if self.voice_configured else "disabled",
            "voice_flag_on": self.muse_voice_enabled,
            "voice_key_present": bool(self.meta_voice_api_key),
            "voice_max_seconds": self.muse_voice_max_seconds,
            "voice_max_upload_mb": self.muse_voice_max_upload_mb,
        }
