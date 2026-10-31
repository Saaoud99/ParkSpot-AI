"""Focused tests for the Meta integration.

Everything external is mocked at the httpx transport layer or with fake
inventory/reader objects — no test needs real credentials, and no test
claims a live integration. Run:  pytest tests/test_meta_integration.py -q
"""
from __future__ import annotations

import io
import json
import wave

import httpx
import pytest

from app.meta.config import Settings
from app.meta.errors import NotConfigured, ProviderUnavailable, ValidationFailed
from app.meta.inventory import quote_cents
from app.meta.services.easy_ocr import EasyOCRService
from app.meta.services.muse_spark import MuseSparkService
from app.meta.services.muse_voice import MuseVoiceService
from app.meta.services.sam_vision import SamVisionService
from app.meta.tools import ToolExecutor


FACILITY = {
    "id": "11111111-1111-1111-1111-111111111111", "name": "Casa Marina Parking",
    "name_ar": "موقف كازا مارينا", "city": "Casablanca", "address": "Bd Mohammed V",
    "lat": 33.59, "lng": -7.61, "price_per_hour_cents": 1200, "available": 14,
    "capacity": 120, "features": ["covered", "cctv"], "rating": 4.6, "open_24h": True,
}


class FakeInventory:
    def __init__(self, rows=None, facility=None):
        self.rows = rows if rows is not None else [FACILITY]
        self.facility = facility if facility is not None else FACILITY

    async def search_facilities(self, **kw):
        return self.rows

    async def get_facility(self, fid, user_jwt=None):
        return self.facility if fid == self.facility["id"] else None

    async def all_facilities(self, user_jwt=None):
        return self.rows


def transport(handler):
    return httpx.MockTransport(handler)


def chat_response(content=None, tool_calls=None):
    msg: dict = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return httpx.Response(200, json={"choices": [{"message": msg}]})


# ---------------------------------------------------------------- Muse Spark

@pytest.mark.asyncio
async def test_muse_not_configured_without_env():
    svc = MuseSparkService(Settings())
    with pytest.raises(NotConfigured):
        await svc.ask(messages=[{"role": "user", "content": "parking?"}], executor=ToolExecutor(FakeInventory(), "jwt"))


def configured(handler, **over):
    s = Settings(meta_model_api_key="test-key", muse_spark_model="test-model", **over)
    return MuseSparkService(s, transport=transport(handler))


@pytest.mark.asyncio
async def test_muse_tool_call_returns_only_real_facilities():
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return chat_response(tool_calls=[{
                "id": "c1", "type": "function",
                "function": {"name": "search_facilities", "arguments": json.dumps({"city": "Casablanca"})},
            }])
        return chat_response(content="Casa Marina Parking has spaces.")

    out = await configured(handler).ask(
        messages=[{"role": "user", "content": "parking in Casablanca"}],
        executor=ToolExecutor(FakeInventory(), "jwt"))
    assert out["reply"].startswith("Casa Marina")
    assert [f["id"] for f in out["facilities"]] == [FACILITY["id"]]
    assert out["facilities"][0]["price_mad_per_hour"] == 12.0  # from cents, server-side


@pytest.mark.asyncio
async def test_muse_provider_401_is_honest_error():
    svc = configured(lambda req: httpx.Response(401, json={}))
    with pytest.raises(ProviderUnavailable):
        await svc.ask(messages=[{"role": "user", "content": "hi"}], executor=ToolExecutor(FakeInventory(), "jwt"))


@pytest.mark.asyncio
async def test_muse_timeout_retries_then_reports():
    def slow(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=req)

    s = Settings(meta_model_api_key="k", muse_spark_model="m", provider_max_retries=1)
    svc = MuseSparkService(s, transport=transport(slow))
    with pytest.raises(Exception) as ei:
        await svc.ask(messages=[{"role": "user", "content": "hi"}], executor=ToolExecutor(FakeInventory(), "jwt"))
    assert ei.value.code == "provider_timeout"


# ---------------------------------------------------------------------- tools

