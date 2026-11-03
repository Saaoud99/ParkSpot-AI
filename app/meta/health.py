"""Health checks for the four AI integration modules.

Every probe is *safe*: HTTP reachability only, no inference, no tool
execution, no audio or image is sent, and credentials never appear in
the result. Each result carries the same shape so the dashboard can
render every card the same way::

    {
      "service": "muse_spark", "label": "Muse Spark",
      "enabled": true,            # admin switch (flags)
      "configured": true,         # env credentials / URL present
      "reachable": true | false | null,   # null = local module, nothing to reach
      "tested_ok": true,          # the probe itself passed
      "status": "ok" | "disabled" | "unconfigured" | "unreachable" | "degraded",
      "detail": "...",            # one human sentence, never a secret
      "latency_ms": 123.4 | null,
      "checked_at": "2026-11-03T10:00:00+00:00",
      "backend": {instance_id, started_at, uptime_s, version}
    }

Status precedence: ``disabled`` > ``unconfigured`` > ``unreachable`` >
``degraded`` > ``ok``. A disabled module is still probed when it is
configured, so an admin can confirm a provider is up *before* switching
it back on.
"""
from __future__ import annotations

import asyncio
import importlib.util
import shutil
import time
from datetime import datetime, timezone

import httpx

from . import runtime
from .config import Settings
from .errors import ValidationFailed
from .flags import FLAGS, LABELS, MODULES, FeatureFlags

SERVICES: tuple[str, ...] = MODULES


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def easyocr_installed() -> bool:
    return importlib.util.find_spec("easyocr") is not None


def ffmpeg_installed() -> bool:
    return shutil.which("ffmpeg") is not None


def _result(service: str, *, enabled: bool, configured: bool, reachable: bool | None,
            tested_ok: bool, detail: str, latency_ms: float | None = None, **extra) -> dict:
    if not enabled:
        status = "disabled"
    elif not configured:
        status = "unconfigured"
    elif reachable is False:
        status = "unreachable"
    elif not tested_ok:
        status = "degraded"
    else:
        status = "ok"
    return {
        "service": service, "label": LABELS[service],
        "enabled": enabled, "configured": configured, "reachable": reachable,
        "tested_ok": tested_ok, "status": status, "detail": detail,
        "latency_ms": round(latency_ms, 1) if latency_ms is not None else None,
        "checked_at": _now(), "backend": runtime.info(), **extra,
    }


async def _http_get(url: str, key: str | None, timeout: float,
                    transport: httpx.AsyncBaseTransport | None) -> tuple[int | None, float, str | None]:
    """GET ``url``; return (status_code or None, latency_ms, error_kind)."""
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout, headers=headers, transport=transport,
                                     follow_redirects=False) as client:
            r = await client.get(url)
        return r.status_code, (time.perf_counter() - started) * 1000.0, None
    except httpx.TimeoutException:
        return None, (time.perf_counter() - started) * 1000.0, "timeout"
    except httpx.HTTPError as e:
        return None, (time.perf_counter() - started) * 1000.0, e.__class__.__name__


async def _probe_meta_api(service: str, *, enabled: bool, configured: bool, base_url: str | None,
                          key: str | None, missing: str, timeout: float,
                          transport: httpx.AsyncBaseTransport | None, **extra) -> dict:
    if not configured or not base_url:
        return _result(service, enabled=enabled, configured=False, reachable=False, tested_ok=False,
                       detail=f"Not configured ({missing}).", **extra)
    code, ms, err = await _http_get(base_url.rstrip("/") + "/models", key, timeout, transport)
    if code is None:
        return _result(service, enabled=enabled, configured=True, reachable=False, tested_ok=False,
                       detail=f"Endpoint unreachable ({err}).", latency_ms=ms, **extra)
    if code in (401, 403):
        detail = f"Endpoint reachable but rejected the configured credentials (HTTP {code})."
        return _result(service, enabled=enabled, configured=True, reachable=True, tested_ok=False,
                       detail=detail, latency_ms=ms, **extra)
    ok = code == 200
    detail = (f"Endpoint responded with HTTP {code} (no inference performed)." if ok
              else f"Endpoint reachable but returned HTTP {code}.")
    return _result(service, enabled=enabled, configured=True, reachable=True, tested_ok=ok,
                   detail=detail, latency_ms=ms, **extra)


