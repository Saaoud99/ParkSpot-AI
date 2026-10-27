from __future__ import annotations

import re
from datetime import timedelta
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, ValidationError

from app.ai.tools.context import ToolContext
from app.core.exceptions import AppError
from app.repositories import booking_repo, spot_repo
from app.schemas.booking import HoldIn
from app.services import booking_service, geocode_service, pricing_service, spot_service, vehicle_service
from app.services.navigation_service import build_navigation
from app.utils.timeutil import parse_iso, round_up_quarter_hours


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResolveArgs(_Args):
    expression: str
    duration_hint: str | None = None


class GeocodeArgs(_Args):
    query: str


class SearchArgs(_Args):
    latitude: float
    longitude: float
    start_time: str
    end_time: str
    radius_km: float = 2
    covered: bool | None = None
    ev_charging: bool | None = None
    max_price_per_hour: float | None = None
    spot_type: str | None = None
    limit: int = 5


class QuoteArgs(_Args):
    spot_id: int
    start_time: str
    end_time: str


class HoldArgs(_Args):
    spot_id: int
    start_time: str
    end_time: str
    vehicle_id: int | None = None


class BookingIdArgs(_Args):
    booking_id: int


class MyBookingsArgs(_Args):
    status: str | None = None


class EmptyArgs(_Args):
    pass


def _parse_duration(text: str | None, default_hours: float = 2.0) -> float:
    if not text:
        return default_hours
    m = re.search(r"(\d+(?:\.\d+)?)\s*(h|hour|hours)", text)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)\s*(m|min|minutes)", text)
    if m:
        return float(m.group(1)) / 60.0
    return default_hours


async def resolve_datetime(ctx: ToolContext, args: dict[str, Any]) -> dict:
    a = ResolveArgs(**args)
    try:
        import dateparser

        tz = ctx.timezone or "UTC"
        now_local = ctx.now.astimezone(ZoneInfo(tz))
        parsed = dateparser.parse(a.expression, settings={"RELATIVE_BASE": now_local.replace(tzinfo=None), "PREFER_DATES_FROM": "future", "TIMEZONE": tz, "RETURN_AS_TIMEZONE_AWARE": True})
    except Exception:
        parsed = None
    if parsed is None:
        return {"ok": False, "error": "unparseable_datetime", "detail": f"could not parse: {a.expression}"}
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(ctx.timezone or "UTC"))
    start = parsed.astimezone(ZoneInfo("UTC"))
    duration = _parse_duration(a.duration_hint) if a.duration_hint else _parse_duration(a.expression)
    end = start + timedelta(hours=duration)
    return {"ok": True, "start": start.isoformat(), "end": end.isoformat(), "hours": round_up_quarter_hours(end - start)}


async def geocode_place(ctx: ToolContext, args: dict[str, Any]) -> dict:
    a = GeocodeArgs(**args)
    result = await geocode_service.geocode(a.query, ctx.location)
    return result


async def search_parking_spots(ctx: ToolContext, args: dict[str, Any]) -> dict:
    a = SearchArgs(**args)
    from decimal import Decimal

    results = await spot_service.search(ctx.db, a.latitude, a.longitude, a.radius_km, parse_iso(a.start_time), parse_iso(a.end_time),
                                        a.covered, a.ev_charging, a.spot_type, Decimal(str(a.max_price_per_hour)) if a.max_price_per_hour else None, min(a.limit, 8))
    spots = [{"id": r["id"], "title": r["title"], "address": r["address"], "spot_type": r["spot_type"].value if hasattr(r["spot_type"], "value") else r["spot_type"],
              "distance_km": r["distance_km"], "price_per_hour_now": str(r["price_per_hour_now"]), "estimated_total": str(r["estimated_total"]),
              "spaces_available": r.get("spaces_available"), "authorized_capacity": r.get("authorized_capacity"),
              "is_covered": r["is_covered"], "has_ev_charging": r["has_ev_charging"]} for r in results[:8]]
    return {"ok": True, "count": len(spots), "spots": spots}