@pytest.mark.asyncio
async def test_tool_rejects_unknown_city_and_feature():
    ex = ToolExecutor(FakeInventory(), "jwt")
    with pytest.raises(ValidationFailed):
        await ex.execute("search_facilities", {"city": "Atlantis"})
    with pytest.raises(ValidationFailed):
        await ex.execute("search_facilities", {"feature": "helicopter_pad"})


@pytest.mark.asyncio
async def test_tool_rejects_unknown_tool_and_bad_hours():
    ex = ToolExecutor(FakeInventory(), "jwt")
    with pytest.raises(ValidationFailed):
        await ex.execute("run_sql", {"query": "drop table bookings"})
    with pytest.raises(ValidationFailed):
        await ex.execute("calculate_booking_quote", {"facility_id": FACILITY["id"], "hours": 999})


@pytest.mark.asyncio
async def test_quote_is_server_side_cents_math():
    ex = ToolExecutor(FakeInventory(), "jwt")
    out = await ex.execute("calculate_booking_quote", {"facility_id": FACILITY["id"], "hours": 3})
    assert out == {"found": True, "facility_id": FACILITY["id"], "hours": 3, "total_mad": 36.0, "currency": "MAD"}
    assert quote_cents(FACILITY, 3) == 3600


@pytest.mark.asyncio
async def test_unknown_facility_is_found_false_not_invented():
    ex = ToolExecutor(FakeInventory(), "jwt")
    assert await ex.execute("get_facility_details", {"facility_id": "99999999-9999-9999-9999-999999999999"}) == {"found": False}


@pytest.mark.asyncio
async def test_nearby_tool_needs_shared_location_and_uses_real_coords():
    rows = [{**FACILITY, "id": "near-1", "lat": 33.5800, "lng": -7.5900},
            {**FACILITY, "id": "far-1", "lat": 34.0209, "lng": -6.8416}]
    no_loc = ToolExecutor(FakeInventory(rows), "jwt")
    out = await no_loc.execute("search_nearby_facilities", {})
    assert out["found"] is False and out["reason"] == "location_not_shared"  # model cannot guess GPS
    with_loc = ToolExecutor(FakeInventory(rows), "jwt", coords=(33.5731, -7.5898))
    out = await with_loc.execute("search_nearby_facilities", {"radius_km": 5})
    assert [f["id"] for f in out["facilities"]] == ["near-1"]
    assert out["facilities"][0]["distance_meters"] < 1000


# ------------------------------------------------------------------- SAM 3.1

@pytest.mark.asyncio
async def test_sam_not_configured():
    with pytest.raises(NotConfigured):
        await SamVisionService(Settings()).segment_vehicles(b"x")


@pytest.mark.asyncio
async def test_sam_parses_detections():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"detections": [
            {"label": "car", "score": 0.93, "box": {"x": 0.1, "y": 0.2, "w": 0.4, "h": 0.3}},
            {"label": "license plate", "score": 0.87, "box": {"x": 0.2, "y": 0.4, "w": 0.1, "h": 0.05}},
            {"label": "broken"},
        ]})

    svc = SamVisionService(Settings(sam_service_url="http://sam.local"), transport=transport(handler))
    out = await svc.segment_vehicles(b"jpeg-bytes")
    assert len(out) == 2 and out[0]["label"] == "car"


@pytest.mark.asyncio
async def test_sam_invalid_image_rejected_without_pillow_payloads():
    with pytest.raises(ValidationFailed):
        SamVisionService.validate_image(b"not-an-image", max_bytes=1024)


# -------------------------------------------------------------------- EasyOCR

class FakeReader:
    def __init__(self, results):
        self._results = results

    def readtext(self, _img):
        return self._results


@pytest.mark.asyncio
async def test_ocr_confident_plate_accepted():
    svc = EasyOCRService(Settings(), reader=FakeReader([((0, 0), "12345-A-6", 0.91)]))
    out = await svc.read_plate(b"img")
    assert out == {"plate": "12345A6", "confidence": 0.91, "accepted": True}


