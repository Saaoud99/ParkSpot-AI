"""Real inventory access — the only data tools and services may use.

Talks to the existing Supabase project over PostgREST using the caller's
own JWT, so Row Level Security (own bookings, public facilities) stays in
force. Prices always come from ``facilities.price_per_hour_cents`` here,
never from the model.
"""
from __future__ import annotations

import httpx

from .config import Settings
from .errors import NotConfigured, ProviderUnavailable

FACILITY_FIELDS = "id,name,name_ar,city,address,lat,lng,price_per_hour_cents,available,capacity,authorized_capacity,total_capacity,active,features,rating,open_24h"


class Inventory:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self._s = settings
        self._transport = transport

    def _client(self, user_jwt: str | None) -> httpx.AsyncClient:
        if not (self._s.supabase_url and self._s.supabase_publishable_key):
            raise NotConfigured("Inventory is not configured (SUPABASE_URL / SUPABASE_PUBLISHABLE_KEY missing).")
        headers = {"apikey": self._s.supabase_publishable_key}
        if user_jwt:
            headers["Authorization"] = f"Bearer {user_jwt}"
        return httpx.AsyncClient(
            base_url=self._s.supabase_url, headers=headers,
            timeout=self._s.provider_timeout_s, transport=self._transport,
        )

    async def _get(self, path: str, params: dict, user_jwt: str | None) -> list[dict]:
        try:
            async with self._client(user_jwt) as c:
                r = await c.get(path, params=params)
        except httpx.TimeoutException:
            raise ProviderUnavailable("Inventory lookup timed out.")
        except httpx.HTTPError:
            raise ProviderUnavailable("Inventory is unreachable.")
        if r.status_code >= 400:
            raise ProviderUnavailable(f"Inventory lookup failed (HTTP {r.status_code}).")
        data = r.json()
        return data if isinstance(data, list) else []

    @staticmethod
    def _bookable(rows: list[dict]) -> list[dict]:
        """Only facilities an admin has not deactivated are bookable inventory."""
        return [r for r in rows if r.get("active", True) is not False]

    async def search_facilities(self, *, city: str | None = None, feature: str | None = None,
                                max_price_cents: int | None = None, min_available: int = 1,
                                limit: int = 6, user_jwt: str | None = None) -> list[dict]:
        params: dict = {"select": FACILITY_FIELDS, "order": "rating.desc", "limit": str(limit),
                        "available": f"gte.{max(0, min_available)}"}
        if city:
            params["city"] = f"ilike.{city}"
        if feature:
            params["features"] = f"cs.{{{feature}}}"
        if max_price_cents is not None:
            params["price_per_hour_cents"] = f"lte.{max_price_cents}"
        return self._bookable(await self._get("/rest/v1/facilities", params, user_jwt))

    async def get_facility(self, facility_id: str, user_jwt: str | None = None) -> dict | None:
        rows = self._bookable(await self._get("/rest/v1/facilities",
                               {"select": FACILITY_FIELDS, "id": f"eq.{facility_id}", "limit": "1"}, user_jwt))
        return rows[0] if rows else None

    async def all_facilities(self, user_jwt: str | None = None) -> list[dict]:
        """All contracted facilities with coordinates (for GPS distance ranking)."""
        return self._bookable(await self._get("/rest/v1/facilities",
                               {"select": FACILITY_FIELDS, "order": "rating.desc", "limit": "200"}, user_jwt))

    async def insert(self, table: str, row: dict, user_jwt: str) -> bool:
        """Best-effort insert (e.g. camera events). Returns False on any failure."""
        try:
            async with self._client(user_jwt) as c:
                r = await c.post(f"/rest/v1/{table}", json=row, headers={"Prefer": "return=minimal"})
            return r.status_code < 300
        except Exception:
            return False

    async def bookings_for_plate(self, plate_normalized: str, user_jwt: str | None = None) -> list[dict]:
        """Bookings (visible to the caller under RLS) whose account plate matches.

        Plate lives on profiles; bookings live on bookings. Two-step lookup,
        both constrained by RLS to rows the caller may actually see — partner
        and admin roles see facility bookings per existing policies.
        """
        profiles = await self._get("/rest/v1/profiles",
                                   {"select": "id,vehicle_plate", "limit": "200"}, user_jwt)
        owner_ids = [p["id"] for p in profiles
                     if _normalize_plate(str(p.get("vehicle_plate") or "")) == plate_normalized]
        if not owner_ids:
            return []
        rows = await self._get("/rest/v1/bookings",
                               {"select": "id,user_id,facility_id,start_at,end_at,status",
                                "user_id": f"in.({','.join(owner_ids)})",
                                "order": "start_at.desc", "limit": "20"}, user_jwt)
        return rows


def _normalize_plate(text: str) -> str:
    return "".join(ch for ch in text.upper() if ch.isalnum())


def quote_cents(facility: dict, hours: int) -> int:
    """Server-side price. The model may request a quote; only this computes it."""
    return int(facility["price_per_hour_cents"]) * hours
