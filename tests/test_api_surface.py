"""Public surface of the FastAPI app: liveness, status, and module gating.

Imports the real ``app.meta.api`` module (settings come from env/.env on
this machine, so only shapes and switch behaviour are asserted — never
provider values). Provider services are stubbed so no network is used.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.meta import api as api_module
from app.meta.auth import Caller
from app.meta.errors import MetaError
from app.meta.flags import FLAGS

USER = Caller(user_id="u-1", jwt="x.y.z", roles=["user"])
OPS = Caller(user_id="u-2", jwt="x.y.z", roles=["partner"])


class _Auth:
    def __init__(self, caller: Caller):
        self._c = caller

    async def require_user(self, _authorization):
        return self._c

    async def require_ops(self, _authorization):
        return self._c


class _Grounded:
    async def ask(self, *, messages, executor, lang="en"):
        return {"mode": "grounded_fallback", "reply": "grounded", "facilities": []}


class _MuseMustNotRun:
    async def ask(self, **_kw):
        raise AssertionError("Muse Spark must not be called while switched off")


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(api_module, "grounded", _Grounded())
    monkeypatch.setattr(api_module, "muse", _MuseMustNotRun())
    api_module._hits.clear()
    with TestClient(api_module.app) as c:
        yield c


def test_healthz_is_public_and_identifies_the_process(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert set(body) == {"status", "instance_id", "started_at", "uptime_s", "version"}
    assert client.get("/healthz").json()["instance_id"] == body["instance_id"]  # stable within a process


def test_public_status_has_modules_and_backend_but_no_secrets(client):
    body = client.get("/api/v1/meta/status").json()
    assert set(body["modules"]) == {"muse_spark", "muse_voice", "sam", "easyocr"}
    assert set(body["backend"]) == {"instance_id", "started_at", "uptime_s", "version"}
    assert body["assistant"] in {"meta", "grounded_fallback"}
    text = r"".join(str(v) for v in body.values())
    assert "sk-" not in text and "Bearer" not in text


def test_public_status_reflects_switches(client):
    try:
        FLAGS.set("muse_spark", False)
        FLAGS.set("muse_voice", False)
        FLAGS.set("sam", False)
        body = client.get("/api/v1/meta/status").json()
        assert body["assistant"] == "grounded_fallback"
        assert body["voice"] == "disabled"
        assert body["vision_sam"] == "disabled"
        assert body["modules"]["muse_spark"] is False
    finally:
        for m in ("muse_spark", "muse_voice", "sam"):
            FLAGS.set(m, True)


def test_chat_falls_back_to_grounded_when_muse_spark_switched_off(client, monkeypatch):
    monkeypatch.setattr(api_module, "auth", _Auth(USER))
    try:
        FLAGS.set("muse_spark", False)
        r = client.post("/api/v1/meta/assistant/chat", headers={"Authorization": "Bearer x.y.z"},
                        json={"messages": [{"role": "user", "content": "parking in Casablanca"}]})
        assert r.status_code == 200
        assert r.json()["mode"] == "grounded_fallback"
    finally:
        FLAGS.set("muse_spark", True)


def test_vision_blocked_when_sam_switched_off(client, monkeypatch):
    monkeypatch.setattr(api_module, "auth", _Auth(OPS))
    try:
        FLAGS.set("sam", False)
        r = client.post("/api/v1/meta/vision/analyze", headers={"Authorization": "Bearer x.y.z"},
                        files={"image": ("f.jpg", b"\xff\xd8\xff", "image/jpeg")})
        assert r.status_code == 503
        err = r.json()["error"]
        assert err["code"] == "not_configured" and "SAM 3.1" in err["message"]
    finally:
        FLAGS.set("sam", True)


def test_vision_skips_ocr_when_easyocr_switched_off(client, monkeypatch):
    monkeypatch.setattr(api_module, "auth", _Auth(OPS))
    seen = {}

    class _Access:
        async def analyze(self, **kw):
            seen.update(kw)
            return {"vehicles_detected": 1, "detections": [], "plate_region_found": False,
                    "plate": None, "ocr_confidence": 0.0, "ocr_accepted": False,
                    "verified_booking": None, "access": "not_granted", "reason": "ocr_disabled"}

    class _Inventory:
        async def insert(self, *_a, **_k):
            return None

    monkeypatch.setattr(api_module, "access_svc", _Access())
    monkeypatch.setattr(api_module, "inventory", _Inventory())
    try:
        FLAGS.set("easyocr", False)
        r = client.post("/api/v1/meta/vision/analyze", headers={"Authorization": "Bearer x.y.z"},
                        files={"image": ("f.jpg", b"\xff\xd8\xff", "image/jpeg")})
        assert r.status_code == 200
        assert seen["ocr_enabled"] is False
        assert r.json()["reason"] == "ocr_disabled" and r.json()["access"] == "not_granted"
    finally:
        FLAGS.set("easyocr", True)


def test_voice_blocked_when_switched_off(client, monkeypatch):
    monkeypatch.setattr(api_module, "auth", _Auth(USER))
    try:
        FLAGS.set("muse_voice", False)
        r = client.post("/api/v1/meta/voice/transcribe", headers={"Authorization": "Bearer x.y.z"},
                        files={"audio": ("v.wav", b"RIFF0000WAVE", "audio/wav")})
        assert r.status_code == 503
        assert "Muse Voice" in r.json()["error"]["message"]
    finally:
        FLAGS.set("muse_voice", True)


@pytest.mark.asyncio
async def test_access_service_reports_ocr_disabled_without_reading(monkeypatch):
    from app.meta.access import AccessVerificationService
    from app.meta.config import Settings
    from app.meta.services.sam_vision import SamVisionService

    class _Sam(SamVisionService):
        async def segment_vehicles(self, image, content_type="image/jpeg"):
            return [{"label": "car", "score": 0.9, "box": {"x": 0, "y": 0, "w": 1, "h": 1}}]

    class _Ocr:
        async def read_plate(self, *_a, **_k):
            raise AssertionError("OCR must not run when disabled")

    monkeypatch.setattr(SamVisionService, "validate_image", staticmethod(lambda data, *, max_bytes: "jpeg"))
    svc = AccessVerificationService(_Sam(Settings(sam_service_url="https://sam.internal")), _Ocr(), None)
    res = await svc.analyze(image=b"img", content_type="image/jpeg", user_jwt="j", ocr_enabled=False)
    assert res["reason"] == "ocr_disabled" and res["access"] == "not_granted"
    assert res["vehicles_detected"] == 1 and res["ocr_accepted"] is False
