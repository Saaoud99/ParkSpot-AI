"""GPS nearby search over REAL facility coordinates.

Haversine great-circle distance; results are filtered to the requested
radius and sorted by actual distance. Only rows from the real inventory
(contracted ParkSpot facilities, read under the caller's RLS) are ever
considered — coordinates are never invented, and the caller's precise
location is used for this computation only (never stored or logged).
"""
from __future__ import annotations

import math

from .errors import ValidationFailed

EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def validate_coordinates(lat: float, lng: float) -> None:
    if not (-90.0 <= lat <= 90.0):
        raise ValidationFailed("Latitude must be between -90 and 90.")
    if not (-180.0 <= lng <= 180.0):
        raise ValidationFailed("Longitude must be between -180 and 180.")


def nearby_facilities(rows: list[dict], *, lat: float, lng: float,
                      radius_km: float, max_radius_km: float = 50.0,
                      limit: int = 20) -> list[dict]:
    """Filter real facility rows to radius, annotate distance_meters, sort ascending."""
    validate_coordinates(lat, lng)
    radius_km = min(max(0.1, radius_km), max_radius_km)
    out: list[dict] = []
    for f in rows:
        try:
            flat, flng = float(f["lat"]), float(f["lng"])
        except (KeyError, TypeError, ValueError):
            continue  # a facility without real coordinates cannot be ranked honestly
        d = haversine_m(lat, lng, flat, flng)
        if d <= radius_km * 1000:
            out.append({**f, "distance_meters": round(d)})
    out.sort(key=lambda r: r["distance_meters"])
    return out[:limit]
