"""Super Admin API tests — fake authenticator + in-memory PostgREST.

No network, no Supabase, no secrets. The whole FastAPI admin router is
exercised over HTTP (TestClient) with the database replaced by an
httpx.MockTransport that emulates the PostgREST endpoints the admin
layer uses. Run:  pytest tests/test_admin.py -q
"""
from __future__ import annotations

import json
import uuid

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.meta.admin import build_admin_router
from app.meta.auth import Caller
from app.meta.config import Settings
from app.meta.errors import Forbidden, MetaError, Unauthorized
from app.meta.flags import FLAGS

ADMIN_ID = "11111111-1111-1111-1111-111111111111"
ADMIN2_ID = "22222222-2222-2222-2222-222222222222"
DRIVER_ID = "33333333-3333-3333-3333-333333333333"
GHOST_ID = "99999999-9999-9999-9999-999999999999"
FACILITY_ID = "44444444-4444-4444-4444-444444444444"
BOOKING_ID = "55555555-5555-5555-5555-555555555555"
NOW = "2026-10-30T10:00:00+00:00"

ADMIN = {"Authorization": "Bearer admin-token"}
ADMIN2 = {"Authorization": "Bearer admin2-token"}
PARTNER = {"Authorization": "Bearer partner-token"}
DRIVER = {"Authorization": "Bearer driver-token"}


class FakeAuth:
    """Maps test tokens to server-verified callers, like Authenticator."""

    async def require_user(self, authorization: str | None) -> Caller:
        if not authorization or not authorization.startswith("Bearer "):
            raise Unauthorized("Sign in required.")
        token = authorization[7:]
        table = {
            "admin-token": Caller(ADMIN_ID, "admin-token", ["admin"]),
            "admin2-token": Caller(ADMIN2_ID, "admin2-token", ["admin"]),
            "partner-token": Caller(DRIVER_ID, "partner-token", ["partner"]),
            "driver-token": Caller(DRIVER_ID, "driver-token", ["user"]),
        }
        if token not in table:
            raise Unauthorized("Session expired or invalid.")
        return table[token]


