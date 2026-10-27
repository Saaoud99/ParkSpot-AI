from __future__ import annotations

from pydantic import BaseModel


class GeoPoint(BaseModel):
    lat: float
    lng: float
    address: str | None = None
    access_instructions: str | None = None


class NavigationOut(BaseModel):
    destination: GeoPoint
    google_maps_url: str
    apple_maps_url: str
    geo_uri: str
    mapbox_directions_url: str | None = None
