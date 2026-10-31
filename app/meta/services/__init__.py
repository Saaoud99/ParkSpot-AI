"""Separate provider services. Importing this package is cheap; heavy
optional dependencies (EasyOCR/torch) are imported lazily inside methods."""
from .muse_spark import MuseSparkService
from .sam_vision import SamVisionService
from .easy_ocr import EasyOCRService
from .muse_voice import MuseVoiceService

__all__ = ["MuseSparkService", "SamVisionService", "EasyOCRService", "MuseVoiceService"]
