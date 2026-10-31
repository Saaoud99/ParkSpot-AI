"""SAM 3.1 vision service.

SAM (Segment Anything) finds *where* vehicles/plates are; it does not read
text. Meta ships SAM 3/3.1 as open weights (github.com/facebookresearch/sam3,
huggingface.co/facebook/sam3) — there is no official Meta-hosted SAM API
key, so this client talks to YOUR inference deployment at SAM_SERVICE_URL
using the de-facto SAM service contract: POST multipart image + text
prompts, receive boxes/masks/scores. Unset URL = honest not_configured.
"""
from __future__ import annotations

import asyncio
import io

import httpx

from ..config import Settings
from ..errors import (InvalidProviderResponse, NotConfigured,
                      ProviderTimeout, ProviderUnavailable, ValidationFailed)

VEHICLE_PROMPTS = ["car", "vehicle", "license plate"]


class SamVisionService:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self._s = settings
        self._transport = transport

    @staticmethod
    def validate_image(data: bytes, *, max_bytes: int) -> str:
        if not data:
            raise ValidationFailed("Empty image.")
        if len(data) > max_bytes:
            raise ValidationFailed(f"Image too large (max {max_bytes // (1024 * 1024)} MB).")
        try:
            from PIL import Image
            fmt = Image.open(io.BytesIO(data)).format
        except Exception:
            raise ValidationFailed("Unsupported or corrupt image.")
        if fmt not in {"JPEG", "PNG", "WEBP"}:
            raise ValidationFailed(f"Unsupported image format: {fmt or 'unknown'}.")
        return fmt.lower()

    async def segment_vehicles(self, image: bytes, content_type: str = "image/jpeg") -> list[dict]:
        """Return normalized detections: [{label, score, box:{x,y,w,h}}] (0..1 coords)."""
        if not self._s.sam_configured:
            raise NotConfigured(
                "SAM 3.1 is not configured. Deploy the official SAM 3.1 weights "
                "(facebookresearch/sam3) and set SAM_SERVICE_URL (see README).")
        headers = {}
        if self._s.sam_service_api_key:
            headers["Authorization"] = f"Bearer {self._s.sam_service_api_key}"
        files = {"image": ("frame.jpg", image, content_type)}
        form = {"prompts": ",".join(VEHICLE_PROMPTS)}
        if self._s.sam_model:
            form["model"] = self._s.sam_model
        last_error = ProviderUnavailable("SAM service unavailable.")
        for attempt in range(self._s.provider_max_retries + 1):
            try:
                async with httpx.AsyncClient(base_url=self._s.sam_service_url, headers=headers,
                                             timeout=self._s.provider_timeout_s, transport=self._transport) as c:
                    r = await c.post("/segment", files=files, data=form)
                if r.status_code == 200:
                    return _parse_detections(r.json())
                if r.status_code >= 500 or r.status_code == 429:
                    last_error = ProviderUnavailable(f"SAM service error (HTTP {r.status_code}).")
                else:
                    raise InvalidProviderResponse(f"SAM request failed (HTTP {r.status_code}).")
            except httpx.TimeoutException:
                last_error = ProviderTimeout("SAM service timed out.")
            except (NotConfigured, InvalidProviderResponse):
                raise
            except httpx.HTTPError:
                last_error = ProviderUnavailable("SAM service is unreachable.")
            if attempt < self._s.provider_max_retries:
                await asyncio.sleep(0.4 * (attempt + 1))
        raise last_error


def _parse_detections(payload: object) -> list[dict]:
    if not isinstance(payload, dict):
        raise InvalidProviderResponse("SAM returned an unexpected response shape.")
    raw = payload.get("detections") or payload.get("objects") or []
    if not isinstance(raw, list):
        raise InvalidProviderResponse("SAM returned malformed detections.")
    out: list[dict] = []
    for d in raw:
        if not isinstance(d, dict):
            continue
        box = d.get("box") or d.get("bbox") or {}
        try:
            item = {
                "label": str(d.get("label") or d.get("prompt") or "object")[:40],
                "score": round(float(d.get("score", 0)), 4),
                "box": {"x": float(box["x"]), "y": float(box["y"]), "w": float(box["w"]), "h": float(box["h"])},
            }
        except (KeyError, TypeError, ValueError):
            continue
        out.append(item)
    return out


def best_plate_region(detections: list[dict]) -> dict | None:
    plates = [d for d in detections if "plate" in d["label"].lower()]
    pool = plates or detections
    return max(pool, key=lambda d: d["score"]) if pool else None
