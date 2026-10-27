from __future__ import annotations

from app.core.config import get_settings
from app.vision.simulator import SimulatedDetector, SimulatedPlateReader

_detector = None
_reader = None


def get_detector():  # type: ignore[no-untyped-def]
    global _detector
    if _detector is not None:
        return _detector
    s = get_settings()
    if s.VISION_MODE == "real":
        try:
            from app.vision.sam2_detector import Sam2VehicleDetector

            _detector = Sam2VehicleDetector()
        except Exception:
            _detector = SimulatedDetector(True)
    else:
        _detector = SimulatedDetector(True)
    return _detector


def get_plate_reader():  # type: ignore[no-untyped-def]
    global _reader
    if _reader is not None:
        return _reader
    s = get_settings()
    if s.VISION_MODE == "real":
        try:
            from app.vision.easyocr_reader import EasyOcrPlateReader

            _reader = EasyOcrPlateReader()
        except Exception:
            _reader = SimulatedPlateReader(None)
    else:
        _reader = SimulatedPlateReader(None)
    return _reader


def vision_status() -> dict:
    s = get_settings()
    return {"mode": s.VISION_MODE, "device": s.VISION_DEVICE, "detector_loaded": _detector is not None or s.VISION_MODE == "simulate", "ocr_loaded": _reader is not None or s.VISION_MODE == "simulate"}
