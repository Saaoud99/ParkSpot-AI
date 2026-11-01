"""Deterministic, grounded parking assistant — the always-available mode.

This is NOT an LLM and never claims to be one. It parses a small, explicit
set of intents (city, amenity, price ceiling, cheapest, duration quote,
refund/wallet policy, near-me) and answers exclusively from
:class:`app.meta.tools.ToolExecutor` results over real inventory. It exists
so the assistant workflow works end-to-end — and degrades honestly — when
Muse Spark is not configured or the provider fails, instead of the chat
dying or an ungrounded model inventing facilities.

The Muse Spark path stays primary whenever it is configured; the API
layer labels every response with ``mode`` so the UI can say which ran.
"""
from __future__ import annotations

import re

from ..tools import ToolExecutor

_CITIES = {
    "Casablanca": ("casablanca", "casa", "الدار البيضاء", "الدارالبيضاء", "كازا"),
    "Rabat": ("rabat", "الرباط"),
    "Marrakech": ("marrakech", "marrakesh", "مراكش"),
    "Tangier": ("tangier", "tanger", "طنجة"),
}
_FEATURES = {
    "ev": ("ev charging", "electric", "charging", "charge my", "شحن", "كهرباء", "كهربائية"),
    "covered": ("covered", "indoor", "garage", "مغطى", "مغطاة", "مرآب"),
    "cctv": ("cctv", "camera", "secure", "security", "مراقبة", "أمان", "امان"),
    "valet": ("valet",),
}
_CHEAPEST = ("cheapest", "cheap", "أرخص", "ارخص", "رخيص", "moins cher", "pas cher")
_NEAR_ME = ("near me", "nearby", "closest", "قريب مني", "قريبة مني", "قريب", "près de moi", "proche de moi", "a proximite")
_REFUND = ("refund", "cancel", "استرداد", "إلغاء", "الغاء", "rembours")
_WALLET = ("wallet", "top up", "top-up", "balance", "محفظة", "رصيد", "شحن رصيد")
_PARKING_WORDS = ("park", "space", "available", "availability", "book", "reserve", "reservation",
                  "price", "cost", "tarif", "stationnement", "emplacement", "disponible",
                  "موقف", "مواقف", "ركن", "متاح", "حجز", "احجز", "سعر", "أماكن", "اماكن")
_ARABIC = re.compile(r"[؀-ۿ]")
_PRICE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:mad|dh|dirham|درهم|د\.م)")
_PRICE_UNDER = re.compile(r"(?:under|below|less than|أقل من|اقل من)\s*(\d+(?:[.,]\d+)?)")
_HOURS = re.compile(r"(\d{1,2})\s*(?:h\b|hours?|hrs?|ساعات|ساعة)")


def _find(text: str, table: dict) -> str | None:
    for key, words in table.items():
        if any(w in text for w in words):
            return key
    return None