async def probe(settings: Settings, service: str, *, flags: FeatureFlags | None = None,
                transport: httpx.AsyncBaseTransport | None = None) -> dict:
    """Health-check one module. Unknown names raise ``ValidationFailed``."""
    if service not in SERVICES:
        raise ValidationFailed(f"Unknown service: {service}. Known: {', '.join(SERVICES)}.")
    flags = flags or FLAGS
    enabled = flags.get(service)
    timeout = settings.ai_health_timeout_s

    if service == "muse_spark":
        return await _probe_meta_api(
            service, enabled=enabled, configured=settings.muse_configured, base_url=settings.meta_base_url,
            key=settings.meta_model_api_key, missing="MODEL_API_KEY missing", timeout=timeout,
            transport=transport, model=settings.muse_spark_model)

    if service == "muse_voice":
        ffmpeg = ffmpeg_installed()
        if not settings.muse_voice_enabled:
            return _result(service, enabled=enabled, configured=False, reachable=False, tested_ok=False,
                           detail="Not configured (MUSE_VOICE_ENABLED is false).", ffmpeg=ffmpeg,
                           model=settings.muse_voice_model)
        res = await _probe_meta_api(
            service, enabled=enabled, configured=settings.voice_configured,
            base_url=settings.meta_voice_base_url, key=settings.meta_voice_api_key,
            missing="META_VOICE_API_KEY / MODEL_API_KEY missing", timeout=timeout,
            transport=transport, ffmpeg=ffmpeg, model=settings.muse_voice_model)
        if res["status"] == "ok" and not ffmpeg:
            # Provider is fine, but browser recordings cannot be converted.
            res["status"], res["tested_ok"] = "degraded", False
            res["detail"] += " FFmpeg is not installed: only mono 16 kHz WAV uploads will work."
        return res

    if service == "sam":
        if not settings.sam_configured:
            return _result(service, enabled=enabled, configured=False, reachable=False, tested_ok=False,
                           detail="Not configured (SAM_SERVICE_URL missing or not an http(s) URL).",
                           model=settings.sam_model)
        code, ms, err = await _http_get(settings.sam_service_url or "", settings.sam_service_api_key,
                                        timeout, transport)
        if code is None:
            return _result(service, enabled=enabled, configured=True, reachable=False, tested_ok=False,
                           detail=f"Inference service unreachable ({err}).", latency_ms=ms,
                           model=settings.sam_model)
        # A self-hosted inference server may legitimately answer GET / with
        # 404/405 — any non-5xx answer proves the service is up.
        ok = code < 500
        detail = (f"Inference service responded with HTTP {code} (no inference performed)." if ok
                  else f"Inference service reachable but failing (HTTP {code}).")
        return _result(service, enabled=enabled, configured=True, reachable=True, tested_ok=ok,
                       detail=detail, latency_ms=ms, model=settings.sam_model)

    # easyocr: local Python package, nothing to reach over the network.
    installed = await asyncio.to_thread(easyocr_installed)
    detail = ("EasyOCR package importable in this backend environment (models load on first use)."
              if installed else "EasyOCR is not installed (pip install -r requirements-vision.txt).")
    return _result(service, enabled=enabled, configured=installed, reachable=None, tested_ok=installed,
                   detail=detail, min_confidence=settings.ocr_min_confidence)


async def probe_all(settings: Settings, *, flags: FeatureFlags | None = None,
                    transport: httpx.AsyncBaseTransport | None = None) -> dict:
    """Health-check every module concurrently; never raises for one failure."""
    results = await asyncio.gather(
        *(probe(settings, s, flags=flags, transport=transport) for s in SERVICES), return_exceptions=True)
    services: dict[str, dict] = {}
    for name, res in zip(SERVICES, results):
        if isinstance(res, BaseException):
            flags_ = flags or FLAGS
            res = _result(name, enabled=flags_.get(name), configured=False, reachable=False, tested_ok=False,
                          detail=f"Health check failed ({res.__class__.__name__}).")
        services[name] = res
    counts: dict[str, int] = {}
    for res in services.values():
        counts[res["status"]] = counts.get(res["status"], 0) + 1
    if counts.get("unreachable") or counts.get("degraded"):
        overall = "degraded"
    elif counts.get("ok"):
        overall = "ok"
    else:
        overall = "inactive"  # everything disabled or unconfigured
    return {"status": overall, "counts": counts, "services": services,
            "checked_at": _now(), "backend": runtime.info()}
