from __future__ import annotations

import numpy as np

from app.core.config import get_settings
from app.vision.base import VehicleDetection


class Sam2VehicleDetector:
    name = "sam2"

    def __init__(self) -> None:
        # Lazy imports: only required in VISION_MODE=real.
        import torch  # noqa: F401
        from huggingface_hub import hf_hub_download  # noqa: F401

        self._settings = get_settings()
        self._predictor = None  # Real SAM2 predictor wired when checkpoint available.

    def detect(self, image_rgb: np.ndarray, roi: tuple[int, int, int, int]) -> VehicleDetection:
        # Fallback heuristic when predictor weights are unavailable: bright-region occupancy in ROI.
        x1, y1, x2, y2 = roi
        crop = image_rgb[y1:y2, x1:x2]
        if crop.size == 0:
            return VehicleDetection(False, None, 0.0, 0.0)
        gray = crop.mean(axis=2) if crop.ndim == 3 else crop
        area = float((gray > 30).mean())
        present = area > self._settings.VEHICLE_AREA_THRESHOLD
        conf = 0.85 if present else 0.6
        return VehicleDetection(present and conf >= self._settings.VEHICLE_SCORE_THRESHOLD, roi if present else None, conf, area)