class FakeDB:
    """Minimal PostgREST emulation for the tables admin.py touches."""

    RESERVED = {"select", "order", "limit", "offset", "on_conflict"}

    def __init__(self) -> None:
        self.profiles = [
            {"id": ADMIN_ID, "display_name": "Root Admin", "phone": None,
             "vehicle_plate": "11111A1", "vehicle_model": None,
             "status": "active", "created_at": NOW},
            {"id": DRIVER_ID, "display_name": "Driver One", "phone": "+212600000000",
             "vehicle_plate": "22222B2", "vehicle_model": "Clio",
             "status": "active", "created_at": NOW},
        ]
        self.user_roles = [
            {"user_id": ADMIN_ID, "role": "admin"},
            {"user_id": DRIVER_ID, "role": "user"},
        ]
        self.facilities = [
            {"id": FACILITY_ID, "name": "Casa Marina", "name_ar": "كازا مارينا",
             "city": "Casablanca", "address": "Bd Mohammed V", "lat": 33.59,
             "lng": -7.62, "capacity": 50, "total_capacity": 100,
             "authorized_capacity": 50, "available": 20,
             "price_per_hour_cents": 1500, "features": [], "open_24h": True,
             "active": True},
        ]
        self.bookings = [
            {"id": BOOKING_ID, "user_id": DRIVER_ID, "facility_id": FACILITY_ID,
             "start_at": "2026-11-01T10:00:00+00:00",
             "end_at": "2026-11-01T12:00:00+00:00", "hours": 2,
             "total_cents": 3000, "refunded_cents": 0, "status": "confirmed",
             "access_code": "1234", "created_at": NOW},
        ]
        self.wallets = [
            {"user_id": DRIVER_ID, "available_cents": 5000, "reserved_cents": 0,
             "total_deposited_cents": 5000, "is_demo": True, "updated_at": NOW},
        ]
        self.wallet_transactions: list[dict] = []
        self.cameras: list[dict] = []
        self.camera_events: list[dict] = []
        self.incidents: list[dict] = []
        self.app_settings: list[dict] = []
        self.audit_logs: list[dict] = []
        self.rpc_calls: list[tuple[str, dict]] = []

    # ------------------------------------------------------------- helpers
    def _filter(self, rows: list[dict], params) -> list[dict]:
        out = list(rows)
        for key, value in params.multi_items():
            if key in self.RESERVED:
                continue
            if value.startswith("eq."):
                want = value[3:]
                out = [r for r in out if str(r.get(key)) == want]
        return out

    # ------------------------------------------------------------ transport
    async def handle(self, request: httpx.Request) -> httpx.Response:
        parts = [p for p in request.url.path.split("/") if p]
        params = request.url.params
        body = json.loads(request.content) if request.content else {}
        if len(parts) == 4 and parts[:3] == ["rest", "v1", "rpc"]:
            return self._rpc(parts[3], body)
        if len(parts) != 3 or parts[:2] != ["rest", "v1"]:
            return httpx.Response(404, json={"message": "not found"})
        table = parts[2]
        rows = getattr(self, table, None)
        if rows is None:
            return httpx.Response(404, json={"message": f"table {table} missing"})
        if request.method == "GET":
            out = self._filter(rows, params)
            if params.get("limit"):
                out = out[: int(params["limit"])]
            return httpx.Response(200, json=out)
        if request.method == "POST":
            if table == "app_settings":
                rows[:] = [r for r in rows if r["key"] != body["key"]]
                rows.append({"key": body["key"], "value": body["value"]})
                return httpx.Response(201, json=[])
            if table == "audit_logs":
                rows.append(body)
                return httpx.Response(201, json=[body])
            row = dict(body)
            row.setdefault("id", str(uuid.uuid4()))
            rows.append(row)
            return httpx.Response(201, json=[row])
        if request.method == "PATCH":
            for r in self._filter(rows, params):
                r.update(body)
            return httpx.Response(204)
        if request.method == "DELETE":
            doomed = self._filter(rows, params)
            rows[:] = [r for r in rows if r not in doomed]
            return httpx.Response(204)
        return httpx.Response(405, json={"message": "method"})

    def _rpc(self, name: str, body: dict) -> httpx.Response:
        self.rpc_calls.append((name, body))
        if name == "admin_cancel_booking":
            for b in self.bookings:
                if b["id"] == body["p_booking_id"]:
                    b["status"] = "cancelled"
            return httpx.Response(200, json={"id": body["p_booking_id"],
                                             "status": "cancelled",
                                             "refunded_cents": 3000})
        if name == "admin_adjust_wallet":
            wallet = next((w for w in self.wallets
                           if w["user_id"] == body["p_user_id"]), None)
            if wallet is None:
                return httpx.Response(400, json={"message": "NO_WALLET"})
            if wallet["available_cents"] + body["p_amount_cents"] < 0:
                return httpx.Response(400, json={"message": "INSUFFICIENT_FUNDS"})
            wallet["available_cents"] += body["p_amount_cents"]
            tx = {"id": str(uuid.uuid4()), "user_id": body["p_user_id"],
                  "type": "adjustment", "amount_cents": body["p_amount_cents"],
                  "status": "posted", "created_at": NOW}
            self.wallet_transactions.append(tx)
            return httpx.Response(200, json=tx)
        return httpx.Response(404, json={"message": "unknown rpc"})


def make_client(db: FakeDB, **settings_overrides) -> TestClient:
    settings = Settings(supabase_url="https://fake.supabase.co",
                        supabase_publishable_key="publishable-test",
                        **settings_overrides)
    app = FastAPI()

    @app.exception_handler(MetaError)
    async def _meta_error_handler(_req: Request, exc: MetaError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code,
                            content={"error": {"code": exc.code, "message": exc.message}})

    app.include_router(build_admin_router(settings, FakeAuth(),
                                          httpx.MockTransport(db.handle)))
    return TestClient(app)


@pytest.fixture()
def env():
    db = FakeDB()
    return make_client(db), db


# ------------------------------------------------------------------- authz

def test_unauthenticated_rejected(env):
    client, _ = env
    r = client.get("/api/v1/admin/overview")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_driver_forbidden(env):
    client, _ = env
    r = client.get("/api/v1/admin/overview", headers=DRIVER)
    assert r.status_code == 403


def test_partner_forbidden(env):
    client, _ = env
    r = client.get("/api/v1/admin/overview", headers=PARTNER)
    assert r.status_code == 403


