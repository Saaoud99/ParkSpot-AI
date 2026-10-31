"""Grounded (non-LLM) assistant tests — real inventory only, no credentials.

The grounded mode is the always-available assistant: it must answer from
ToolExecutor results, quote server-side prices, and honestly refuse to
guess a location. Run: pytest tests/test_grounded.py -q
"""
from __future__ import annotations

import pytest

from app.meta.services.grounded import GroundedAssistant
from app.meta.tools import ToolExecutor

FACILITIES = [
    {"id": "11111111-1111-1111-1111-111111111111", "name": "Casa Marina Parking",
     "name_ar": "موقف كازا مارينا", "city": "Casablanca", "address": "Bd Mohammed V",
     "lat": 33.59, "lng": -7.61, "price_per_hour_cents": 2000, "available": 14,
     "capacity": 120, "features": ["covered", "cctv"], "rating": 4.6, "open_24h": True},
    {"id": "22222222-2222-2222-2222-222222222222", "name": "Maârif Open Lot",
     "name_ar": "موقف المعاريف", "city": "Casablanca", "address": "Rue Ibnou Mounir",
     "lat": 33.58, "lng": -7.63, "price_per_hour_cents": 800, "available": 22,
     "capacity": 90, "features": ["cctv", "ev"], "rating": 4.3, "open_24h": True},
    {"id": "33333333-3333-3333-3333-333333333333", "name": "Agdal Smart Park",
     "name_ar": "موقف أكدال", "city": "Rabat", "address": "Av. de France",
     "lat": 33.99, "lng": -6.85, "price_per_hour_cents": 1200, "available": 57,
     "capacity": 180, "features": ["ev", "covered"], "rating": 4.7, "open_24h": True},
]


class FakeInventory:
    async def search_facilities(self, **kw):
        rows = FACILITIES
        if kw.get("city"):
            rows = [r for r in rows if r["city"] == kw["city"]]
        if kw.get("feature"):
            rows = [r for r in rows if kw["feature"] in r["features"]]
        if kw.get("max_price_cents") is not None:
            rows = [r for r in rows if r["price_per_hour_cents"] <= kw["max_price_cents"]]
        return rows[: kw.get("limit", 6)]

    async def get_facility(self, fid, user_jwt=None):
        return next((r for r in FACILITIES if r["id"] == fid), None)

    async def all_facilities(self, user_jwt=None):
        return FACILITIES


def run(text, lang="en", coords=None):
    ex = ToolExecutor(FakeInventory(), "jwt", coords=coords)
    return GroundedAssistant().ask(messages=[{"role": "user", "content": text}], executor=ex, lang=lang)


@pytest.mark.asyncio
async def test_city_search_returns_only_real_facilities():
    out = await run("parking in Casablanca")
    assert out["mode"] == "grounded_fallback"
    assert {f["name"] for f in out["facilities"]} == {"Casa Marina Parking", "Maârif Open Lot"}
    assert "Casa Marina" in out["reply"]


@pytest.mark.asyncio
async def test_cheapest_sorts_by_server_price():
    out = await run("cheapest parking in Casablanca")
    assert out["facilities"][0]["name"] == "Maârif Open Lot"  # 8 MAD/h before 20 MAD/h


@pytest.mark.asyncio
async def test_ev_feature_filter():
    out = await run("Where can I charge my EV in Rabat?")
    assert [f["name"] for f in out["facilities"]] == ["Agdal Smart Park"]


@pytest.mark.asyncio
async def test_quote_uses_server_side_math():
    out = await run("parking in Casablanca for 3 hours")
    assert "60.00 MAD" in out["reply"]  # Casa Marina 20 MAD/h × 3, computed by the tool


@pytest.mark.asyncio
async def test_max_price_filter():
    out = await run("parking in Casablanca under 10 MAD")
    assert [f["name"] for f in out["facilities"]] == ["Maârif Open Lot"]


@pytest.mark.asyncio
async def test_near_me_without_location_asks_instead_of_guessing():
    out = await run("parking near me")
    assert out["facilities"] == []
    assert "location" in out["reply"].lower()


@pytest.mark.asyncio
async def test_near_me_with_device_coords_uses_real_distance():
    out = await run("parking near me", coords=(33.5731, -7.5898))
    assert out["facilities"] and "distance_meters" in out["facilities"][0]


@pytest.mark.asyncio
async def test_refund_policy_question():
    out = await run("How do refunds work?")
    assert out["facilities"] == []
    assert "50%" in out["reply"]


@pytest.mark.asyncio
async def test_arabic_city_search():
    out = await run("بغيت موقف في الدار البيضاء", lang="ar")
    assert len(out["facilities"]) == 2
    assert "متاح" in out["reply"]


@pytest.mark.asyncio
async def test_no_match_is_honest():
    out = await run("parking in Casablanca under 1 MAD")
    assert out["facilities"] == []
    assert "no matching" in out["reply"].lower()
