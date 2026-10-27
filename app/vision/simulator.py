from __future__ import annotations

import numpy as np

from app.vision.base import PlateReading, VehicleDetection
from app.vision.plates import normalize_plate


class SimulatedDetector:
    name = "simulated"

    def __init__(self, present: bool = True) -> None:
        self.present = present

    def detect(self, image_rgb: np.ndarray, roi: tuple[int, int, int, int]) -> VehicleDetection:
        return VehicleDetection(present=self.present, bbox=roi if self.present else None, confidence=0.99, area_ratio=0.8 if self.present else 0.0)


class SimulatedPlateReader:
    name = "simulated"

    def __init__(self, plate: str | None = None) -> None:
        self.plate = plate

    def read(self, image_rgb: np.ndarray, bbox: tuple[int, int, int, int]) -> PlateReading:
        text = normalize_plate(self.plate) if self.plate else None
        return PlateReading(text=text or None, confidence=0.98 if text else 0.0, raw=self.plate)