def test_admin_overview(env):
    client, _ = env
    r = client.get("/api/v1/admin/overview", headers=ADMIN)
    assert r.status_code == 200
    data = r.json()
    assert data["users_total"] == 2
    assert data["users_by_role"] == {"admin": 1, "user": 1}
    assert data["spaces_authorized"] == 50
    assert data["bookings_by_status"] == {"confirmed": 1}
    assert data["revenue_cents"] == 3000
    assert data["revenue_is_demo"] is True


# ------------------------------------------------------------------- users

def test_users_list_embeds_roles(env):
    client, _ = env
    r = client.get("/api/v1/admin/users", headers=ADMIN)
    assert r.status_code == 200
    by_id = {u["id"]: u for u in r.json()["users"]}
    assert by_id[DRIVER_ID]["roles"] == ["user"]
    assert by_id[ADMIN_ID]["roles"] == ["admin"]


def test_user_detail_unknown_422(env):
    client, _ = env
    assert client.get(f"/api/v1/admin/users/{GHOST_ID}", headers=ADMIN).status_code == 422


def test_invalid_uuid_422(env):
    client, _ = env
    assert client.get("/api/v1/admin/users/not-a-uuid", headers=ADMIN).status_code == 422


def test_suspend_user_writes_audit(env):
    client, db = env
    r = client.post(f"/api/v1/admin/users/{DRIVER_ID}/suspend",
                    headers=ADMIN, json={"reason": "Fraud investigation"})
    assert r.status_code == 200
    assert db.profiles[1]["status"] == "suspended"
    audit = [a for a in db.audit_logs if a["action"] == "user.suspend"]
    assert len(audit) == 1
    assert audit[0]["reason"] == "Fraud investigation"
    assert audit[0]["actor_id"] == ADMIN_ID


def test_suspend_self_blocked(env):
    client, _ = env
    r = client.post(f"/api/v1/admin/users/{ADMIN_ID}/suspend",
                    headers=ADMIN, json={"reason": "testing self suspend"})
    assert r.status_code == 422


def test_revoke_last_admin_blocked(env):
    client, _ = env
    r = client.post(f"/api/v1/admin/users/{ADMIN_ID}/roles",
                    headers=ADMIN,
                    json={"role": "admin", "action": "revoke", "reason": "cleanup"})
    assert r.status_code == 422
    assert "last" in r.json()["error"]["message"].lower()


def test_revoke_admin_allowed_with_second_admin(env):
    client, db = env
    db.user_roles.append({"user_id": ADMIN2_ID, "role": "admin"})
    r = client.post(f"/api/v1/admin/users/{ADMIN2_ID}/roles",
                    headers=ADMIN,
                    json={"role": "admin", "action": "revoke", "reason": "Rotation"})
    assert r.status_code == 200
    assert {"user_id": ADMIN2_ID, "role": "admin"} not in db.user_roles
    assert any(a["action"] == "role.revoke" for a in db.audit_logs)


def test_grant_role_writes_audit(env):
    client, db = env
    r = client.post(f"/api/v1/admin/users/{DRIVER_ID}/roles",
                    headers=ADMIN,
                    json={"role": "partner", "action": "grant", "reason": "Facility partner"})
    assert r.status_code == 200
    assert "partner" in r.json()["roles"]
    assert any(a["action"] == "role.grant" for a in db.audit_logs)


def test_reason_too_short_422(env):
    client, _ = env
    r = client.post(f"/api/v1/admin/users/{DRIVER_ID}/suspend",
                    headers=ADMIN, json={"reason": "no"})
    assert r.status_code == 422


# --------------------------------------------------------------- facilities

def test_authorized_cannot_exceed_total(env):
    client, _ = env
    body = {"name": "Test Park", "name_ar": "موقف تجريبي", "city": "Rabat",
            "address": "Av. X", "lat": 34.0, "lng": -6.8,
            "price_per_hour_cents": 1000, "total_capacity": 100,
            "authorized_capacity": 120, "available": 10}
    r = client.post("/api/v1/admin/facilities", headers=ADMIN, json=body)
    assert r.status_code == 422
    assert "exceed total" in r.json()["error"]["message"]


def test_available_cannot_exceed_authorized(env):
    client, _ = env
    body = {"name": "Test Park", "name_ar": "موقف تجريبي", "city": "Rabat",
            "address": "Av. X", "lat": 34.0, "lng": -6.8,
            "price_per_hour_cents": 1000, "total_capacity": 100,
            "authorized_capacity": 50, "available": 60}
    r = client.post("/api/v1/admin/facilities", headers=ADMIN, json=body)
    assert r.status_code == 422
    assert "exceed authorized" in r.json()["error"]["message"]


