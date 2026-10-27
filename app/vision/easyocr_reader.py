from __future__ import annotations

import numpy as np

from app.core.config import get_settings
from app.vision.base import PlateReading
from app.vision.plates import normalize_plate


class EasyOcrPlateReader:
    name = "easyocr"

    def __init__(self) -> None:
        import easyocr  # Lazy import: only in VISION_MODE=real.

        s = get_settings()
        self._reader = easyocr.Reader(s.EASYOCR_LANGS, gpu=(s.VISION_DEVICE != "cpu"), verbose=False)

    def read(self, image_rgb: np.ndarray, bbox: tuple[int, int, int, int]) -> PlateReading:
        x1, y1, x2, y2 = bbox
        crop = image_rgb[max(0, y1):y2, max(0, x1):x2]
        if crop.size == 0:
            return PlateReading(None, 0.0, None)
        results = self._reader.readtext(crop)
        if not results:
            return PlateReading(None, 0.0, None)
        _, text, conf = max(results, key=lambda r: r[2])
        normalized = normalize_plate(text)
        return PlateReading(normalized or None, float(conf), text)