async def get_price_quote(ctx: ToolContext, args: dict[str, Any]) -> dict:
    a = QuoteArgs(**args)
    spot = await spot_repo.get(ctx.db, a.spot_id)
    if spot is None:
        return {"ok": False, "error": "not_found", "detail": "spot not found"}
    q = await pricing_service.quote(ctx.db, spot, parse_iso(a.start_time), parse_iso(a.end_time))
    return {"ok": True, **{k: str(v) if not isinstance(v, (int, float, bool, type(None))) else v for k, v in q.items()}}


async def hold_spot(ctx: ToolContext, args: dict[str, Any]) -> dict:
    a = HoldArgs(**args)
    booking = await booking_service.hold(ctx.db, ctx.user, HoldIn(spot_id=a.spot_id, start=parse_iso(a.start_time), end=parse_iso(a.end_time), vehicle_id=a.vehicle_id))
    return {"ok": True, "booking_id": booking.id, "status": booking.status.value, "hold_expires_at": booking.hold_expires_at.isoformat() if booking.hold_expires_at else None,
            "total": str(booking.total_price), "currency": booking.currency, "spot_title": booking.spot.title if booking.spot else ""}


async def confirm_booking(ctx: ToolContext, args: dict[str, Any]) -> dict:
    a = BookingIdArgs(**args)
    booking = await booking_service.confirm(ctx.db, ctx.user, a.booking_id)
    nav = build_navigation(booking.spot) if booking.spot else {}
    return {"ok": True, "booking_id": booking.id, "status": booking.status.value, "total": str(booking.total_price),
            "qr_url": f"/api/v1/bookings/{booking.id}/qr", "navigation": {"google_maps_url": nav.get("google_maps_url"), "apple_maps_url": nav.get("apple_maps_url")},
            "access_instructions": booking.spot.access_instructions if booking.spot else None}


async def get_my_bookings(ctx: ToolContext, args: dict[str, Any]) -> dict:
    a = MyBookingsArgs(**args)
    rows, _ = await booking_repo.list_for_driver(ctx.db, ctx.user.id, a.status, 10, 0)
    return {"ok": True, "bookings": [{"id": b.id, "spot_title": b.spot.title if b.spot else "", "start_time": b.start_time.isoformat(), "end_time": b.end_time.isoformat(), "status": b.status.value, "total": str(b.total_price)} for b in rows[:10]]}


async def cancel_booking(ctx: ToolContext, args: dict[str, Any]) -> dict:
    a = BookingIdArgs(**args)
    booking = await booking_service.cancel(ctx.db, ctx.user, a.booking_id)
    return {"ok": True, "booking_id": booking.id, "status": booking.status.value}


async def get_navigation_link(ctx: ToolContext, args: dict[str, Any]) -> dict:
    a = BookingIdArgs(**args)
    booking = await booking_service.get_for_user(ctx.db, a.booking_id, ctx.user)
    nav = build_navigation(booking.spot, *(ctx.location or (None, None))) if booking.spot else {}
    return {"ok": True, **nav}


async def list_my_vehicles(ctx: ToolContext, args: dict[str, Any]) -> dict:
    EmptyArgs(**args)
    vehicles = await vehicle_service.list_vehicles(ctx.db, ctx.user)
    return {"ok": True, "vehicles": [{"id": v.id, "plate": v.plate, "make": v.make, "model": v.model, "is_default": v.is_default} for v in vehicles]}


TOOL_HANDLERS = {
    "resolve_datetime": resolve_datetime, "geocode_place": geocode_place, "search_parking_spots": search_parking_spots,
    "get_price_quote": get_price_quote, "hold_spot": hold_spot, "confirm_booking": confirm_booking,
    "get_my_bookings": get_my_bookings, "cancel_booking": cancel_booking, "get_navigation_link": get_navigation_link,
    "list_my_vehicles": list_my_vehicles,
}


async def execute_tool(name: str, args: dict[str, Any], ctx: ToolContext) -> dict:
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return {"ok": False, "error": "unknown_tool"}
    try:
        return await handler(ctx, args)
    except AppError as e:
        return {"ok": False, "error": e.code, "detail": e.detail}
    except ValidationError as e:
        return {"ok": False, "error": "invalid_arguments", "detail": str(e)}