def test_create_facility_syncs_legacy_capacity(env):
    client, db = env
    body = {"name": "Test Park", "name_ar": "موقف تجريبي", "city": "Rabat",
            "address": "Av. X", "lat": 34.0, "lng": -6.8,
            "price_per_hour_cents": 1000, "total_capacity": 100,
            "authorized_capacity": 40, "available": 40}
    r = client.post("/api/v1/admin/facilities", headers=ADMIN, json=body)
    assert r.status_code == 200
    created = db.facilities[-1]
    assert created["capacity"] == 40  # legacy column synced to authorized
    assert any(a["action"] == "facility.create" for a in db.audit_logs)


def test_authorized_below_active_bookings_blocked(env):
    client, _ = env
    r = client.patch(f"/api/v1/admin/facilities/{FACILITY_ID}",
                     headers=ADMIN,
                     json={"authorized_capacity": 0, "reason": "Reduce capacity"})
    assert r.status_code == 422
    assert "active reservations" in r.json()["error"]["message"]


# ------------------------------------------------------------------ pricing

def test_price_below_bounds_rejected(env):
    client, _ = env
    r = client.patch(f"/api/v1/admin/facilities/{FACILITY_ID}/price",
                     headers=ADMIN,
                     json={"price_per_hour_cents": 50, "reason": "Promo"})
    assert r.status_code == 422


def test_price_update_writes_audit(env):
    client, db = env
    r = client.patch(f"/api/v1/admin/facilities/{FACILITY_ID}/price",
                     headers=ADMIN,
                     json={"price_per_hour_cents": 2000, "reason": "Peak season"})
    assert r.status_code == 200
    assert db.facilities[0]["price_per_hour_cents"] == 2000
    audit = [a for a in db.audit_logs if a["action"] == "pricing.update"]
    assert audit and audit[0]["metadata"]["price_per_hour_cents"] == 2000


# ----------------------------------------------------------------- bookings

def test_cancel_requires_reason(env):
    client, _ = env
    r = client.post(f"/api/v1/admin/bookings/{BOOKING_ID}/cancel",
                    headers=ADMIN, json={"reason": "no"})
    assert r.status_code == 422


def test_cancel_booking_calls_rpc(env):
    client, db = env
    r = client.post(f"/api/v1/admin/bookings/{BOOKING_ID}/cancel",
                    headers=ADMIN, json={"reason": "Facility emergency closure"})
    assert r.status_code == 200
    assert ("admin_cancel_booking",
            {"p_booking_id": BOOKING_ID,
             "p_reason": "Facility emergency closure"}) in db.rpc_calls
    assert db.bookings[0]["status"] == "cancelled"


# ------------------------------------------------------------------ wallets

def test_wallet_adjust_zero_rejected(env):
    client, _ = env
    r = client.post(f"/api/v1/admin/wallets/{DRIVER_ID}/adjust",
                    headers=ADMIN, json={"amount_cents": 0, "reason": "noop test"})
    assert r.status_code == 422


def test_wallet_adjust_negative_balance_rejected(env):
    client, _ = env
    r = client.post(f"/api/v1/admin/wallets/{DRIVER_ID}/adjust",
                    headers=ADMIN, json={"amount_cents": -999999, "reason": "Chargeback"})
    assert r.status_code == 422
    assert "negative" in r.json()["error"]["message"]


def test_wallet_adjust_ok(env):
    client, db = env
    r = client.post(f"/api/v1/admin/wallets/{DRIVER_ID}/adjust",
                    headers=ADMIN, json={"amount_cents": 1000, "reason": "Goodwill credit"})
    assert r.status_code == 200
    assert db.wallets[0]["available_cents"] == 6000
    assert r.json()["transaction"]["type"] == "adjustment"


# ------------------------------------------------------------------ reports

def test_reports_summary(env):
    client, _ = env
    r = client.get("/api/v1/admin/reports?days=30", headers=ADMIN)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1 and data["cancelled"] == 0
    assert data["facility_performance"][0]["name"] == "Casa Marina"
    assert data["revenue_is_demo"] is True


