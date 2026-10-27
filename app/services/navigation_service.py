from __future__ import annotations

from urllib.parse import quote_plus

from app.core.config import get_settings
from app.db.models.spot import ParkingSpot


def build_navigation(spot: ParkingSpot, origin_lat: float | None = None, origin_lng: float | None = None) -> dict:
    s = get_settings()
    dest = f"{spot.latitude},{spot.longitude}"
    mapbox_url = None
    if origin_lat is not None and origin_lng is not None:
        mapbox_url = (
            f"https://api.mapbox.com/directions/v5/mapbox/driving/{origin_lng},{origin_lat};{spot.longitude},{spot.latitude}"
            f"?geometries=geojson&overview=full&access_token={s.MAPBOX_ACCESS_TOKEN}"
        )
    return {
        "destination": {"lat": spot.latitude, "lng": spot.longitude, "address": spot.address, "access_instructions": spot.access_instructions},
        "google_maps_url": f"https://www.google.com/maps/dir/?api=1&destination={dest}",
        "apple_maps_url": f"https://maps.apple.com/?daddr={dest}&q={quote_plus(spot.address)}",
        "geo_uri": f"geo:{dest}?q={dest}",
        "mapbox_directions_url": mapbox_url,
    }