@pytest.mark.asyncio
async def test_ocr_uncertain_plate_rejected():
    svc = EasyOCRService(Settings(ocr_min_confidence=0.6), reader=FakeReader([((0, 0), "12345A6", 0.31)]))
    out = await svc.read_plate(b"img")
    assert out["accepted"] is False  # never grant access on a guess


@pytest.mark.asyncio
async def test_ocr_no_text():
    svc = EasyOCRService(Settings(), reader=FakeReader([]))
    assert (await svc.read_plate(b"img"))["plate"] is None


# ----------------------------------------------------------------------- voice

def _make_wav(seconds: float = 0.1, channels: int = 1, rate: int = 16000) -> bytes:
    """A real, parseable PCM WAV (silence) for pipeline tests."""
    frames = int(seconds * rate)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * channels * frames)
    return buf.getvalue()


def _wav_info(data: bytes) -> dict:
    with wave.open(io.BytesIO(data), "rb") as w:
        return {"channels": w.getnchannels(), "rate": w.getframerate(),
                "width": w.getsampwidth(), "frames": w.getnframes()}


WAV_BYTES = _make_wav()


@pytest.mark.asyncio
async def test_voice_disabled_by_default():
    with pytest.raises(NotConfigured):
        await MuseVoiceService(Settings()).transcribe(WAV_BYTES, "audio/wav")


@pytest.mark.asyncio
async def test_voice_rejects_unsupported_language_and_type():
    from app.meta.services.muse_voice import ensure_wav
    s = Settings(muse_voice_enabled=True, meta_voice_api_key="k")
    svc = MuseVoiceService(s)
    with pytest.raises(ValidationFailed):
        await svc.transcribe(WAV_BYTES, "audio/wav", language="darija")  # not claimed as supported
    with pytest.raises(ValidationFailed):
        await ensure_wav(b"audio", "video/mp4", 30)


@pytest.mark.asyncio
async def test_voice_wav_passthrough_and_conversion_unavailable(monkeypatch):
    import shutil

    from app.meta.services.muse_voice import ensure_wav
    assert await ensure_wav(WAV_BYTES, "audio/wav", 30) == WAV_BYTES
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    with pytest.raises(ProviderUnavailable):  # honest failure, never sends WebM as-is
        await ensure_wav(b"webm-bytes", "audio/webm", 30)


@pytest.mark.asyncio
async def test_voice_wav_duration_is_capped():
    from app.meta.services.muse_voice import ensure_wav
    out = await ensure_wav(_make_wav(seconds=2), "audio/wav", 1)
    info = _wav_info(out)
    assert info["channels"] == 1 and info["rate"] == 16000 and info["width"] == 2
    assert info["frames"] <= 16000  # ≤ 1 s at 16 kHz


@pytest.mark.asyncio
async def test_voice_nonconforming_wav_needs_ffmpeg(monkeypatch):
    import shutil

    from app.meta.services.muse_voice import ensure_wav
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    with pytest.raises(ProviderUnavailable):  # stereo 48 kHz WAV must be converted, not passed through
        await ensure_wav(_make_wav(channels=2, rate=48000), "audio/wav", 30)


@pytest.mark.asyncio
async def test_voice_invalid_wav_and_unsupported_format_rejected():
    from app.meta.services.muse_voice import ensure_wav
    with pytest.raises(ValidationFailed):  # RIFF header but unparseable body
        await ensure_wav(b"RIFF$\x00\x00\x00WAVEfmt " + b"\x00" * 32, "audio/wav", 30)
    with pytest.raises(ValidationFailed):  # not on the accepted-type list
        await ensure_wav(b"flac-bytes", "audio/flac", 30)


def test_voice_upload_limit_has_one_config_source():
    s = Settings(muse_voice_max_upload_mb=2, muse_voice_max_seconds=45)
    svc = MuseVoiceService(s)
    assert s.audio_upload_limit_bytes == svc._max_bytes == 2 * 1024 * 1024
    assert s.public_status()["voice_max_seconds"] == 45
    with pytest.raises(ValidationFailed):
        svc.validate_upload(b"x" * (2 * 1024 * 1024 + 1), "audio/webm")


