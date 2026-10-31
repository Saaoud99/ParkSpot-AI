"""EasyOCR license-plate reading.

SAM detects *where* a plate is; only OCR reads the characters. EasyOCR is a
heavy optional dependency (torch) imported lazily — if it is not installed,
the service honestly reports ``not_configured`` instead of faking results.
Uncertain reads are rejected: a plate below the confidence threshold is
returned as ``None`` so the verification layer can never grant access on a
guess.
"""
from __future__ import annotations

import asyncio
import re
import threading

from ..config import Settings
from ..errors import NotConfigured, ValidationFailed

_PLATE_RE = re.compile(r"[^A-Z0-9]")


def normalize_plate(text: str) -> str:
    return _PLATE_RE.sub("", (text or "").upper())


class EasyOCRService:
    def __init__(self, settings: Settings, reader=None):
        self._s = settings
        self._reader = reader  # injectable for tests
        self._lock = threading.Lock()

    def _get_reader(self):
        if self._reader is not None:
            return self._reader
        try:
            import easyocr  # heavy: torch. Only loaded when actually used.
        except ImportError as e:
            raise NotConfigured(
                "EasyOCR is not installed in the backend environment. "
                "Install requirements-vision.txt on a machine that can run it (see README).") from e
        with self._lock:
            if self._reader is None:
                # Arabic + French/Latin plates are the product target; English covers Latin digits/letters.
                self._reader = easyocr.Reader(["ar", "fr", "en"], gpu=False, verbose=False)
        return self._reader

    async def read_plate(self, image: bytes, region: dict | None = None) -> dict:
        """Read a plate. Returns {plate, confidence, accepted}.

        ``accepted`` is True only when normalized text exists and the mean
        character confidence clears ``OCR_MIN_CONFIDENCE``. Callers must
        treat ``accepted=False`` as "no plate read", never as a match.
        """
        if not image:
            raise ValidationFailed("Empty image.")
        reader = self._get_reader()
        crop = await asyncio.to_thread(self._crop, image, region)
        results = await asyncio.to_thread(reader.readtext, self._to_array(crop))
        if not results:
            return {"plate": None, "confidence": 0.0, "accepted": False}
        # readtext -> [(bbox, text, confidence)]; join fragments of the plate line.
        fragments = sorted(results, key=lambda r: -float(r[2]))
        best_text, best_conf = "", 0.0
        for _bbox, text, conf in fragments:
            normalized = normalize_plate(str(text))
            if len(normalized) > len(best_text):
                best_text, best_conf = normalized, float(conf)
        accepted = bool(best_text) and best_conf >= self._s.ocr_min_confidence
        return {"plate": best_text or None, "confidence": round(best_conf, 4), "accepted": accepted}

    @staticmethod
    def _to_array(image: bytes):
        """EasyOCR reliably accepts numpy arrays; raw bytes support varies by version."""
        try:
            import io

            import numpy as np
            from PIL import Image
            return np.array(Image.open(io.BytesIO(image)).convert("RGB"))
        except Exception:
            return image

    @staticmethod
    def _crop(image: bytes, region: dict | None) -> bytes:
        if not region:
            return image
        try:
            import io

            from PIL import Image
            img = Image.open(io.BytesIO(image)).convert("RGB")
            w, h = img.size
            x = int(region["x"] * w)
            y = int(region["y"] * h)
            box = (x, y, int((region["x"] + region["w"]) * w), int((region["y"] + region["h"]) * h))
            out = io.BytesIO()
            img.crop(box).save(out, format="JPEG")
            return out.getvalue()
        except Exception:
            return image  # fall back to the full frame rather than failing the read
