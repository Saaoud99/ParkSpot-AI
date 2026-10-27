from __future__ import annotations

import httpx

from app.core.config import get_settings

LANDMARKS: dict[str, tuple[str, float, float]] = {
    "downtown": ("Downtown", 37.7749, -122.4194),
    "downtown sf": ("Downtown SF", 37.7749, -122.4194),
    "union square": ("Union Square", 37.7880, -122.4075),
    "fisherman's wharf": ("Fisherman's Wharf", 37.8080, -122.4177),
    "mission": ("Mission District", 37.7599, -122.4148),
    "soma": ("SoMa", 37.7785, -122.4056),
    "airport": ("SFO Airport", 37.6213, -122.3790),
    "sfo": ("SFO Airport", 37.6213, -122.3790),
}


async def geocode(query: str, proximity: tuple[float, float] | None = None) -> dict:
    s = get_settings()
    key = query.strip().lower()
    if s.MAPBOX_ACCESS_TOKEN:
        try:
            prox = proximity or (s.DEMO_CENTER_LAT, s.DEMO_CENTER_LNG)
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://api.mapbox.com/search/geocode/v6/forward",
                    params={"q": query, "proximity": f"{prox[1]},{prox[0]}", "limit": 1, "access_token": s.MAPBOX_ACCESS_TOKEN},
                )
                resp.raise_for_status()
                features = resp.json().get("features", [])
                if features:
                    coords = features[0]["geometry"]["coordinates"]
                    name = features[0].get("properties", {}).get("name", query)
                    return {"ok": True, "name": name, "lat": coords[1], "lng": coords[0]}
        except Exception:
            pass
    if key in LANDMARKS:
        name, lat, lng = LANDMARKS[key]
        return {"ok": True, "name": name, "lat": lat, "lng": lng}
    for k, (name, lat, lng) in LANDMARKS.items():
        if k in key or key in k:
            return {"ok": True, "name": name, "lat": lat, "lng": lng}
    return {"ok": False, "name": query, "lat": s.DEMO_CENTER_LAT, "lng": s.DEMO_CENTER_LNG}