@pytest.mark.asyncio
async def test_voice_transcribes_with_documented_multipart_shape():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["path"] = req.url.path
        seen["auth"] = req.headers.get("authorization")
        seen["body"] = req.content.decode("utf-8", "ignore")
        return httpx.Response(200, json={"text": "بغيت موقف في كازا"})

    s = Settings(muse_voice_enabled=True, meta_voice_api_key="k",
                 meta_voice_base_url="http://voice.local", muse_voice_model="muse-voice-transcribe-1.0")
    out = await MuseVoiceService(s, transport=transport(handler)).transcribe(WAV_BYTES, "audio/wav", language="ar")
    assert out["text"].startswith("بغيت")
    assert seen["path"] == "/asr/transcribe"
    assert seen["auth"] == "Bearer k"
    assert '"mode": "PUSH_TO_TALK"' in seen["body"]
    assert '"audioEncoding": "WAV"' in seen["body"]
    assert "k" not in out["text"]


@pytest.mark.asyncio
async def test_voice_empty_transcript_rejected():
    s = Settings(muse_voice_enabled=True, meta_voice_api_key="k", meta_voice_base_url="http://v.local")
    svc = MuseVoiceService(s, transport=transport(lambda req: httpx.Response(200, json={"text": "  "})))
    with pytest.raises(ValidationFailed):
        await svc.transcribe(WAV_BYTES, "audio/wav")


# ------------------------------------------------------------------ GPS nearby

def test_haversine_known_distance():
    from app.meta.geo import haversine_m
    # Casablanca (33.5731,-7.5898) → Rabat (34.0209,-6.8416) ≈ 84 km
    d = haversine_m(33.5731, -7.5898, 34.0209, -6.8416)
    assert 80_000 < d < 88_000


def test_nearby_sorts_filters_and_validates():
    from app.meta.geo import nearby_facilities
    rows = [
        {**FACILITY, "id": "far", "lat": 34.0209, "lng": -6.8416},
        {**FACILITY, "id": "near", "lat": 33.5800, "lng": -7.5900},
        {**FACILITY, "id": "nocoords", "lat": None, "lng": None},
    ]
    out = nearby_facilities(rows, lat=33.5731, lng=-7.5898, radius_km=5)
    assert [r["id"] for r in out] == ["near"]  # far excluded by radius, no-coords skipped
    assert out[0]["distance_meters"] < 1000
    with pytest.raises(ValidationFailed):
        nearby_facilities(rows, lat=91.0, lng=0.0, radius_km=5)
    with pytest.raises(ValidationFailed):
        nearby_facilities(rows, lat=0.0, lng=-181.0, radius_km=5)
    wide = nearby_facilities(rows, lat=33.5731, lng=-7.5898, radius_km=500, max_radius_km=50)
    assert all(r["distance_meters"] <= 50_000 for r in wide)  # radius clamped to max


# ------------------------------------------------------------------ status API

def test_status_never_exposes_secrets():
    s = Settings(meta_model_api_key="super-secret-value", muse_spark_model="m")
    status = s.public_status()
    assert "super-secret-value" not in json.dumps(status)
    assert status["assistant"] == "meta"


def test_placeholder_env_values_count_as_unconfigured(monkeypatch):
    # A copied-but-unfilled .env must not make the status claim "meta".
    monkeypatch.setenv("MODEL_API_KEY", "sk-REPLACE_ME")
    monkeypatch.setenv("MUSE_SPARK_MODEL", "some-model")
    s = Settings.from_env()
    assert s.muse_configured is False
    assert s.public_status()["assistant"] == "grounded_fallback"


def test_placeholder_supabase_values_count_as_unset(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://YOUR_PROJECT.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_REPLACE_ME")
    s = Settings.from_env()
    assert s.supabase_url is None
    assert s.supabase_publishable_key is None


def test_sam_requires_a_real_http_url():
    assert Settings(sam_service_url="LLM_2187466105533446_not-a-url").sam_configured is False
    assert Settings(sam_service_url="https://sam.internal:9000").sam_configured is True
    assert Settings(sam_service_url=None).sam_configured is False
