from __future__ import annotations


def _fn(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
    return {"type": "function", "function": {"name": name, "description": description, "parameters": {"type": "object", "properties": properties, "required": required or [], "additionalProperties": False}}}


TOOL_SPECS: list[dict] = [
    _fn("resolve_datetime", "Resolve a natural-language time expression to start/end ISO datetimes.", {"expression": {"type": "string"}, "duration_hint": {"type": "string"}}, ["expression"]),
    _fn("geocode_place", "Geocode a place name to coordinates.", {"query": {"type": "string"}}, ["query"]),
    _fn("search_parking_spots", "Search available parking spots.", {
        "latitude": {"type": "number"}, "longitude": {"type": "number"}, "start_time": {"type": "string"}, "end_time": {"type": "string"},
        "radius_km": {"type": "number"}, "covered": {"type": "boolean"}, "ev_charging": {"type": "boolean"},
        "max_price_per_hour": {"type": "number"}, "spot_type": {"type": "string"}, "limit": {"type": "integer"}},
        ["latitude", "longitude", "start_time", "end_time"]),
    _fn("get_price_quote", "Get price quote for a spot.", {"spot_id": {"type": "integer"}, "start_time": {"type": "string"}, "end_time": {"type": "string"}}, ["spot_id", "start_time", "end_time"]),
    _fn("hold_spot", "Hold a spot for the current user.", {"spot_id": {"type": "integer"}, "start_time": {"type": "string"}, "end_time": {"type": "string"}, "vehicle_id": {"type": "integer"}}, ["spot_id", "start_time", "end_time"]),
    _fn("confirm_booking", "Confirm and pay a held booking owned by the current user.", {"booking_id": {"type": "integer"}}, ["booking_id"]),
    _fn("get_my_bookings", "List current user's bookings.", {"status": {"type": "string"}}),
    _fn("cancel_booking", "Cancel a booking owned by the current user.", {"booking_id": {"type": "integer"}}, ["booking_id"]),
    _fn("get_navigation_link", "Get navigation links for a booking.", {"booking_id": {"type": "integer"}}, ["booking_id"]),
    _fn("list_my_vehicles", "List current user's vehicles.", {}),
]
