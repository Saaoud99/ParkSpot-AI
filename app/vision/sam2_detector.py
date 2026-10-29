from __future__ import annotations

import numpy as np

from app.core.config import get_settings
from app.vision.base import VehicleDetection


class Sam2VehicleDetector:
    """Real SAM 2 vehicle-presence detector.

    Loads the SAM 2 image predictor from the configured checkpoint. If the
    `sam2` package / weights are unavailable this raises at construction —
    real mode must never fall back to a heuristic or the simulator and
    present its output as SAM 2 segmentation.
    """

    name = "sam2"

    def __init__(self) -> None:
        # Lazy imports: only required in VISION_MODE=real.
        import torch  # noqa: F401

        self._settings = get_settings()
        self._predictor = self._load_predictor()

    def _load_predictor(self):  # type: ignore[no-untyped-def]
        try:
            from sam2.build_sam import build_sam2
            from sam2.sam2_image_predictor import SAM2ImagePredictor
        except ImportError as exc:
            raise RuntimeError(
                "sam2 package not installed — install requirements-vision.txt and configure the SAM 2 checkpoint for VISION_MODE=real"
            ) from exc
        # Checkpoint/config resolution is deployment-specific; building the
        # predictor here is the honest integration point. Without a usable
        # checkpoint, construction fails instead of faking detections.
        model_id = self._settings.SAM2_MODEL_ID
        try:
            return SAM2ImagePredictor.from_pretrained(model_id)  # type: ignore[attr-defined]
        except Exception as exc:
            raise RuntimeError(f"could not load SAM 2 weights '{model_id}': {exc}") from exc

    def detect(self, image_rgb: np.ndarray, roi: tuple[int, int, int, int]) -> VehicleDetection:
        if self._predictor is None:
            raise RuntimeError("SAM 2 predictor is not loaded")
        x1, y1, x2, y2 = roi
        crop = image_rgb[y1:y2, x1:x2]
        if crop.size == 0:
            return VehicleDetection(False, None, 0.0, 0.0)
        self._predictor.set_image(crop)
        # Prompt SAM 2 with the full ROI box; the largest resulting mask is
        # treated as the vehicle candidate. SAM 2 segments — it does not
        # classify or read plates; OCR + backend matching happen later.
        masks, scores, _ = self._predictor.predict(box=np.array([0, 0, crop.shape[1], crop.shape[0]]), multimask_output=True)
        if masks is None or len(masks) == 0:
            return VehicleDetection(False, None, 0.0, 0.0)
        areas = [float(m.mean()) for m in masks]
        best = int(np.argmax(areas))
        area = areas[best]
        conf = float(scores[best]) if scores is not None else area
        present = area > self._settings.VEHICLE_AREA_THRESHOLD and conf >= self._settings.VEHICLE_SCORE_THRESHOLD
        return VehicleDetection(present, roi if present else None, conf, area)
