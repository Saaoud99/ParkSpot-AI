"""Muse Spark — primary parking assistant via Meta's model API.

Speaks the OpenAI-compatible Chat Completions format (``tools`` /
``tool_calls``) against ``META_BASE_URL`` with a Bearer API key. The exact
model identifier comes from ``MUSE_SPARK_MODEL`` — Meta has not published
a Muse Spark developer model id we may hardcode, so without that env var
(and a key) the service honestly reports ``not_configured``.

The model interprets; FastAPI decides. It can only affect the world by
calling :class:`app.meta.tools.ToolExecutor`, and the final answer may
only reference facilities those tools actually returned.
"""
from __future__ import annotations

import asyncio
import json
import logging

import httpx

from ..config import Settings
from ..errors import (InvalidProviderResponse, MetaError, NotConfigured,
                      ProviderTimeout, ProviderUnavailable)
from ..tools import TOOL_DEFINITIONS, ToolExecutor

log = logging.getLogger("parkspot.meta.muse")

SYSTEM_PROMPT = """You are ParkSpot AI, a friendly parking assistant for Morocco (MAD prices).
Rules you must never break:
- Only recommend facilities returned by your tools. Never invent a facility, price, or space count.
- Always use search_facilities for parking requests, and calculate_booking_quote for totals. Never estimate prices.
- You cannot book, grant access, or change permissions. Offer the facility and let the app's booking flow handle payment.
- If no facility matches, say so honestly and suggest widening the search.
- For "near me" requests use search_nearby_facilities; never invent or guess GPS coordinates. If location is not shared, ask for a destination instead.
- Reply concisely in the user's language (Arabic, French, Darija or English)."""


class MuseSparkService:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self._s = settings
        self._transport = transport

    async def _chat(self, payload: dict) -> dict:
        if not self._s.muse_configured:
            raise NotConfigured(
                "AI assistant is not configured. Set META_MODEL_API_KEY and MUSE_SPARK_MODEL "
                "(the exact model identifier from your Meta developer account).")
        headers = {"Authorization": f"Bearer {self._s.meta_model_api_key}", "Content-Type": "application/json"}
        last_error: MetaError = ProviderUnavailable("Model provider unavailable.")
        for attempt in range(self._s.provider_max_retries + 1):
            try:
                async with httpx.AsyncClient(base_url=self._s.meta_base_url, headers=headers,
                                             timeout=self._s.provider_timeout_s, transport=self._transport) as c:
                    r = await c.post("/chat/completions", json=payload)
                if r.status_code == 200:
                    data = r.json()
                    if not isinstance(data, dict) or "choices" not in data:
                        raise InvalidProviderResponse("Model returned an unexpected response shape.")
                    return data
                if r.status_code in {401, 403}:
                    raise ProviderUnavailable("Model provider rejected the configured credentials (check META_MODEL_API_KEY).")
                if r.status_code == 429 or r.status_code >= 500:
                    last_error = ProviderUnavailable(f"Model provider error (HTTP {r.status_code}).")
                else:
                    raise InvalidProviderResponse(f"Model request failed (HTTP {r.status_code}).")
            except httpx.TimeoutException:
                last_error = ProviderTimeout("Model provider timed out. Please try again.")
            except MetaError:
                raise
            except httpx.HTTPError:
                last_error = ProviderUnavailable("Model provider is unreachable.")
            if attempt < self._s.provider_max_retries:
                await asyncio.sleep(0.4 * (attempt + 1))
        raise last_error

    async def ask(self, *, messages: list[dict], executor: ToolExecutor, lang: str = "en") -> dict:
        """Run one user turn with tool calling. Returns reply + real facilities."""
        convo: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT + f"\nPreferred language: {lang}."}]
        convo += [{"role": m["role"], "content": m["content"]} for m in messages[-12:]]
        facilities: list[dict] = []

        for _ in range(3):  # bounded tool loop — no runaway model calls
            data = await self._chat({
                "model": self._s.muse_spark_model,
                "messages": convo,
                "tools": TOOL_DEFINITIONS,
                "tool_choice": "auto",
                "temperature": 0.2,
                "max_tokens": 600,
            })
            msg = (data.get("choices") or [{}])[0].get("message") or {}
            calls = msg.get("tool_calls") or []
            if not calls:
                reply = (msg.get("content") or "").strip()
                if not reply:
                    raise InvalidProviderResponse("Model returned an empty reply.")
                return {"reply": reply, "facilities": facilities, "model": self._s.muse_spark_model}
            convo.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
            for call in calls:
                fn = (call.get("function") or {})
                name = fn.get("name", "")
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                    if not isinstance(args, dict):
                        raise ValueError("arguments must be an object")
                    result = await executor.execute(name, args)
                except Exception as e:  # tool errors go back to the model as data, never crash chat
                    result = {"error": str(e)[:200]}
                    log.warning("tool %s rejected: %s", name, result["error"])
                convo.append({"role": "tool", "tool_call_id": call.get("id", name), "content": json.dumps(result)[:4000]})
            facilities = list(executor.facilities_seen.values())

        # Tool loop exhausted: one final no-tools turn so the user still gets an answer.
        data = await self._chat({"model": self._s.muse_spark_model, "messages": convo, "temperature": 0.2, "max_tokens": 400})
        reply = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "").strip()
        if not reply:
            raise InvalidProviderResponse("Model returned an empty reply.")
        return {"reply": reply, "facilities": facilities, "model": self._s.muse_spark_model}
