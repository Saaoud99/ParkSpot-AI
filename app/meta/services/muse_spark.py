"""Muse Spark — primary parking assistant via Meta's model API.

Speaks the Chat Completions format (``tools`` / ``tool_calls``) against
``META_BASE_URL`` with a Bearer API key, per Meta's documented tool /
function-calling contract. The model identifier defaults to the documented
``muse-spark-1.3`` and can be overridden with ``MUSE_SPARK_MODEL``
(``muse-spark-1.2`` / ``muse-spark-1.1`` are also documented). Without an
API key the service honestly reports ``not_configured``; no live Meta call
has been verified from this codebase — the client is covered only by
mocked-transport tests.

The model interprets; FastAPI decides. It can only affect the world by
calling :class:`app.meta.tools.ToolExecutor`, and any facility,
availability, price, or quote fact shown to the user is rendered
deterministically from tool results — never from unverified model prose.
Ordinary conversation with no factual tool activity keeps the model's
natural reply.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from datetime import timezone
from email.utils import parsedate_to_datetime

import httpx

from ..config import Settings
from ..errors import (InvalidProviderResponse, MetaError, NotConfigured,
                      ProviderTimeout, ProviderUnavailable)
from ..tools import TOOL_DEFINITIONS, ToolExecutor
from .grounded import GroundedAssistant

log = logging.getLogger("parkspot.meta.muse")

# Retry policy (Meta error-handling guidance): 429/500/503 are retried with
# exponential backoff + bounded jitter, honoring Retry-After when the
# provider sends it, never sleeping past the overall ask() deadline.
# 504 is NOT retried — replaying the same non-streaming request would just
# repeat the long generation that timed out at the gateway. Client errors
# (400/401/402/403/404/413) are never retried.
_MAX_RETRY_DELAY_S = 30.0

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

    @staticmethod
    def _parse_retry_after(headers) -> float | None:
        """Seconds from a Retry-After header (numeric or HTTP-date), or None."""
        raw = headers.get("Retry-After") if headers is not None else None
        if not raw:
            return None
        raw = str(raw).strip()
        try:
            return max(0.0, float(raw))
        except ValueError:
            pass
        try:
            dt = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            return None
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, dt.timestamp() - time.time())

    @classmethod
    def _retry_delay(cls, attempt: int, headers=None) -> float:
        """Exponential backoff with bounded jitter; honors Retry-After.

        The provider's Retry-After wins when it exceeds our own backoff.
        The result is capped so one sleep can never stall a chat turn.
        """
        backoff = min(8.0, 0.5 * (2 ** attempt))  # 0.5s, 1s, 2s, 4s, 8s
        retry_after = cls._parse_retry_after(headers)
        base = max(backoff, retry_after) if retry_after is not None else backoff
        base = min(base, _MAX_RETRY_DELAY_S)
        return min(_MAX_RETRY_DELAY_S, base + random.uniform(0.0, min(1.0, 0.25 * base)))

    @staticmethod
    def _error_detail(r: httpx.Response) -> dict:
        """Safely extract structured provider error fields, if present.

        Only message/type/param/code are pulled, each truncated; malformed
        or non-JSON bodies yield {}. Used for logs and a generic code suffix
        — never for raw provider prose in user-facing messages, and never
        near credentials or request data.
        """
        try:
            data = r.json()
        except ValueError:
            return {}
        err = data.get("error") if isinstance(data, dict) else None
        if not isinstance(err, dict):
            return {}
        out: dict[str, str] = {}
        for field in ("message", "type", "param", "code"):
            v = err.get(field)
            if isinstance(v, bool) or not isinstance(v, (str, int, float)):
                continue
            out[field] = str(v)[:200]
        return out

    async def _chat(self, payload: dict, *, deadline: float | None = None) -> dict:
        if not self._s.muse_configured:
            raise NotConfigured(
                "AI assistant is not configured. Set MODEL_API_KEY "
                "(MUSE_SPARK_MODEL defaults to muse-spark-1.3).")
        headers = {"Authorization": f"Bearer {self._s.meta_model_api_key}", "Content-Type": "application/json"}
        last_error: MetaError = ProviderUnavailable("Model provider unavailable.")
        for attempt in range(self._s.provider_max_retries + 1):
            resp_headers = None
            timeout = self._s.provider_timeout_s
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ProviderTimeout("Model provider timed out. Please try again.")
                timeout = min(timeout, remaining)
            try:
                async with httpx.AsyncClient(base_url=self._s.meta_base_url, headers=headers,
                                             timeout=timeout, transport=self._transport) as c:
                    r = await c.post("/chat/completions", json=payload)
                resp_headers = r.headers
                if r.status_code == 200:
                    try:
                        data = r.json()
                    except ValueError as e:
                        raise InvalidProviderResponse("Model returned an unexpected response shape.") from e
                    if not isinstance(data, dict) or "choices" not in data:
                        raise InvalidProviderResponse("Model returned an unexpected response shape.")
                    return data
                detail = self._error_detail(r)
                if detail:
                    # Diagnostic fields only — no key, headers, or request body.
                    log.warning("model provider HTTP %s type=%s code=%s param=%s message=%s",
                                r.status_code, detail.get("type"), detail.get("code"),
                                detail.get("param"), detail.get("message"))
                suffix = f" (provider code: {detail['code']})" if detail.get("code") else ""
                if r.status_code == 504:
                    # Never blindly replay a non-streaming request whose
                    # generation already timed out at the gateway.
                    raise ProviderTimeout("Model provider timed out. Please try again.")
                if r.status_code in {401, 403}:
                    raise ProviderUnavailable("Model provider rejected the configured credentials (check MODEL_API_KEY).")
                if r.status_code == 429 or r.status_code >= 500:
                    last_error = ProviderUnavailable(f"Model provider error (HTTP {r.status_code}){suffix}.")
                else:
                    raise InvalidProviderResponse(f"Model request failed (HTTP {r.status_code}){suffix}.")
            except httpx.TimeoutException:
                last_error = ProviderTimeout("Model provider timed out. Please try again.")
            except MetaError:
                raise
            except httpx.HTTPError:
                last_error = ProviderUnavailable("Model provider is unreachable.")
            if attempt < self._s.provider_max_retries:
                delay = self._retry_delay(attempt, resp_headers)
                if deadline is not None:
                    # Never sleep past the overall ask() budget.
                    delay = min(delay, max(0.0, deadline - time.monotonic()))
                await asyncio.sleep(delay)
        raise last_error

    @staticmethod
    def _message(data: dict) -> dict:
        """Return choices[0].message, or raise a typed provider error."""
        choices = data.get("choices") if isinstance(data, dict) else None
        if (not isinstance(choices, list) or not choices
                or not isinstance(choices[0], dict)
                or not isinstance(choices[0].get("message"), dict)):
            raise InvalidProviderResponse("Model returned an unexpected response shape.")
        return choices[0]["message"]

    @staticmethod
    def _reply_text(msg: dict) -> str:
        content = msg.get("content")
        reply = content.strip() if isinstance(content, str) else ""
        if not reply:
            raise InvalidProviderResponse("Model returned an empty reply.")
        return reply

    @staticmethod
    def _parse_call(call: object) -> tuple[str, str, dict]:
        """Validate one tool_call and return (tool_call_id, name, args).

        Malformed provider structures raise InvalidProviderResponse (a typed
        MetaError, so the API layer falls back to grounded mode) instead of
        crashing. A tool_call_id is never fabricated: missing, empty, or
        non-string ids are rejected outright.
        """
        if not isinstance(call, dict):
            raise InvalidProviderResponse("Model returned a malformed tool call.")
        call_id = call.get("id")
        if not isinstance(call_id, str) or not call_id.strip():
            raise InvalidProviderResponse("Model returned a tool call without a valid id.")
        fn = call.get("function")
        if not isinstance(fn, dict):
            raise InvalidProviderResponse("Model returned a malformed tool call.")
        name = fn.get("name")
        if not isinstance(name, str) or not name:
            raise InvalidProviderResponse("Model returned a tool call without a name.")
        raw_args = fn.get("arguments") or "{}"
        if not isinstance(raw_args, str):
            raise InvalidProviderResponse("Model returned malformed tool arguments.")
        try:
            args = json.loads(raw_args)
        except ValueError as e:
            raise InvalidProviderResponse("Model returned malformed tool arguments.") from e
        if not isinstance(args, dict):
            raise InvalidProviderResponse("Model returned malformed tool arguments.")
        return call_id, name, args

    def _finish(self, reply: str, *, executor: ToolExecutor, lang: str,
                tools_used: bool, location_not_shared: bool) -> dict:
        """Build the user-facing result.

        Factual turns (any verified facility/quote from tools) are rendered
        deterministically from tool results — model prose about facilities,
        availability, prices, or totals is never returned. Ordinary
        conversation with no factual tool activity keeps the model reply.
        """
        facilities = list(executor.facilities_seen.values())
        quotes = list(getattr(executor, "quotes_seen", []) or [])
        model = self._s.muse_spark_model
        ar = lang == "ar"
        if facilities or quotes:
            parts: list[str] = []
            if facilities:
                parts.append(GroundedAssistant._format(facilities, ar=ar, text="", executor=executor))
            for q in quotes:
                name = q.get("facility_name") or q.get("facility_id", "")
                parts.append(
                    f"💰 {name}: {q['hours']} ساعة = {q['total_mad']:.2f} درهم" if ar
                    else f"💰 {name}: {q['hours']}h = {q['total_mad']:.2f} MAD")
            return {"reply": "\n".join(parts), "facilities": facilities, "model": model}
        if location_not_shared:
            return {"reply": (
                "لا أستطيع معرفة موقعك من المحادثة. اضغط «مواقف قربي» في الرئيسية لمشاركة موقع جهازك، أو أخبرني بالمدينة (الدار البيضاء، الرباط، مراكش، طنجة)."
                if ar else
                "I can't get your location from chat. Tap “Parking Near Me” on Home to share your device location, or tell me a city (Casablanca, Rabat, Marrakech, Tangier)."),
                "facilities": [], "model": model}
        if tools_used:
            # Tools ran but produced no verified facts (no match, unknown id).
            return {"reply": GroundedAssistant._format([], ar=ar, text="", executor=executor),
                    "facilities": [], "model": model}
        return {"reply": reply, "facilities": facilities, "model": model}

    async def ask(self, *, messages: list[dict], executor: ToolExecutor, lang: str = "en") -> dict:
        """Run one user turn with tool calling. Returns reply + real facilities.

        The whole operation — every tool round plus the final completion —
        shares one total deadline (provider_total_timeout_s). Expiry raises
        ProviderTimeout, a typed MetaError the API layer already converts
        into the grounded fallback.
        """
        budget = self._s.provider_total_timeout_s
        deadline = time.monotonic() + budget
        try:
            return await asyncio.wait_for(
                self._ask(messages=messages, executor=executor, lang=lang, deadline=deadline),
                timeout=budget)
        except (asyncio.TimeoutError, TimeoutError):
            raise ProviderTimeout("Model provider timed out. Please try again.") from None

    async def _ask(self, *, messages: list[dict], executor: ToolExecutor, lang: str,
                   deadline: float) -> dict:
        convo: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT + f"\nPreferred language: {lang}."}]
        convo += [{"role": m["role"], "content": m["content"]} for m in messages[-12:]]
        last_user = next((str(m.get("content") or "") for m in reversed(messages) if m.get("role") == "user"), "")
        tools_used = False
        location_not_shared = False

        for _ in range(3):  # bounded tool loop — no runaway model calls
            data = await self._chat({
                "model": self._s.muse_spark_model,
                "messages": convo,
                "tools": TOOL_DEFINITIONS,
                "tool_choice": "auto",
                "temperature": 0.2,
                "max_completion_tokens": 600,
            }, deadline=deadline)
            msg = self._message(data)
            calls = msg.get("tool_calls") or []
            if not isinstance(calls, list):
                raise InvalidProviderResponse("Model returned a malformed tool call.")
            if not calls:
                if not tools_used and GroundedAssistant.parking_intent(last_user):
                    # Factual parking question, but the model skipped its
                    # tools: never ship ungrounded prose about inventory,
                    # prices, or availability — the deterministic assistant
                    # answers from real inventory instead. (General chat
                    # without parking intent keeps the natural reply below.)
                    return await GroundedAssistant().ask(messages=messages, executor=executor, lang=lang)
                return self._finish(self._reply_text(msg), executor=executor, lang=lang,
                                    tools_used=tools_used, location_not_shared=location_not_shared)
            # Replay the COMPLETE assistant message exactly as returned —
            # never reconstruct it or drop fields.
            convo.append(dict(msg))
            for call in calls:
                call_id, name, args = self._parse_call(call)
                tools_used = True
                try:
                    result = await executor.execute(name, args)
                except Exception as e:  # tool errors go back to the model as data, never crash chat
                    result = {"error": str(e)[:200]}
                    log.warning("tool %s rejected: %s", name, result["error"])
                if isinstance(result, dict) and result.get("reason") == "location_not_shared":
                    location_not_shared = True
                convo.append({"role": "tool", "tool_call_id": call_id, "content": json.dumps(result)[:4000]})

        # Tool loop exhausted: one final no-tools turn so the user still gets an answer.
        data = await self._chat({"model": self._s.muse_spark_model, "messages": convo, "temperature": 0.2, "max_completion_tokens": 400}, deadline=deadline)
        return self._finish(self._reply_text(self._message(data)), executor=executor, lang=lang,
                            tools_used=tools_used, location_not_shared=location_not_shared)
