from __future__ import annotations

from app.core.config import get_settings
from app.core.exceptions import UpstreamError
from app.vision.simulator import SimulatedDetector, SimulatedPlateReader

_detector = None
_reader = None
_load_error: str | None = None


def get_detector():  # type: ignore[no-untyped-def]
    global _detector, _load_error
    if _detector is not None:
        return _detector
    s = get_settings()
    if s.VISION_MODE == "real":
        try:
            from app.vision.sam2_detector import Sam2VehicleDetector

            _detector = Sam2VehicleDetector()
        except Exception as exc:
            # Real mode must fail loudly — never silently substitute the
            # simulator and present simulated detections as camera output.
            _load_error = f"SAM 2 detector unavailable: {exc}"
            raise UpstreamError(_load_error, code="vision_unavailable") from exc
    else:
        _detector = SimulatedDetector(True)
    return _detector


def get_plate_reader():  # type: ignore[no-untyped-def]
    global _reader, _load_error
    if _reader is not None:
        return _reader
    s = get_settings()
    if s.VISION_MODE == "real":
        try:
            from app.vision.easyocr_reader import EasyOcrPlateReader

            _reader = EasyOcrPlateReader()
        except Exception as exc:
            _load_error = f"EasyOCR reader unavailable: {exc}"
            raise UpstreamError(_load_error, code="vision_unavailable") from exc
    else:
        _reader = SimulatedPlateReader(None)
    return _reader


def vision_status() -> dict:
    s = get_settings()
    return {
        "mode": s.VISION_MODE,
        "device": s.VISION_DEVICE,
        "detector": getattr(_detector, "name", None) or ("simulated" if s.VISION_MODE == "simulate" else None),
        "ocr": getattr(_reader, "name", None) or ("simulated" if s.VISION_MODE == "simulate" else None),
        "detector_loaded": _detector is not None or s.VISION_MODE == "simulate",
        "ocr_loaded": _reader is not None or s.VISION_MODE == "simulate",
        "load_error": _load_error,
        "note": (
            "Simulation mode: detections and plate reads are synthetic; backend reservation matching still decides every grant."
            if s.VISION_MODE == "simulate"
            else "Real mode: SAM 2 vehicle segmentation + EasyOCR plate read; backend reservation matching decides every grant."
        ),
    }
