"""Focused tests for the Meta integration.

Everything external is mocked at the httpx transport layer or with fake
inventory/reader objects — no test needs real credentials, and no test
claims a live integration. Run:  pytest tests/test_meta_integration.py -q
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import wave
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import httpx
import pytest

from app.meta.config import Settings
from app.meta.errors import (InvalidProviderResponse, MetaError,
                             NotConfigured, ProviderTimeout,
                             ProviderUnavailable, ValidationFailed)
from app.meta.inventory import Inventory, effective_available, quote_cents
from app.meta.services.easy_ocr import EasyOCRService
from app.meta.services.grounded import GroundedAssistant
from app.meta.services.muse_spark import MuseSparkService
from app.meta.services.muse_voice import MuseVoiceService
from app.meta.services.sam_vision import SamVisionService
from app.meta.tools import ToolExecutor


FACILITY = {
    "id": "11111111-1111-1111-1111-111111111111", "name": "Casa Marina Parking",
    "name_ar": "موقف كازا مارينا", "city": "Casablanca", "address": "Bd Mohammed V",
    "lat": 33.59, "lng": -7.61, "price_per_hour_cents": 1200, "available": 14,
    "capacity": 120, "features": ["covered", "cctv"], "rating": 4.6, "open_24h": True,
}


class FakeInventory:
    def __init__(self, rows=None, facility=None):
        self.rows = rows if rows is not None else [FACILITY]
        self.facility = facility if facility is not None else FACILITY

    async def search_facilities(self, **kw):
        return self.rows

    async def get_facility(self, fid, user_jwt=None):
        return self.facility if fid == self.facility["id"] else None

    async def all_facilities(self, user_jwt=None):
        return self.rows


def transport(handler):
    return httpx.MockTransport(handler)


def chat_response(content=None, tool_calls=None):
    msg: dict = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return httpx.Response(200, json={"choices": [{"message": msg}]})


# ---------------------------------------------------------------- Muse Spark

@pytest.mark.asyncio
async def test_muse_not_configured_without_env():
    svc = MuseSparkService(Settings())
    with pytest.raises(NotConfigured):
        await svc.ask(messages=[{"role": "user", "content": "parking?"}], executor=ToolExecutor(FakeInventory(), "jwt"))


def configured(handler, **over):
    s = Settings(meta_model_api_key="test-key", muse_spark_model="test-model", **over)
    return MuseSparkService(s, transport=transport(handler))


@pytest.mark.asyncio
async def test_muse_tool_call_returns_only_real_facilities():
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return chat_response(tool_calls=[{
                "id": "c1", "type": "function",
                "function": {"name": "search_facilities", "arguments": json.dumps({"city": "Casablanca"})},
            }])
        return chat_response(content="Casa Marina Parking has spaces.")

    out = await configured(handler).ask(
        messages=[{"role": "user", "content": "parking in Casablanca"}],
        executor=ToolExecutor(FakeInventory(), "jwt"))
    # Factual turns are rendered deterministically from tool results, not
    # from model prose — the facility and its server-side price are present.
    assert "Casa Marina Parking" in out["reply"]
    assert "12.00" in out["reply"]
    assert [f["id"] for f in out["facilities"]] == [FACILITY["id"]]
    assert out["facilities"][0]["price_mad_per_hour"] == 12.0  # from cents, server-side


@pytest.mark.asyncio
async def test_muse_provider_401_is_honest_error():
    svc = configured(lambda req: httpx.Response(401, json={}))
    with pytest.raises(ProviderUnavailable):
        await svc.ask(messages=[{"role": "user", "content": "hi"}], executor=ToolExecutor(FakeInventory(), "jwt"))


@pytest.mark.asyncio
async def test_muse_timeout_retries_then_reports():
    def slow(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=req)

    s = Settings(meta_model_api_key="k", muse_spark_model="m", provider_max_retries=1)
    svc = MuseSparkService(s, transport=transport(slow))
    with pytest.raises(Exception) as ei:
        await svc.ask(messages=[{"role": "user", "content": "hi"}], executor=ToolExecutor(FakeInventory(), "jwt"))
    assert ei.value.code == "provider_timeout"


def _tool_call(call_id, name, args):
    return {"id": call_id, "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)}}


@pytest.mark.asyncio
async def test_muse_replays_complete_assistant_tool_message():
    seen = []
    assistant_msg = {"role": "assistant", "content": None, "tool_calls": [
        _tool_call("c1", "search_facilities", {"city": "Casablanca"})]}

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(json.loads(req.content))
        if len(seen) == 1:
            return httpx.Response(200, json={"choices": [{"message": assistant_msg}]})
        return chat_response(content="done")

    await configured(handler).ask(
        messages=[{"role": "user", "content": "parking in Casablanca"}],
        executor=ToolExecutor(FakeInventory(), "jwt"))
    # The assistant message is replayed byte-identical (content: null and the
    # full tool_calls object preserved), then exactly one tool result follows.
    assert seen[1]["messages"][-2] == assistant_msg
    tool_msg = seen[1]["messages"][-1]
    assert tool_msg["role"] == "tool" and tool_msg["tool_call_id"] == "c1"
    assert json.loads(tool_msg["content"])["facilities"][0]["id"] == FACILITY["id"]


@pytest.mark.asyncio
async def test_muse_tool_results_match_every_tool_call_id():
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(json.loads(req.content))
        if len(seen) == 1:
            return chat_response(tool_calls=[
                _tool_call("c1", "search_facilities", {"city": "Casablanca"}),
                _tool_call("c2", "get_facility_details", {"facility_id": FACILITY["id"]}),
            ])
        return chat_response(content="done")

    await configured(handler).ask(
        messages=[{"role": "user", "content": "parking in Casablanca"}],
        executor=ToolExecutor(FakeInventory(), "jwt"))
    tool_msgs = seen[1]["messages"][-2:]
    assert [m["tool_call_id"] for m in tool_msgs] == ["c1", "c2"]
    assert all(m["role"] == "tool" and json.loads(m["content"]) for m in tool_msgs)


@pytest.mark.asyncio
async def test_muse_missing_tool_call_id_fails_honestly():
    bad_calls = [
        {"type": "function", "function": {"name": "search_facilities", "arguments": "{}"}},
        _tool_call("", "search_facilities", {}),
        _tool_call("   ", "search_facilities", {}),
        {**_tool_call("c1", "search_facilities", {}), "id": 42},
    ]
    for bad in bad_calls:
        svc = configured(lambda req, bad=bad: chat_response(tool_calls=[bad]))
        with pytest.raises(InvalidProviderResponse):
            await svc.ask(messages=[{"role": "user", "content": "hi"}],
                          executor=ToolExecutor(FakeInventory(), "jwt"))


@pytest.mark.asyncio
async def test_muse_malformed_tool_calls_become_typed_errors():
    bad_messages = [
        {"role": "assistant", "content": None, "tool_calls": {"id": "c1"}},  # not a list
        {"role": "assistant", "content": None, "tool_calls": ["bogus"]},  # not an object
        {"role": "assistant", "content": None, "tool_calls": [{"id": "c1"}]},  # no function
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "search_facilities", "arguments": "{not json"}}]},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "search_facilities", "arguments": "[1, 2]"}}]},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "search_facilities", "arguments": {"city": "Casablanca"}}}]},
    ]
    for msg in bad_messages:
        svc = configured(lambda req, msg=msg: httpx.Response(200, json={"choices": [{"message": msg}]}))
        with pytest.raises(InvalidProviderResponse) as ei:
            await svc.ask(messages=[{"role": "user", "content": "hi"}],
                          executor=ToolExecutor(FakeInventory(), "jwt"))
        assert ei.value.code == "invalid_provider_response"  # typed MetaError -> grounded fallback


@pytest.mark.asyncio
async def test_muse_loop_terminates_after_three_tool_rounds():
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(json.loads(req.content))
        if len(seen) <= 3:
            return chat_response(tool_calls=[
                _tool_call(f"c{len(seen)}", "search_facilities", {"city": "Casablanca"})])
        return chat_response(content="Final answer.")

    out = await configured(handler).ask(
        messages=[{"role": "user", "content": "parking in Casablanca"}],
        executor=ToolExecutor(FakeInventory(), "jwt"))
    assert len(seen) == 4  # 3 tool rounds + exactly one final no-tools call
    assert "tools" not in seen[3] and "tool_choice" not in seen[3]
    assert seen[3]["max_completion_tokens"] == 400
    assert "Casa Marina Parking" in out["reply"]


@pytest.mark.asyncio
async def test_muse_payload_contract():
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        if len(seen) == 1:
            return chat_response(tool_calls=[
                _tool_call("c1", "search_facilities", {"city": "Casablanca"})])
        return chat_response(content="done")

    await configured(handler).ask(
        messages=[{"role": "user", "content": "parking in Casablanca"}],
        executor=ToolExecutor(FakeInventory(), "jwt"))
    req = seen[0]
    body = json.loads(req.content)
    assert str(req.url) == "https://api.meta.ai/v1/chat/completions"
    assert req.headers["authorization"] == "Bearer test-key"
    assert body["model"] == "test-model"
    assert body["tool_choice"] == "auto"
    assert body["max_completion_tokens"] == 600 and "max_tokens" not in body
    assert [t["function"]["name"] for t in body["tools"]] == [
        "search_facilities", "get_facility_details", "check_availability",
        "calculate_booking_quote", "search_nearby_facilities"]


def test_muse_default_model_and_env_override(monkeypatch):
    assert Settings().muse_spark_model == "muse-spark-1.3"
    assert Settings().muse_configured is False  # default model alone never enables the LLM
    monkeypatch.setenv("MODEL_API_KEY", "k")
    monkeypatch.setenv("MUSE_SPARK_MODEL", "muse-spark-1.2")
    s = Settings.from_env()
    assert s.muse_spark_model == "muse-spark-1.2" and s.muse_configured is True


@pytest.mark.asyncio
async def test_muse_unverified_prose_is_not_returned():
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return chat_response(tool_calls=[
                _tool_call("c1", "search_facilities", {"city": "Casablanca"})])
        return chat_response(content="Invented Parking Palace has 500 spaces free for 5 MAD/h. Trust me.")

    out = await configured(handler).ask(
        messages=[{"role": "user", "content": "parking in Casablanca"}],
        executor=ToolExecutor(FakeInventory(), "jwt"))
    assert "Invented Parking Palace" not in out["reply"] and "500" not in out["reply"]
    assert "Casa Marina Parking" in out["reply"]
    assert "12.00" in out["reply"] and "14/120" in out["reply"]  # server-verified price/availability


@pytest.mark.asyncio
async def test_muse_wrong_quote_total_is_corrected():
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return chat_response(tool_calls=[
                _tool_call("c1", "calculate_booking_quote", {"facility_id": FACILITY["id"], "hours": 3})])
        return chat_response(content="That will be 999 MAD in total.")

    out = await configured(handler).ask(
        messages=[{"role": "user", "content": "3 hours in Casablanca?"}],
        executor=ToolExecutor(FakeInventory(), "jwt"))
    assert "999" not in out["reply"]
    assert "36.00 MAD" in out["reply"]  # 12 MAD/h x 3h, computed server-side
    assert [f["id"] for f in out["facilities"]] == [FACILITY["id"]]


@pytest.mark.asyncio
async def test_muse_natural_reply_preserved_without_tools():
    svc = configured(lambda req: chat_response(content="Hello! I can help you find parking."))
    out = await svc.ask(messages=[{"role": "user", "content": "hello"}],
                        executor=ToolExecutor(FakeInventory(), "jwt"))
    assert out["reply"] == "Hello! I can help you find parking."
    assert out["facilities"] == []


@pytest.mark.asyncio
async def test_muse_factual_question_without_tool_calls_is_grounded():
    # The model answers a price/availability question from prose, calling no
    # tools. The server-side safeguard must ground it instead of shipping
    # invented numbers.
    svc = configured(lambda req: chat_response(
        content="Casa Marina Parking costs 999 MAD/h and has 500 spaces free right now."))
    out = await svc.ask(messages=[{"role": "user", "content": "How much is parking in Casablanca?"}],
                        executor=ToolExecutor(FakeInventory(), "jwt"))
    assert "999" not in out["reply"] and "500" not in out["reply"]
    assert "Casa Marina Parking" in out["reply"] and "12.00" in out["reply"]  # real row, server price
    assert [f["id"] for f in out["facilities"]] == [FACILITY["id"]]
    assert out["mode"] == "grounded_fallback"  # honestly labeled


@pytest.mark.asyncio
async def test_muse_general_conversation_without_tool_calls_stays_natural():
    svc = configured(lambda req: chat_response(content="Hi there! Great to meet you."))
    out = await svc.ask(messages=[{"role": "user", "content": "hello, how are you today?"}],
                        executor=ToolExecutor(FakeInventory(), "jwt"))
    assert out["reply"] == "Hi there! Great to meet you."
    assert out["facilities"] == []


@pytest.mark.asyncio
async def test_muse_factual_answer_with_tool_results_stays_grounded():
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return chat_response(tool_calls=[
                _tool_call("c1", "search_facilities", {"city": "Casablanca"})])
        return chat_response(content="Invented Parking Palace: 1 MAD/h, 999 spaces free!")

    out = await configured(handler).ask(
        messages=[{"role": "user", "content": "parking in Casablanca"}],
        executor=ToolExecutor(FakeInventory(), "jwt"))
    assert "Invented" not in out["reply"] and "999" not in out["reply"]
    assert "Casa Marina Parking" in out["reply"] and "12.00" in out["reply"]
    assert [f["id"] for f in out["facilities"]] == [FACILITY["id"]]


# ------------------------------------------------------- retry / error policy

def _record_sleeps(monkeypatch):
    """Replace asyncio.sleep with a recorder so backoff timing is asserted
    without the test suite actually waiting."""
    sleeps: list[float] = []

    async def fake_sleep(delay):
        sleeps.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    return sleeps


@pytest.mark.asyncio
async def test_muse_429_honors_numeric_retry_after(monkeypatch):
    sleeps = _record_sleeps(monkeypatch)
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "7"},
                                  json={"error": {"message": "slow down", "type": "rate_limit_error",
                                                  "param": None, "code": "rate_limited"}})
        return chat_response(content="recovered")

    out = await configured(handler).ask(
        messages=[{"role": "user", "content": "hi"}], executor=ToolExecutor(FakeInventory(), "jwt"))
    assert out["reply"] == "recovered" and calls["n"] == 2
    assert len(sleeps) == 1 and 7.0 <= sleeps[0] <= 30.0  # Retry-After wins, capped


@pytest.mark.asyncio
async def test_muse_429_honors_http_date_retry_after(monkeypatch):
    sleeps = _record_sleeps(monkeypatch)
    calls = {"n": 0}
    retry_at = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=12), usegmt=True)

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": retry_at}, json={})
        return chat_response(content="recovered")

    out = await configured(handler).ask(
        messages=[{"role": "user", "content": "hi"}], executor=ToolExecutor(FakeInventory(), "jwt"))
    assert out["reply"] == "recovered" and calls["n"] == 2
    assert len(sleeps) == 1 and 9.0 <= sleeps[0] <= 30.0  # ~12s from the HTTP-date, capped


@pytest.mark.asyncio
async def test_muse_429_without_retry_after_uses_exponential_backoff(monkeypatch):
    sleeps = _record_sleeps(monkeypatch)
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] <= 2:
            return httpx.Response(429, json={})
        return chat_response(content="recovered")

    out = await configured(handler).ask(
        messages=[{"role": "user", "content": "hi"}], executor=ToolExecutor(FakeInventory(), "jwt"))
    assert out["reply"] == "recovered" and calls["n"] == 3
    assert len(sleeps) == 2
    assert 0.5 <= sleeps[0] <= 0.65  # 0.5s base + bounded jitter
    assert sleeps[1] >= 1.0 and sleeps[1] > sleeps[0]  # exponential growth


@pytest.mark.asyncio
async def test_muse_503_and_500_are_retried(monkeypatch):
    _record_sleeps(monkeypatch)
    for status in (500, 503):
        calls = {"n": 0}

        def handler(req: httpx.Request, status=status, calls=calls) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(status, headers={"Retry-After": "3"}, json={})
            return chat_response(content="recovered")

        out = await configured(handler).ask(
            messages=[{"role": "user", "content": "hi"}], executor=ToolExecutor(FakeInventory(), "jwt"))
        assert out["reply"] == "recovered" and calls["n"] == 2


@pytest.mark.asyncio
async def test_muse_504_is_not_retried(monkeypatch):
    _record_sleeps(monkeypatch)
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(504, json={})

    svc = configured(handler)  # default retries=2 — must still fire exactly once
    with pytest.raises(ProviderTimeout) as ei:
        await svc.ask(messages=[{"role": "user", "content": "hi"}],
                      executor=ToolExecutor(FakeInventory(), "jwt"))
    assert ei.value.code == "provider_timeout"  # typed -> API grounded fallback
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_muse_client_errors_are_not_retried(monkeypatch):
    _record_sleeps(monkeypatch)
    expected = {400: InvalidProviderResponse, 401: ProviderUnavailable,
                402: InvalidProviderResponse, 403: ProviderUnavailable,
                404: InvalidProviderResponse, 413: InvalidProviderResponse}
    for status, exc_type in expected.items():
        calls = {"n": 0}

        def handler(req: httpx.Request, status=status, calls=calls) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(status, json={})

        with pytest.raises(exc_type):
            await configured(handler).ask(
                messages=[{"role": "user", "content": "hi"}],
                executor=ToolExecutor(FakeInventory(), "jwt"))
        assert calls["n"] == 1, f"HTTP {status} must not be retried"


@pytest.mark.asyncio
async def test_muse_malformed_success_response_is_not_retried(monkeypatch):
    _record_sleeps(monkeypatch)
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, text="this is not json")

    with pytest.raises(InvalidProviderResponse):
        await configured(handler).ask(
            messages=[{"role": "user", "content": "hi"}], executor=ToolExecutor(FakeInventory(), "jwt"))
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_muse_structured_error_body_is_logged_not_shown(caplog):
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {
            "message": "max_completion_tokens is invalid", "type": "invalid_request_error",
            "param": "max_completion_tokens", "code": "invalid_parameter"}})

    with caplog.at_level(logging.WARNING, logger="parkspot.meta.muse"):
        with pytest.raises(InvalidProviderResponse) as ei:
            await configured(handler).ask(
                messages=[{"role": "user", "content": "hi"}],
                executor=ToolExecutor(FakeInventory(), "jwt"))
    assert ei.value.code == "invalid_provider_response"
    assert "invalid_parameter" in str(ei.value)  # code safely surfaced
    assert "max_completion_tokens is invalid" not in str(ei.value)  # provider prose not user-facing
    assert "invalid_request_error" in caplog.text and "invalid_parameter" in caplog.text
    assert "max_completion_tokens" in caplog.text  # param logged for diagnostics
    assert "test-key" not in caplog.text  # never the credential


@pytest.mark.asyncio
async def test_muse_malformed_error_bodies_are_safe():
    cases = [
        (500, {"text": "<html>gateway oops</html>"}, ProviderUnavailable),  # non-JSON body
        (400, {"json": {"error": "oops-string"}}, InvalidProviderResponse),  # wrong shape
        (429, {"json": ["not", "an", "object"]}, ProviderUnavailable),
    ]
    for status, kwargs, exc_type in cases:
        svc = configured(lambda req, s=status, k=kwargs: httpx.Response(s, **k),
                         provider_max_retries=0)
        with pytest.raises(exc_type):
            await svc.ask(messages=[{"role": "user", "content": "hi"}],
                          executor=ToolExecutor(FakeInventory(), "jwt"))


class _SlowToolTransport(httpx.AsyncBaseTransport):
    """Every request takes 0.15s and asks for another tool round, forever."""

    def __init__(self):
        self.calls = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        await asyncio.sleep(0.15)
        return chat_response(tool_calls=[_tool_call("c1", "search_facilities", {"city": "Casablanca"})])


@pytest.mark.asyncio
async def test_muse_overall_deadline_bounds_all_tool_rounds():
    slow = _SlowToolTransport()
    svc = MuseSparkService(
        Settings(meta_model_api_key="k", muse_spark_model="m",
                 provider_max_retries=0, provider_total_timeout_s=0.4),
        transport=slow)
    started = asyncio.get_running_loop().time()
    with pytest.raises(ProviderTimeout) as ei:
        await svc.ask(messages=[{"role": "user", "content": "parking in Casablanca"}],
                      executor=ToolExecutor(FakeInventory(), "jwt"))
    elapsed = asyncio.get_running_loop().time() - started
    assert ei.value.code == "provider_timeout"
    assert slow.calls >= 2  # several rounds happened — the deadline, not the round cap, stopped it
    assert elapsed < 5  # and it stopped promptly, not after every possible retry


@pytest.mark.asyncio
async def test_muse_deadline_timeout_reaches_grounded_fallback():
    slow = _SlowToolTransport()
    svc = MuseSparkService(
        Settings(meta_model_api_key="k", muse_spark_model="m",
                 provider_max_retries=0, provider_total_timeout_s=0.3),
        transport=slow)
    with pytest.raises(ProviderTimeout) as ei:
        await svc.ask(messages=[{"role": "user", "content": "parking in Casablanca"}],
                      executor=ToolExecutor(FakeInventory(), "jwt"))
    # api.py catches MetaError and re-asks the grounded assistant with a
    # fresh executor — replicate exactly that contract here.
    assert isinstance(ei.value, MetaError)
    out = await GroundedAssistant().ask(
        messages=[{"role": "user", "content": "parking in Casablanca"}],
        executor=ToolExecutor(FakeInventory(), "jwt"), lang="en")
    assert "Casa Marina Parking" in out["reply"]
    assert [f["id"] for f in out["facilities"]] == [FACILITY["id"]]


def test_retry_and_timeout_config_is_clamped(monkeypatch):
    # Defaults preserved.
    d = Settings()
    assert (d.provider_timeout_s, d.provider_max_retries, d.provider_total_timeout_s) == (30.0, 2, 90.0)
    monkeypatch.setenv("META_MAX_RETRIES", "99")
    monkeypatch.setenv("META_TIMEOUT_S", "99999")
    monkeypatch.setenv("META_TOTAL_TIMEOUT_S", "99999")
    s = Settings.from_env()
    assert s.provider_max_retries == 4 and s.provider_timeout_s == 120.0
    assert s.provider_total_timeout_s == 300.0
    monkeypatch.setenv("META_MAX_RETRIES", "-3")
    monkeypatch.setenv("META_TIMEOUT_S", "0")
    monkeypatch.setenv("META_TOTAL_TIMEOUT_S", "1")
    s = Settings.from_env()
    assert s.provider_max_retries == 0 and s.provider_timeout_s == 1.0
    assert s.provider_total_timeout_s == 10.0


# ---------------------------------------------------------------------- tools

@pytest.mark.asyncio
async def test_tool_rejects_unknown_city_and_feature():
    ex = ToolExecutor(FakeInventory(), "jwt")
    with pytest.raises(ValidationFailed):
        await ex.execute("search_facilities", {"city": "Atlantis"})
    with pytest.raises(ValidationFailed):
        await ex.execute("search_facilities", {"feature": "helicopter_pad"})


@pytest.mark.asyncio
async def test_tool_rejects_unknown_tool_and_bad_hours():
    ex = ToolExecutor(FakeInventory(), "jwt")
    with pytest.raises(ValidationFailed):
        await ex.execute("run_sql", {"query": "drop table bookings"})
    with pytest.raises(ValidationFailed):
        await ex.execute("calculate_booking_quote", {"facility_id": FACILITY["id"], "hours": 999})


@pytest.mark.asyncio
async def test_quote_is_server_side_cents_math():
    ex = ToolExecutor(FakeInventory(), "jwt")
    out = await ex.execute("calculate_booking_quote", {"facility_id": FACILITY["id"], "hours": 3})
    assert out == {"found": True, "facility_id": FACILITY["id"], "hours": 3, "total_mad": 36.0, "currency": "MAD"}
    assert quote_cents(FACILITY, 3) == 3600


@pytest.mark.asyncio
async def test_unknown_facility_is_found_false_not_invented():
    ex = ToolExecutor(FakeInventory(), "jwt")
    assert await ex.execute("get_facility_details", {"facility_id": "99999999-9999-9999-9999-999999999999"}) == {"found": False}


@pytest.mark.asyncio
async def test_nearby_tool_needs_shared_location_and_uses_real_coords():
    rows = [{**FACILITY, "id": "near-1", "lat": 33.5800, "lng": -7.5900},
            {**FACILITY, "id": "far-1", "lat": 34.0209, "lng": -6.8416}]
    no_loc = ToolExecutor(FakeInventory(rows), "jwt")
    out = await no_loc.execute("search_nearby_facilities", {})
    assert out["found"] is False and out["reason"] == "location_not_shared"  # model cannot guess GPS
    with_loc = ToolExecutor(FakeInventory(rows), "jwt", coords=(33.5731, -7.5898))
    out = await with_loc.execute("search_nearby_facilities", {"radius_km": 5})
    assert [f["id"] for f in out["facilities"]] == ["near-1"]
    assert out["facilities"][0]["distance_meters"] < 1000


# ------------------------------------------- authorized-capacity (Option A)

def test_effective_available_clamps_to_authorized_capacity():
    # Stale counter above the ParkSpot-authorized ceiling is clamped down.
    assert effective_available({"available": 50, "capacity": 120, "authorized_capacity": 10}) == 10
    # Zero authorized capacity means nothing is sellable, whatever the counter says.
    assert effective_available({"available": 14, "capacity": 120, "authorized_capacity": 0}) == 0
    # Pre-0001 rows without authorized_capacity fall back to legacy capacity.
    assert effective_available({"available": 14, "capacity": 120}) == 14
    assert effective_available({"available": 500, "capacity": 120, "authorized_capacity": None}) == 120
    # Negative counters never surface; missing counters read as zero.
    assert effective_available({"available": -3, "capacity": 120, "authorized_capacity": 10}) == 0
    assert effective_available({"capacity": 120, "authorized_capacity": 10}) == 0


@pytest.mark.asyncio
async def test_tool_availability_never_exceeds_authorized_capacity():
    row = {**FACILITY, "available": 50, "capacity": 120, "authorized_capacity": 10}
    ex = ToolExecutor(FakeInventory([row], facility=row), "jwt")
    out = await ex.execute("search_facilities", {"city": "Casablanca"})
    assert out["facilities"][0]["available"] == 10
    # "capacity" shown to the model is the authorized figure, not physical.
    assert out["facilities"][0]["capacity"] == 10
    out = await ex.execute("check_availability", {"facility_id": row["id"]})
    assert out == {"found": True, "facility_id": row["id"], "available": 10, "capacity": 10}


@pytest.mark.asyncio
async def test_tool_zero_authorized_capacity_reports_zero_available():
    row = {**FACILITY, "available": 14, "capacity": 120, "authorized_capacity": 0}
    ex = ToolExecutor(FakeInventory([row], facility=row), "jwt")
    out = await ex.execute("check_availability", {"facility_id": row["id"]})
    assert out["available"] == 0 and out["capacity"] == 0


@pytest.mark.asyncio
async def test_inventory_search_normalizes_and_drops_zero_authorized():
    rows = [
        {**FACILITY, "id": "zero-auth", "available": 9, "capacity": 120, "authorized_capacity": 0},
        {**FACILITY, "id": "inflated", "available": 50, "capacity": 120, "authorized_capacity": 10},
    ]

    def handler(req: httpx.Request) -> httpx.Response:
        id_filter = req.url.params.get("id", "")
        if id_filter.startswith("eq."):
            return httpx.Response(200, json=[r for r in rows if r["id"] == id_filter[3:]])
        return httpx.Response(200, json=rows)

    s = Settings(supabase_url="http://inventory.test", supabase_publishable_key="test-key")
    inv = Inventory(s, transport=httpx.MockTransport(handler))
    found = await inv.search_facilities(user_jwt="jwt")
    # The zero-authorized facility passes the raw PostgREST `available >= 1`
    # filter but must not surface as bookable after normalization.
    assert [r["id"] for r in found] == ["inflated"]
    assert found[0]["available"] == 10
    one = await inv.get_facility("inflated", user_jwt="jwt")
    assert one is not None and one["available"] == 10


# ------------------------------------------------------------------- SAM 3.1

@pytest.mark.asyncio
async def test_sam_not_configured():
    with pytest.raises(NotConfigured):
        await SamVisionService(Settings()).segment_vehicles(b"x")


@pytest.mark.asyncio
async def test_sam_parses_detections():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"detections": [
            {"label": "car", "score": 0.93, "box": {"x": 0.1, "y": 0.2, "w": 0.4, "h": 0.3}},
            {"label": "license plate", "score": 0.87, "box": {"x": 0.2, "y": 0.4, "w": 0.1, "h": 0.05}},
            {"label": "broken"},
        ]})

    svc = SamVisionService(Settings(sam_service_url="http://sam.local"), transport=transport(handler))
    out = await svc.segment_vehicles(b"jpeg-bytes")
    assert len(out) == 2 and out[0]["label"] == "car"


@pytest.mark.asyncio
async def test_sam_invalid_image_rejected_without_pillow_payloads():
    with pytest.raises(ValidationFailed):
        SamVisionService.validate_image(b"not-an-image", max_bytes=1024)


# -------------------------------------------------------------------- EasyOCR

class FakeReader:
    def __init__(self, results):
        self._results = results

    def readtext(self, _img):
        return self._results


@pytest.mark.asyncio
async def test_ocr_confident_plate_accepted():
    svc = EasyOCRService(Settings(), reader=FakeReader([((0, 0), "12345-A-6", 0.91)]))
    out = await svc.read_plate(b"img")
    assert out == {"plate": "12345A6", "confidence": 0.91, "accepted": True}


@pytest.mark.asyncio
async def test_ocr_uncertain_plate_rejected():
    svc = EasyOCRService(Settings(ocr_min_confidence=0.6), reader=FakeReader([((0, 0), "12345A6", 0.31)]))
    out = await svc.read_plate(b"img")
    assert out["accepted"] is False  # never grant access on a guess


@pytest.mark.asyncio
async def test_ocr_no_text():
    svc = EasyOCRService(Settings(), reader=FakeReader([]))
    assert (await svc.read_plate(b"img"))["plate"] is None


# ----------------------------------------------------------------------- voice

def _make_wav(seconds: float = 0.1, channels: int = 1, rate: int = 16000) -> bytes:
    """A real, parseable PCM WAV (silence) for pipeline tests."""
    frames = int(seconds * rate)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * channels * frames)
    return buf.getvalue()


def _wav_info(data: bytes) -> dict:
    with wave.open(io.BytesIO(data), "rb") as w:
        return {"channels": w.getnchannels(), "rate": w.getframerate(),
                "width": w.getsampwidth(), "frames": w.getnframes()}


WAV_BYTES = _make_wav()


@pytest.mark.asyncio
async def test_voice_disabled_by_default():
    with pytest.raises(NotConfigured):
        await MuseVoiceService(Settings()).transcribe(WAV_BYTES, "audio/wav")


@pytest.mark.asyncio
async def test_voice_rejects_unsupported_language_and_type():
    from app.meta.services.muse_voice import ensure_wav
    s = Settings(muse_voice_enabled=True, meta_voice_api_key="k")
    svc = MuseVoiceService(s)
    with pytest.raises(ValidationFailed):
        await svc.transcribe(WAV_BYTES, "audio/wav", language="darija")  # not claimed as supported
    with pytest.raises(ValidationFailed):
        await ensure_wav(b"audio", "video/mp4", 30)


@pytest.mark.asyncio
async def test_voice_wav_passthrough_and_conversion_unavailable(monkeypatch):
    import shutil

    from app.meta.services.muse_voice import ensure_wav
    assert await ensure_wav(WAV_BYTES, "audio/wav", 30) == WAV_BYTES
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    with pytest.raises(ProviderUnavailable):  # honest failure, never sends WebM as-is
        await ensure_wav(b"webm-bytes", "audio/webm", 30)


@pytest.mark.asyncio
async def test_voice_wav_duration_is_capped():
    from app.meta.services.muse_voice import ensure_wav
    out = await ensure_wav(_make_wav(seconds=2), "audio/wav", 1)
    info = _wav_info(out)
    assert info["channels"] == 1 and info["rate"] == 16000 and info["width"] == 2
    assert info["frames"] <= 16000  # ≤ 1 s at 16 kHz


@pytest.mark.asyncio
async def test_voice_nonconforming_wav_needs_ffmpeg(monkeypatch):
    import shutil

    from app.meta.services.muse_voice import ensure_wav
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    with pytest.raises(ProviderUnavailable):  # stereo 48 kHz WAV must be converted, not passed through
        await ensure_wav(_make_wav(channels=2, rate=48000), "audio/wav", 30)


@pytest.mark.asyncio
async def test_voice_invalid_wav_and_unsupported_format_rejected():
    from app.meta.services.muse_voice import ensure_wav
    with pytest.raises(ValidationFailed):  # RIFF header but unparseable body
        await ensure_wav(b"RIFF$\x00\x00\x00WAVEfmt " + b"\x00" * 32, "audio/wav", 30)
    with pytest.raises(ValidationFailed):  # not on the accepted-type list
        await ensure_wav(b"flac-bytes", "audio/flac", 30)


def test_voice_upload_limit_has_one_config_source():
    s = Settings(muse_voice_max_upload_mb=2, muse_voice_max_seconds=45)
    svc = MuseVoiceService(s)
    assert s.audio_upload_limit_bytes == svc._max_bytes == 2 * 1024 * 1024
    assert s.public_status()["voice_max_seconds"] == 45
    with pytest.raises(ValidationFailed):
        svc.validate_upload(b"x" * (2 * 1024 * 1024 + 1), "audio/webm")


@pytest.mark.asyncio
async def test_voice_transcribes_with_documented_multipart_shape():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["path"] = req.url.path
        seen["auth"] = req.headers.get("authorization")
        seen["body"] = req.content.decode("utf-8", "ignore")
        return httpx.Response(200, json={"text": "بغيت موقف في كازا"})

    s = Settings(muse_voice_enabled=True, meta_voice_api_key="k",
                 meta_voice_base_url="http://voice.local", muse_voice_model="muse-voice-transcribe-1.0")
    out = await MuseVoiceService(s, transport=transport(handler)).transcribe(WAV_BYTES, "audio/wav", language="ar")
    assert out["text"].startswith("بغيت")
    assert seen["path"] == "/asr/transcribe"
    assert seen["auth"] == "Bearer k"
    assert '"mode": "PUSH_TO_TALK"' in seen["body"]
    assert '"audioEncoding": "WAV"' in seen["body"]
    assert "k" not in out["text"]


@pytest.mark.asyncio
async def test_voice_empty_transcript_rejected():
    s = Settings(muse_voice_enabled=True, meta_voice_api_key="k", meta_voice_base_url="http://v.local")
    svc = MuseVoiceService(s, transport=transport(lambda req: httpx.Response(200, json={"text": "  "})))
    with pytest.raises(ValidationFailed):
        await svc.transcribe(WAV_BYTES, "audio/wav")


# ------------------------------------------------------------------ GPS nearby

def test_haversine_known_distance():
    from app.meta.geo import haversine_m
    # Casablanca (33.5731,-7.5898) → Rabat (34.0209,-6.8416) ≈ 84 km
    d = haversine_m(33.5731, -7.5898, 34.0209, -6.8416)
    assert 80_000 < d < 88_000


def test_nearby_sorts_filters_and_validates():
    from app.meta.geo import nearby_facilities
    rows = [
        {**FACILITY, "id": "far", "lat": 34.0209, "lng": -6.8416},
        {**FACILITY, "id": "near", "lat": 33.5800, "lng": -7.5900},
        {**FACILITY, "id": "nocoords", "lat": None, "lng": None},
    ]
    out = nearby_facilities(rows, lat=33.5731, lng=-7.5898, radius_km=5)
    assert [r["id"] for r in out] == ["near"]  # far excluded by radius, no-coords skipped
    assert out[0]["distance_meters"] < 1000
    with pytest.raises(ValidationFailed):
        nearby_facilities(rows, lat=91.0, lng=0.0, radius_km=5)
    with pytest.raises(ValidationFailed):
        nearby_facilities(rows, lat=0.0, lng=-181.0, radius_km=5)
    wide = nearby_facilities(rows, lat=33.5731, lng=-7.5898, radius_km=500, max_radius_km=50)
    assert all(r["distance_meters"] <= 50_000 for r in wide)  # radius clamped to max


# ------------------------------------------------------------------ status API

def test_status_never_exposes_secrets():
    s = Settings(meta_model_api_key="super-secret-value", muse_spark_model="m")
    status = s.public_status()
    assert "super-secret-value" not in json.dumps(status)
    assert status["assistant"] == "meta"


def test_placeholder_env_values_count_as_unconfigured(monkeypatch):
    # A copied-but-unfilled .env must not make the status claim "meta".
    monkeypatch.setenv("MODEL_API_KEY", "sk-REPLACE_ME")
    monkeypatch.setenv("MUSE_SPARK_MODEL", "some-model")
    s = Settings.from_env()
    assert s.muse_configured is False
    assert s.public_status()["assistant"] == "grounded_fallback"


def test_placeholder_supabase_values_count_as_unset(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://YOUR_PROJECT.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_REPLACE_ME")
    s = Settings.from_env()
    assert s.supabase_url is None
    assert s.supabase_publishable_key is None


def test_sam_requires_a_real_http_url():
    assert Settings(sam_service_url="LLM_2187466105533446_not-a-url").sam_configured is False
    assert Settings(sam_service_url="https://sam.internal:9000").sam_configured is True
    assert Settings(sam_service_url=None).sam_configured is False
