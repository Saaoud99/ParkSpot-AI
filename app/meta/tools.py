"""Controlled tools the model may call.

Every argument is validated here, every result comes from real inventory,
and prices are computed server-side. The model receives tool *results*;
it cannot invent facility ids — handlers only return rows that exist, and
the assistant layer drops any facility the model mentions that a tool did
not return.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, ValidationError

from .errors import ValidationFailed
from .inventory import Inventory, quote_cents

ALLOWED_FEATURES = {"covered", "ev", "cctv", "valet"}
ALLOWED_CITIES = {"Casablanca", "Rabat", "Marrakech", "Tangier"}


class SearchArgs(BaseModel):
    city: str | None = Field(default=None, max_length=40)
    feature: str | None = Field(default=None, max_length=20)
    max_price_mad: float | None = Field(default=None, gt=0, le=1000)
    limit: int = Field(default=5, ge=1, le=8)


class FacilityArgs(BaseModel):
    facility_id: str = Field(min_length=8, max_length=64)


class QuoteArgs(BaseModel):
    facility_id: str = Field(min_length=8, max_length=64)
    hours: int = Field(ge=1, le=24)


TOOL_DEFINITIONS = [
    {"type": "function", "function": {
        "name": "search_facilities",
        "description": "Search real ParkSpot parking facilities by city, amenity and max hourly price in MAD. Returns only facilities that exist.",
        "parameters": {"type": "object", "properties": {
            "city": {"type": "string", "enum": sorted(ALLOWED_CITIES)},
            "feature": {"type": "string", "enum": sorted(ALLOWED_FEATURES), "description": "covered, ev (EV charging), cctv, valet"},
            "max_price_mad": {"type": "number"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 8}}, "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "get_facility_details",
        "description": "Get details for one facility by its id (from search_facilities results).",
        "parameters": {"type": "object", "properties": {"facility_id": {"type": "string"}}, "required": ["facility_id"], "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "check_availability",
        "description": "Check current free spaces for one facility by id.",
        "parameters": {"type": "object", "properties": {"facility_id": {"type": "string"}}, "required": ["facility_id"], "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "calculate_booking_quote",
        "description": "Calculate the exact total price in MAD for parking N hours at a facility. The server computes this; never estimate prices yourself.",
        "parameters": {"type": "object", "properties": {"facility_id": {"type": "string"}, "hours": {"type": "integer", "minimum": 1, "maximum": 24}}, "required": ["facility_id", "hours"], "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "search_nearby_facilities",
        "description": "Search real facilities near the user's CURRENT location. Only works when the user shared GPS from their device; coordinates come from the server, never from you. Use for 'near me' requests.",
        "parameters": {"type": "object", "properties": {"radius_km": {"type": "number", "minimum": 0.5, "maximum": 50}}, "additionalProperties": False}}},
]


def _public(f: dict) -> dict:
    return {
        "id": f["id"], "name": f["name"], "name_ar": f.get("name_ar"),
        "city": f["city"], "address": f["address"],
        "price_mad_per_hour": round(int(f["price_per_hour_cents"]) / 100, 2),
        "available": f["available"], "capacity": f["capacity"],
        "features": f.get("features") or [], "rating": f.get("rating"),
    }


class ToolExecutor:
    def __init__(self, inventory: Inventory, user_jwt: str, coords: tuple[float, float] | None = None):
        self._inv = inventory
        self._jwt = user_jwt
        self._coords = coords  # device GPS supplied by the client — the model can never set this
        self.facilities_seen: dict[str, dict] = {}

    async def execute(self, name: str, raw_args: dict) -> dict:
        try:
            if name == "search_facilities":
                a = SearchArgs(**(raw_args or {}))
                if a.city and a.city not in ALLOWED_CITIES:
                    raise ValidationFailed(f"Unknown city: {a.city}")
                if a.feature and a.feature not in ALLOWED_FEATURES:
                    raise ValidationFailed(f"Unknown feature: {a.feature}")
                rows = await self._inv.search_facilities(
                    city=a.city, feature=a.feature,
                    max_price_cents=int(a.max_price_mad * 100) if a.max_price_mad else None,
                    limit=a.limit, user_jwt=self._jwt)
                out = [_public(r) for r in rows]
                for r in out:
                    self.facilities_seen[r["id"]] = r
                return {"facilities": out, "count": len(out)}
            if name in {"get_facility_details", "check_availability"}:
                a = FacilityArgs(**(raw_args or {}))
                f = await self._inv.get_facility(a.facility_id, user_jwt=self._jwt)
                if not f:
                    return {"found": False}
                pub = _public(f)
                self.facilities_seen[pub["id"]] = pub
                return {"found": True, "facility": pub} if name == "get_facility_details" else {
                    "found": True, "facility_id": pub["id"], "available": pub["available"], "capacity": pub["capacity"]}
            if name == "search_nearby_facilities":
                if not self._coords:
                    return {"found": False, "reason": "location_not_shared",
                            "message": "Ask the user to tap 'Parking Near Me' or share a destination instead. Never guess coordinates."}
                from .geo import nearby_facilities
                radius = float((raw_args or {}).get("radius_km") or 5)
                rows = await self._inv.all_facilities(self._jwt)
                found = nearby_facilities(rows, lat=self._coords[0], lng=self._coords[1], radius_km=radius)
                out = [{**_public(r), "distance_meters": r["distance_meters"]} for r in found]
                for r in out:
                    self.facilities_seen[r["id"]] = r
                return {"facilities": out, "count": len(out)}
            if name == "calculate_booking_quote":
                a = QuoteArgs(**(raw_args or {}))
                f = await self._inv.get_facility(a.facility_id, user_jwt=self._jwt)
                if not f:
                    return {"found": False}
                total = quote_cents(f, a.hours)
                return {"found": True, "facility_id": f["id"], "hours": a.hours,
                        "total_mad": round(total / 100, 2), "currency": "MAD"}
        except ValidationError as e:
            raise ValidationFailed(f"Invalid tool arguments for {name}: {e.errors()[0]['msg'] if e.errors() else 'invalid'}")
        raise ValidationFailed(f"Unknown tool: {name}")