def test_csv_export_admin_only_and_audited(env):
    client, db = env
    assert client.get("/api/v1/admin/reports/bookings.csv",
                      headers=DRIVER).status_code == 403
    r = client.get("/api/v1/admin/reports/bookings.csv", headers=ADMIN)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert r.text.startswith("id,user_id,facility_id")
    assert any(a["action"] == "report.export" for a in db.audit_logs)


# ----------------------------------------------------------------- settings

def test_settings_allowlist_rejects_unknown(env):
    client, _ = env
    r = client.patch("/api/v1/admin/settings", headers=ADMIN,
                     json={"settings": {"shell_command": "rm -rf /"}, "reason": "test"})
    assert r.status_code == 422
    assert "Arbitrary settings" in r.json()["error"]["message"]


def test_settings_wrong_type_rejected(env):
    client, _ = env
    r = client.patch("/api/v1/admin/settings", headers=ADMIN,
                     json={"settings": {"hold_expiry_minutes": "soon"}, "reason": "test"})
    assert r.status_code == 422


def test_settings_update_ok(env):
    client, db = env
    r = client.patch("/api/v1/admin/settings", headers=ADMIN,
                     json={"settings": {"app_name": "ParkSpot"}, "reason": "Branding"})
    assert r.status_code == 200
    assert {"key": "app_name", "value": "ParkSpot"} in db.app_settings
    assert any(a["action"] == "settings.update" for a in db.audit_logs)


# ----------------------------------------------------------------------- AI

def test_ai_status_never_leaks_secrets(env):
    db = FakeDB()
    client = make_client(db, meta_model_api_key="sk-TESTSECRET",
                         muse_spark_model="test-model-1")
    r = client.get("/api/v1/admin/ai/status", headers=ADMIN)
    assert r.status_code == 200
    assert "sk-TESTSECRET" not in r.text
    spark = r.json()["services"]["muse_spark"]
    assert spark["configured"] is True
    assert spark["model"] == "test-model-1"
    assert spark["base_url_host"] == "api.meta.ai"


def test_ai_health_easyocr_is_safe(env):
    client, _ = env
    r = client.post("/api/v1/admin/ai/health/easyocr", headers=ADMIN)
    assert r.status_code == 200
    data = r.json()
    assert data["service"] == "easyocr"
    assert set(data) >= {"configured", "reachable", "tested_ok", "detail"}


def test_ai_toggle_writes_audit(env):
    client, db = env
    try:
        r = client.post("/api/v1/admin/ai/toggle", headers=ADMIN,
                        json={"feature": "voice", "enabled": False,
                              "reason": "Incident response"})
        assert r.status_code == 200
        assert FLAGS.get("voice") is False
        assert any(a["action"] == "ai.toggle" for a in db.audit_logs)
    finally:
        FLAGS.set("voice", True)


# ------------------------------------------------------- cameras / incidents

def test_camera_create_and_disable(env):
    client, db = env
    r = client.post("/api/v1/admin/cameras", headers=ADMIN,
                    json={"label": "Gate A camera"})
    assert r.status_code == 200
    cam_id = db.cameras[0]["id"]
    r = client.patch(f"/api/v1/admin/cameras/{cam_id}", headers=ADMIN,
                     json={"status": "inactive", "reason": "Maintenance"})
    assert r.status_code == 200
    assert db.cameras[0]["status"] == "inactive"


def test_incident_lifecycle(env):
    client, db = env
    r = client.post("/api/v1/admin/incidents", headers=ADMIN,
                    json={"kind": "user_report", "title": "Gate blocked"})
    assert r.status_code == 200
    inc_id = db.incidents[0]["id"]
    r = client.patch(f"/api/v1/admin/incidents/{inc_id}", headers=ADMIN,
                     json={"status": "resolved", "reason": "Cleared"})
    assert r.status_code == 200
    assert db.incidents[0]["status"] == "resolved"
    assert any(a["action"] == "incident.update" for a in db.audit_logs)


def test_audit_endpoint_filters_by_action(env):
    client, db = env
    client.post(f"/api/v1/admin/users/{DRIVER_ID}/suspend",
                headers=ADMIN, json={"reason": "Fraud investigation"})
    r = client.get("/api/v1/admin/audit?action=user.suspend", headers=ADMIN)
    assert r.status_code == 200
    assert r.json()["entries"][0]["action"] == "user.suspend"
