"""Access verification: SAM locates, EasyOCR reads, the DATABASE decides.

A vehicle is "verified" only when a confidently-read plate matches a real
booking row visible to the caller under RLS. Segmentation confidence or an
uncertain OCR read can never grant access on their own — those outcomes are
reported as diagnostics for a human operator, not as decisions.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .inventory import Inventory, _normalize_plate
from .services.easy_ocr import EasyOCRService, normalize_plate
from .services.sam_vision import SamVisionService, best_plate_region


class AccessVerificationService:
    def __init__(self, sam: SamVisionService, ocr: EasyOCRService, inventory: Inventory):
        self._sam = sam
        self._ocr = ocr
        self._inv = inventory

    async def analyze(self, *, image: bytes, content_type: str, user_jwt: str,
                      facility_id: str | None = None) -> dict:
        SamVisionService.validate_image(image, max_bytes=self._sam._s.max_image_bytes)
        detections = await self._sam.segment_vehicles(image, content_type)
        vehicles = [d for d in detections if "plate" not in d["label"].lower()]
        region = best_plate_region(detections)
        ocr = await self._ocr.read_plate(image, region["box"] if region else None)

        result: dict = {
            "vehicles_detected": len(vehicles),
            "detections": detections,
            "plate_region_found": region is not None,
            "plate": ocr["plate"] if ocr["accepted"] else None,
            "ocr_confidence": ocr["confidence"],
            "ocr_accepted": ocr["accepted"],
            "verified_booking": None,
            "access": "not_granted",
        }
        if not ocr["accepted"] or not ocr["plate"]:
            result["reason"] = "plate_not_read_confidently"
            return result

        bookings = await self._inv.bookings_for_plate(_normalize_plate(ocr["plate"]), user_jwt)
        now = datetime.now(timezone.utc)
        active = None
        for b in bookings:
            if facility_id and str(b.get("facility_id")) != facility_id:
                continue
            try:
                start = datetime.fromisoformat(str(b["start_at"]).replace("Z", "+00:00"))
                end = datetime.fromisoformat(str(b["end_at"]).replace("Z", "+00:00"))
            except (KeyError, ValueError):
                continue
            if b.get("status") in {"confirmed", "active", None} and start <= now <= end:
                active = b
                break
        if active:
            result["verified_booking"] = {
                "booking_id": active["id"], "facility_id": active["facility_id"],
                "start_at": active["start_at"], "end_at": active["end_at"],
            }
            result["access"] = "booking_verified"  # DB truth, not an AI prediction
        else:
            result["reason"] = "no_active_booking_for_plate"
        return result