class GroundedAssistant:
    """Rule-based assistant over the same validated tools Muse uses."""

    @staticmethod
    def parking_intent(text: str) -> bool:
        """True when the text asks about live parking inventory, pricing,
        availability, amenities, or booking/refund policy.

        Reuses this module's own intent tables and patterns (no extra LLM
        call). The Muse path uses it as a server-side safeguard: a factual
        parking question the model answered without its tools is answered
        by this deterministic assistant instead of ungrounded prose.
        Greetings and general conversation return False.
        """
        t = (text or "").lower()
        if not t.strip():
            return False
        return bool(
            _find(t, _CITIES) or _find(t, _FEATURES)
            or any(w in t for w in _NEAR_ME + _CHEAPEST + _REFUND + _WALLET)
            or _PRICE.search(t) or _HOURS.search(t)
            or any(w in t for w in _PARKING_WORDS))

    async def ask(self, *, messages: list[dict], executor: ToolExecutor, lang: str = "en") -> dict:
        text_raw = next((str(m.get("content") or "") for m in reversed(messages) if m.get("role") == "user"), "")
        text = text_raw.lower()
        ar = lang == "ar" or bool(_ARABIC.search(text_raw))

        # Policy questions are answered from the product's actual rules —
        # no facility search, no invented balances (we cannot see wallets here).
        if any(w in text for w in _REFUND) and not _find(text, _CITIES):
            return {"reply": (
                "سياسة الاسترداد: استرداد كامل قبل ساعتين أو أكثر من بدء الحجز، 50٪ قبل البدء، ولا استرداد بعد البدء. يمكنك الإلغاء من صفحة حجوزاتي."
                if ar else
                "Refund policy: full refund 2h or more before your booking starts, 50% until it starts, none after. You can cancel from My Bookings."),
                "facilities": [], "model": "grounded-fallback", "mode": "grounded_fallback"}
        if any(w in text for w in _WALLET) and not _find(text, _CITIES):
            return {"reply": (
                "محفظة ParkSpot رصيد تجريبي مسبق الدفع بالدرهم. اشحنها من صفحة المحفظة، وادفع عند الحجز، وتظهر الاستردادات هناك تلقائياً."
                if ar else
                "ParkSpot Wallet is a prepaid MAD balance (currently demo money). Top up on the Wallet screen, pay when you book, and refunds appear there automatically."),
                "facilities": [], "model": "grounded-fallback", "mode": "grounded_fallback"}

        near = any(w in text for w in _NEAR_ME)
        if near:
            result = await executor.execute("search_nearby_facilities", {"radius_km": 5})
            facilities = result.get("facilities") or []
            if result.get("reason") == "location_not_shared":
                return {"reply": (
                    "لا أستطيع معرفة موقعك من المحادثة. اضغط «مواقف قربي» في الرئيسية لمشاركة موقع جهازك، أو أخبرني بالمدينة (الدار البيضاء، الرباط، مراكش، طنجة)."
                    if ar else
                    "I can't get your location from chat. Tap “Parking Near Me” on Home to share your device location, or tell me a city (Casablanca, Rabat, Marrakech, Tangier)."),
                    "facilities": [], "model": "grounded-fallback", "mode": "grounded_fallback"}
            return {"reply": self._format(facilities, ar=ar, text=text, executor=executor),
                    "facilities": facilities, "model": "grounded-fallback", "mode": "grounded_fallback"}

        args: dict = {"limit": 5}
        city = _find(text, _CITIES)
        if city:
            args["city"] = city
        feature = _find(text, _FEATURES)
        if feature:
            args["feature"] = feature
        m = _PRICE.search(text) or _PRICE_UNDER.search(text)
        if m:
            args["max_price_mad"] = float(m.group(1).replace(",", "."))
        result = await executor.execute("search_facilities", args)
        facilities = list(result.get("facilities") or [])
        if any(w in text for w in _CHEAPEST):
            facilities.sort(key=lambda f: f["price_mad_per_hour"])
        reply = await self._format_with_quote(facilities, ar=ar, text=text, executor=executor)
        return {"reply": reply, "facilities": facilities,
                "model": "grounded-fallback", "mode": "grounded_fallback"}

    async def _format_with_quote(self, facilities: list[dict], *, ar: bool, text: str, executor: ToolExecutor) -> str:
        head = self._format(facilities, ar=ar, text=text, executor=executor)
        hm = _HOURS.search(text)
        if hm and facilities:
            hours = max(1, min(24, int(hm.group(1))))
            q = await executor.execute("calculate_booking_quote",
                                        {"facility_id": facilities[0]["id"], "hours": hours})
            if q.get("found"):
                head += (f"\n💰 {hours}h = {q['total_mad']:.2f} MAD" if not ar
                         else f"\n💰 {hours} ساعة = {q['total_mad']:.2f} درهم")
        return head

    @staticmethod
    def _format(facilities: list[dict], *, ar: bool, text: str, executor: ToolExecutor) -> str:
        if not facilities:
            return ("لم أجد مواقف مطابقة في المخزون الحقيقي. جرّب مدينة أخرى أو وسّع البحث."
                    if ar else
                    "I found no matching parking in the real inventory. Try another city or widen the search.")
        lines = []
        for f in facilities[:5]:
            dist = f.get("distance_meters")
            suffix = f" · {dist} m" if isinstance(dist, (int, float)) else ""
            lines.append(
                f"• {f['name']} ({f['city']}) — {f['price_mad_per_hour']:.2f} {'درهم/ساعة' if ar else 'MAD/h'}, "
                f"{f['available']}/{f['capacity']} {'متاح' if ar else 'free'}{suffix}")
        intro = "إليك مواقف حقيقية متاحة الآن:" if ar else "Here are real facilities available now:"
        outro = ("اضغط على بطاقة لفتح التفاصيل والحجز." if ar
                 else "Tap a card to open details and book.")
        return f"{intro}\n" + "\n".join(lines) + f"\n{outro}"
