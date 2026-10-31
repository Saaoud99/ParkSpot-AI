"""FastAPI surface for the Meta integration.

Routes (all under /api/v1/meta):
  GET  /status            public feature flags only — never secrets
  POST /assistant/chat    Muse Spark with controlled tools (auth required)
  POST /vision/analyze    SAM 3.1 + EasyOCR + booking verification (ops only)
  POST /voice/transcribe  optional voice input (auth required, off by default)

Every route requires the caller's own Supabase JWT; identity never comes
from the request body or the model. Errors are typed and never include
credentials or provider payloads.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque

from fastapi import FastAPI, File, Form, Header, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .access import AccessVerificationService
from .admin import build_admin_router
from .auth import Authenticator
from .config import Settings
from .errors import MetaError, NotConfigured, RateLimited
from .flags import FLAGS
from .geo import nearby_facilities, validate_coordinates
from .inventory import Inventory
from .metrics import METRICS, elapsed_ms
from .services import EasyOCRService, MuseSparkService, MuseVoiceService, SamVisionService
from .services.grounded import GroundedAssistant
from .tools import ToolExecutor

log = logging.getLogger("parkspot.meta.api")

settings = Settings.from_env()
auth = Authenticator(settings)
inventory = Inventory(settings)
muse = MuseSparkService(settings)
grounded = GroundedAssistant()
sam = SamVisionService(settings)
ocr = EasyOCRService(settings)
voice = MuseVoiceService(settings)
access_svc = AccessVerificationService(sam, ocr, inventory)

app = FastAPI(title="ParkSpot AI — Meta integration", version="1.0.0")

# The web app (different port/host, incl. LAN IPs like 10.1.19.4) calls this
# API cross-origin; without CORS the browser blocks every response.
# Auth is via Bearer JWT (no cookies), so a permissive dev default is safe;
# tighten with META_CORS_ORIGINS (comma-separated) in production.
import os as _os
_cors = [o.strip() for o in _os.environ.get("META_CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors or ["*"],
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(build_admin_router(settings, auth))

# --- tiny in-memory per-user rate limiter (per process; swap for Redis in prod)
_hits: dict[str, deque[float]] = defaultdict(deque)
_hits_lock = asyncio.Lock()


async def _rate_limit(key: str) -> None:
    now = time.monotonic()
    async with _hits_lock:
        q = _hits[key]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= settings.rate_limit_per_minute:
            raise RateLimited("Too many requests. Please wait a moment and try again.")
        q.append(now)


@app.exception_handler(MetaError)
async def _meta_error_handler(_req: Request, exc: MetaError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message}})


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=2000)


class ChatCoords(BaseModel):
    lat: float
    lng: float


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=12)
    lang: str = Field(default="en", pattern="^(en|ar|fr)$")
    coords: ChatCoords | None = None  # device GPS from the client; the model never supplies this


@app.get("/api/v1/meta/status")
async def status() -> dict:
    return settings.public_status()


@app.post("/api/v1/meta/assistant/chat")
async def assistant_chat(body: ChatRequest, authorization: str | None = Header(default=None)) -> dict:
    caller = await auth.require_user(authorization)
    await _rate_limit(f"chat:{caller.user_id}")
    if not FLAGS.get("assistant"):
        raise NotConfigured("The AI assistant is disabled by an administrator.")
    coords = None
    if body.coords:
        validate_coordinates(body.coords.lat, body.coords.lng)
        coords = (body.coords.lat, body.coords.lng)
    executor = ToolExecutor(inventory, caller.jwt, coords=coords)
    started = time.perf_counter()
    messages = [m.model_dump() for m in body.messages]
    if not settings.muse_configured:
        # Always-available mode: deterministic answers from real inventory,
        # honestly labeled — never presented as Muse Spark output.
        result = await grounded.ask(messages=messages, executor=executor, lang=body.lang)
        METRICS.record("grounded_assistant", True, elapsed_ms(started))
        log.info("assistant chat (grounded) user=%s facilities=%d", caller.user_id, len(result["facilities"]))
        return result
    try:
        result = await muse.ask(messages=messages, executor=executor, lang=body.lang)
    except MetaError as e:
        # Provider failed: degrade to the grounded mode and say so in the
        # response (mode field) instead of leaving the driver with an error.
        METRICS.record("muse_spark", False, elapsed_ms(started), str(e)[:120])
        log.warning("muse unavailable (%s) — grounded fallback for user=%s", e.code, caller.user_id)
        result = await grounded.ask(messages=messages, executor=ToolExecutor(inventory, caller.jwt, coords=coords), lang=body.lang)
        METRICS.record("grounded_assistant", True, elapsed_ms(started))
        return result
    result = {**result, "mode": "meta"}
    METRICS.record("muse_spark", True, elapsed_ms(started))
    log.info("assistant chat user=%s facilities=%d", caller.user_id, len(result["facilities"]))
    return result


@app.post("/api/v1/meta/vision/analyze")
async def vision_analyze(image: UploadFile = File(...), facility_id: str | None = Form(default=None),
                         camera_id: str | None = Form(default=None), simulated: bool = Form(default=False),
                         authorization: str | None = Header(default=None)) -> dict:
    caller = await auth.require_ops(authorization)
    await _rate_limit(f"vision:{caller.user_id}")
    if not FLAGS.get("vision"):
        raise NotConfigured("Camera vision is disabled by an administrator.")
    # Bounded read: never load an unbounded upload into memory.
    data = await image.read(settings.max_image_bytes + 1)
    started = time.perf_counter()
    try:
        result = await access_svc.analyze(image=data, content_type=image.content_type or "image/jpeg",
                                          user_jwt=caller.jwt, facility_id=facility_id)
    except Exception as e:
        METRICS.record("sam", False, elapsed_ms(started), str(e)[:120])
        raise
    METRICS.record("sam", True, elapsed_ms(started))
    if result.get("ocr_accepted"):
        METRICS.record("easyocr", True, 0)
    result["source"] = "simulated" if simulated else "camera"
    # Record the camera event (best-effort; analysis never fails because logging did).
    await inventory.insert("camera_events", {
        "camera_id": camera_id, "facility_id": facility_id, "kind": "access_check",
        "ocr_confidence": result.get("ocr_confidence"), "access_result": result.get("access"),
        "simulated": simulated,
    }, caller.jwt)
    log.info("vision analyze user=%s vehicles=%s ocr_accepted=%s access=%s",
             caller.user_id, result["vehicles_detected"], result["ocr_accepted"], result["access"])
    return result


@app.get("/api/v1/meta/spots/nearby")
async def spots_nearby(lat: float, lng: float, radius_km: float | None = None,
                       authorization: str | None = Header(default=None)) -> dict:
    """Real facilities near GPS coordinates, sorted by actual distance.

    Coordinates are used only for this search — never stored or logged.
    """
    caller = await auth.require_user(authorization)
    await _rate_limit(f"nearby:{caller.user_id}")
    validate_coordinates(lat, lng)
    radius = radius_km if radius_km is not None else settings.nearby_default_radius_km
    rows = await inventory.all_facilities(caller.jwt)
    found = nearby_facilities(rows, lat=lat, lng=lng, radius_km=radius,
                                max_radius_km=settings.nearby_max_radius_km)
    return {"facilities": found, "radius_km": min(radius, settings.nearby_max_radius_km), "count": len(found)}


@app.post("/api/v1/voice/transcribe")
@app.post("/api/v1/meta/voice/transcribe")
async def voice_transcribe(audio: UploadFile = File(...), language: str = Form(default="ar"),
                           authorization: str | None = Header(default=None)) -> dict:
    caller = await auth.require_user(authorization)
    await _rate_limit(f"voice:{caller.user_id}")
    if not FLAGS.get("voice"):
        raise NotConfigured("Voice input is disabled by an administrator.")
    data = await audio.read(settings.audio_upload_limit_bytes + 1)
    started = time.perf_counter()
    try:
        result = await voice.transcribe(data, audio.content_type or "audio/webm", language)
    except Exception as e:
        METRICS.record("muse_voice", False, elapsed_ms(started), str(e)[:120])
        raise
    METRICS.record("muse_voice", True, elapsed_ms(started))
    log.info("voice transcribe user=%s lang=%s chars=%d", caller.user_id, language, len(result["text"]))
    return result
