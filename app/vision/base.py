from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(slots=True)
class VehicleDetection:
    present: bool
    bbox: tuple[int, int, int, int] | None
    confidence: float
    area_ratio: float


@dataclass(slots=True)
class PlateReading:
    text: str | None
    confidence: float
    raw: str | None


class VehicleDetector(Protocol):
    name: str

    def detect(self, image_rgb: np.ndarray, roi: tuple[int, int, int, int]) -> VehicleDetection: ...


class PlateReader(Protocol):
    name: str

    def read(self, image_rgb: np.ndarray, bbox: tuple[int, int, int, int]) -> PlateReading: ...
