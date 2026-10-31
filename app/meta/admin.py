"""Super Admin Control Center API.

Every endpoint requires an authenticated caller whose *server-verified*
roles include ``admin`` (checked against Supabase on each request via
:class:`Authenticator`) — frontend hiding is never the authorization.
Data access uses the caller's own JWT against PostgREST, so the admin RLS
policies in ``drizzle/migrations/0001_admin.sql`` are the second layer.

Money moves only through SECURITY DEFINER functions
(``admin_adjust_wallet``, ``admin_cancel_booking``) which also write the
audit row in the same transaction. Other mutations write audit entries
here. Audit logs are append-only: no endpoint updates or deletes them.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from .auth import Authenticator, Caller
from .config import Settings
from .errors import Forbidden, NotConfigured, ProviderUnavailable, ValidationFailed
from .flags import FLAGS
from .metrics import METRICS

UUID_RE = re.compile(r"^[0-9a-fA-F-]{36}$")
ROLES = {"admin", "partner", "user"}
SETTING_KEYS = {
    "app_name": str, "nearby_default_radius_km": (int, float),
    "hold_expiry_minutes": int, "cancellation_window_hours": (int, float),
    "pricing_min_cents": int, "pricing_max_cents": int,
}


class AdminStore:
    """PostgREST access with the admin caller's JWT (RLS still applies)."""

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self._s = settings
        self._transport = transport

    def _client(self, jwt: str) -> httpx.AsyncClient:
        if not (self._s.supabase_url and self._s.supabase_publishable_key):
            raise NotConfigured("Backend inventory is not configured (SUPABASE_URL / SUPABASE_PUBLISHABLE_KEY missing).")
        return httpx.AsyncClient(
            base_url=self._s.supabase_url,
            headers={"apikey": self._s.supabase_publishable_key, "Authorization": f"Bearer {jwt}",
                     "Content-Type": "application/json"},
            timeout=self._s.provider_timeout_s, transport=self._transport)

    async def req(self, method: str, path: str, jwt: str, *, params: dict | None = None,
                  json: object | None = None, prefer: str | None = None):
        headers = {"Prefer": prefer} if prefer else {}
        try:
            async with self._client(jwt) as c:
                r = await c.request(method, path, params=params, json=json, headers=headers)
        except httpx.HTTPError:
            raise ProviderUnavailable("Database is unreachable.")
        data = None
        if r.content:
            try:
                data = r.json()
            except ValueError:
                data = None
        if r.status_code >= 400:
            msg = ""
            if isinstance(data, dict):
                msg = str(data.get("message") or data.get("details") or "")
            if "FORBIDDEN" in msg:
                raise Forbidden("Admin role required by the database policy.")
            if "REASON_REQUIRED" in msg:
                raise ValidationFailed("A reason of at least 3 characters is required.")
            if "BOOKING_NOT_FOUND" in msg:
                raise ValidationFailed("Booking not found.")
            if "INSUFFICIENT_FUNDS" in msg:
                raise ValidationFailed("Adjustment would make the balance negative.")
            if "NO_WALLET" in msg:
                raise ValidationFailed("Wallet not found.")
            raise ProviderUnavailable(f"Database operation failed (HTTP {r.status_code}).")
        return data

    async def get(self, table: str, jwt: str, **params) -> list[dict]:
        data = await self.req("GET", f"/rest/v1/{table}", jwt, params=params)
        return data if isinstance(data, list) else []

    async def audit(self, caller: Caller, action: str, target_type: str, target_id: str | None,
                    reason: str | None = None, metadata: dict | None = None) -> None:
        await self.req("POST", "/rest/v1/audit_logs", caller.jwt, json={
            "actor_id": caller.user_id, "action": action, "target_type": target_type,
            "target_id": target_id, "reason": reason, "metadata": metadata or {},
        })


# --------------------------------------------------------------------- models

class ReasonBody(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class RoleBody(BaseModel):
    role: str = Field(pattern="^(admin|partner|user)$")
    action: str = Field(pattern="^(grant|revoke)$")
    reason: str = Field(min_length=3, max_length=500)


class FacilityBody(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    name_ar: str = Field(min_length=2, max_length=120)
    city: str = Field(min_length=2, max_length=60)
    address: str = Field(min_length=3, max_length=200)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    price_per_hour_cents: int = Field(gt=0, le=1_000_000)
    total_capacity: int = Field(ge=0, le=100_000)
    authorized_capacity: int = Field(ge=0, le=100_000)
    available: int = Field(ge=0, le=100_000)
    features: list[str] = Field(default_factory=list, max_length=10)
    open_24h: bool = True
    active: bool = True


class FacilityPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    name_ar: str | None = Field(default=None, min_length=2, max_length=120)
    city: str | None = Field(default=None, min_length=2, max_length=60)
    address: str | None = Field(default=None, min_length=3, max_length=200)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    price_per_hour_cents: int | None = Field(default=None, gt=0, le=1_000_000)
    total_capacity: int | None = Field(default=None, ge=0, le=100_000)
    authorized_capacity: int | None = Field(default=None, ge=0, le=100_000)
    available: int | None = Field(default=None, ge=0, le=100_000)
    features: list[str] | None = Field(default=None, max_length=10)
    open_24h: bool | None = None
    active: bool | None = None
    reason: str = Field(min_length=3, max_length=500)


class PriceBody(BaseModel):
    price_per_hour_cents: int = Field(gt=0, le=1_000_000)
    reason: str = Field(min_length=3, max_length=500)


class AdjustBody(BaseModel):
    amount_cents: int = Field(ge=-100_000_000, le=100_000_000)
    reason: str = Field(min_length=3, max_length=500)


class CameraBody(BaseModel):
    label: str = Field(min_length=2, max_length=120)
    facility_id: str | None = None
    status: str = Field(default="active", pattern="^(active|inactive)$")


class CameraPatch(BaseModel):
    label: str | None = Field(default=None, min_length=2, max_length=120)
    facility_id: str | None = None
    status: str | None = Field(default=None, pattern="^(active|inactive)$")
    reason: str = Field(min_length=3, max_length=500)


class IncidentBody(BaseModel):
    kind: str = Field(pattern="^(user_report|booking_complaint|facility|camera|system|ai_error)$")
    title: str = Field(min_length=3, max_length=200)
    details: str | None = Field(default=None, max_length=2000)


class IncidentPatch(BaseModel):
    status: str = Field(pattern="^(open|investigating|resolved|dismissed)$")
    reason: str = Field(min_length=3, max_length=500)


class ToggleBody(BaseModel):
    feature: str = Field(pattern="^(assistant|voice|vision)$")
    enabled: bool
    reason: str = Field(min_length=3, max_length=500)


class SettingsBody(BaseModel):
    settings: dict
    reason: str = Field(min_length=3, max_length=500)


def _uuid(value: str) -> str:
    if not UUID_RE.match(value or ""):
        raise ValidationFailed("Invalid id.")
    return value


def build_admin_router(settings: Settings, authenticator: Authenticator,
                       transport: httpx.AsyncBaseTransport | None = None) -> APIRouter:
    store = AdminStore(settings, transport)
    router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

    async def admin(authorization: str | None) -> Caller:
        caller = await authenticator.require_user(authorization)
        if "admin" not in caller.roles:
            raise Forbidden("Admin role required.")
        return caller

    # ------------------------------------------------------------- overview
    @router.get("/overview")
    async def overview(authorization: str | None = Header(default=None)) -> dict:
        c = await admin(authorization)
        profiles = await store.get("profiles", c.jwt, select="id,status,created_at", limit="5000")
        facilities = await store.get("facilities", c.jwt,
                                     select="id,total_capacity,authorized_capacity,available,active", limit="1000")
        bookings = await store.get("bookings", c.jwt, select="id,status,total_cents,refunded_cents,created_at",
                                   order="created_at.desc", limit="2000")
        roles = await store.get("user_roles", c.jwt, select="user_id,role", limit="5000")
        cameras = await store.get("cameras", c.jwt, select="id,status", limit="1000")
        audit = await store.get("audit_logs", c.jwt, select="id,actor_id,action,target_type,created_at",
                                order="created_at.desc", limit="8")
        by_status: dict[str, int] = {}
        for b in bookings:
            by_status[b["status"]] = by_status.get(b["status"], 0) + 1
        revenue_cents = sum(int(b["total_cents"]) - int(b.get("refunded_cents") or 0)
                            for b in bookings if b["status"] in {"confirmed", "completed"})
        since = datetime.now(timezone.utc) - timedelta(days=30)
        per_day: dict[str, int] = {}
        regs: dict[str, int] = {}
        for b in bookings:
            d = str(b["created_at"])[:10]
            if datetime.fromisoformat(str(b["created_at"]).replace("Z", "+00:00")) >= since:
                per_day[d] = per_day.get(d, 0) + 1
        for p in profiles:
            d = str(p["created_at"])[:10]
            if datetime.fromisoformat(str(p["created_at"]).replace("Z", "+00:00")) >= since:
                regs[d] = regs.get(d, 0) + 1
        role_counts: dict[str, int] = {}
        for r in roles:
            role_counts[r["role"]] = role_counts.get(r["role"], 0) + 1
        return {
            "users_total": len(profiles),
            "users_suspended": sum(1 for p in profiles if p.get("status") == "suspended"),
            "users_by_role": role_counts,
            "facilities_total": len(facilities),
            "facilities_active": sum(1 for f in facilities if f.get("active", True)),
            "spaces_total_capacity": sum(int(f.get("total_capacity") or 0) for f in facilities),
            "spaces_authorized": sum(int(f.get("authorized_capacity") or 0) for f in facilities if f.get("active", True)),
            "spaces_available": sum(int(f.get("available") or 0) for f in facilities if f.get("active", True)),
            "bookings_by_status": by_status,
            "revenue_cents": revenue_cents,
            "revenue_is_demo": True,  # wallets are demo until a real payment provider exists
            "cameras_total": len(cameras),
            "cameras_active": sum(1 for cam in cameras if cam.get("status") == "active"),
            "bookings_per_day": [{"date": d, "count": per_day[d]} for d in sorted(per_day)],
            "registrations_per_day": [{"date": d, "count": regs[d]} for d in sorted(regs)],
            "recent_audit": audit,
        }

    # ---------------------------------------------------------------- users
    @router.get("/users")
    async def users(search: str = "", role: str = "", status: str = "",
                    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                    authorization: str | None = Header(default=None)) -> dict:
        c = await admin(authorization)
        profiles = await store.get("profiles", c.jwt,
                                   select="id,display_name,phone,vehicle_plate,vehicle_model,status,created_at",
                                   order="created_at.desc", limit="5000")
        roles = await store.get("user_roles", c.jwt, select="user_id,role", limit="5000")
        role_map: dict[str, list[str]] = {}
        for r in roles:
            role_map.setdefault(r["user_id"], []).append(r["role"])
        out = []
        q = search.strip().lower()
        for p in profiles:
            p["roles"] = role_map.get(p["id"], [])
            if q and q not in f"{p.get('display_name') or ''} {p.get('phone') or ''} {p.get('vehicle_plate') or ''} {p['id']}".lower():
                continue
            if role and role not in p["roles"]:
                continue
            if status and p.get("status") != status:
                continue
            out.append(p)
        return {"users": out[offset:offset + limit], "total": len(out)}

    @router.get("/users/{user_id}")
    async def user_detail(user_id: str, authorization: str | None = Header(default=None)) -> dict:
        c = await admin(authorization)
        uid = _uuid(user_id)
        rows = await store.get("profiles", c.jwt, select="*", id=f"eq.{uid}", limit="1")
        if not rows:
            raise ValidationFailed("User not found.")
        roles = await store.get("user_roles", c.jwt, select="role", user_id=f"eq.{uid}")
        bookings = await store.get("bookings", c.jwt, select="*", user_id=f"eq.{uid}",
                                   order="created_at.desc", limit="50")
        wallet = await store.get("wallets", c.jwt, select="*", user_id=f"eq.{uid}", limit="1")
        return {"profile": rows[0], "roles": [r["role"] for r in roles],
                "bookings": bookings, "wallet": wallet[0] if wallet else None}

    async def _guard_last_admin(c: Caller, target_id: str) -> None:
        target_roles = await store.get("user_roles", c.jwt, select="role", user_id=f"eq.{target_id}")
        if any(r["role"] == "admin" for r in target_roles):
            admins = await store.get("user_roles", c.jwt, select="user_id", role="eq.admin", limit="5000")
            if len(admins) <= 1:
                raise ValidationFailed("Cannot remove or suspend the last active administrator.")

    @router.post("/users/{user_id}/suspend")
    async def suspend(user_id: str, body: ReasonBody, authorization: str | None = Header(default=None)) -> dict:
        c = await admin(authorization)
        uid = _uuid(user_id)
        if uid == c.user_id:
            raise ValidationFailed("You cannot suspend your own account.")
        await _guard_last_admin(c, uid)
        await store.req("PATCH", "/rest/v1/profiles", c.jwt, params={"id": f"eq.{uid}"},
                        json={"status": "suspended"}, prefer="return=minimal")
        await store.audit(c, "user.suspend", "user", uid, body.reason)
        return {"user_id": uid, "status": "suspended"}

    @router.post("/users/{user_id}/reactivate")
    async def reactivate(user_id: str, body: ReasonBody, authorization: str | None = Header(default=None)) -> dict:
        c = await admin(authorization)
        uid = _uuid(user_id)
        await store.req("PATCH", "/rest/v1/profiles", c.jwt, params={"id": f"eq.{uid}"},
                        json={"status": "active"}, prefer="return=minimal")
        await store.audit(c, "user.reactivate", "user", uid, body.reason)
        return {"user_id": uid, "status": "active"}

    @router.post("/users/{user_id}/roles")
    async def change_role(user_id: str, body: RoleBody, authorization: str | None = Header(default=None)) -> dict:
        c = await admin(authorization)
        uid = _uuid(user_id)
        if body.role == "admin" and body.action == "revoke":
            await _guard_last_admin(c, uid)
        if body.action == "grant":
            await store.req("POST", "/rest/v1/user_roles", c.jwt,
                            json={"user_id": uid, "role": body.role}, prefer="return=minimal")
        else:
            await store.req("DELETE", "/rest/v1/user_roles", c.jwt,
                            params={"user_id": f"eq.{uid}", "role": f"eq.{body.role}"}, prefer="return=minimal")
        await store.audit(c, f"role.{body.action}", "user", uid, body.reason, {"role": body.role})
        roles = await store.get("user_roles", c.jwt, select="role", user_id=f"eq.{uid}")
        return {"user_id": uid, "roles": [r["role"] for r in roles]}

    # ------------------------------------------------------------ facilities
    @router.get("/facilities")
    async def facilities(authorization: str | None = Header(default=None)) -> dict:
        c = await admin(authorization)
        rows = await store.get("facilities", c.jwt, select="*", order="name.asc", limit="1000")
        return {"facilities": rows}

    def _validate_capacities(total: int, authorized: int, available: int) -> None:
        if authorized > total:
            raise ValidationFailed("Authorized capacity cannot exceed total physical capacity.")
        if available > authorized:
            raise ValidationFailed("Available spaces cannot exceed authorized capacity.")

    @router.post("/facilities")
    async def create_facility(body: FacilityBody, authorization: str | None = Header(default=None)) -> dict:
        c = await admin(authorization)
        _validate_capacities(body.total_capacity, body.authorized_capacity, body.available)
        payload = body.model_dump()
        payload["capacity"] = body.authorized_capacity  # legacy column stays in sync with authorized
        payload["image_key"] = "garage"
        rows = await store.req("POST", "/rest/v1/facilities", c.jwt, json=payload, prefer="return=representation")
        row = rows[0] if isinstance(rows, list) and rows else {}
        await store.audit(c, "facility.create", "facility", row.get("id"), None, {"name": body.name})
        return {"facility": row}

    @router.patch("/facilities/{facility_id}")
    async def update_facility(facility_id: str, body: FacilityPatch,
                              authorization: str | None = Header(default=None)) -> dict:
        c = await admin(authorization)
        fid = _uuid(facility_id)
        rows = await store.get("facilities", c.jwt, select="*", id=f"eq.{fid}", limit="1")
        if not rows:
            raise ValidationFailed("Facility not found.")
        cur = rows[0]
        patch = {k: v for k, v in body.model_dump().items() if v is not None and k != "reason"}
        merged = {**cur, **patch}
        # Active-reservation protection runs FIRST: shrinking authorized
        # capacity below live confirmed bookings is the most specific (and
        # safety-critical) failure, and it must be reported even when the
        # merged row would also trip a generic capacity rule (e.g. the
        # unchanged `available` now exceeding the reduced authorized cap).
        if int(merged["authorized_capacity"]) < int(cur.get("authorized_capacity") or 0):
            active_bookings = await store.get("bookings", c.jwt, select="id", facility_id=f"eq.{fid}",
                                              status="eq.confirmed", limit="5000")
            if len(active_bookings) > int(merged["authorized_capacity"]):
                raise ValidationFailed("Authorized capacity cannot be below active reservations.")
        _validate_capacities(int(merged["total_capacity"]), int(merged["authorized_capacity"]), int(merged["available"]))
        patch["capacity"] = int(merged["authorized_capacity"])
        await store.req("PATCH", "/rest/v1/facilities", c.jwt, params={"id": f"eq.{fid}"},
                        json=patch, prefer="return=minimal")
        await store.audit(c, "facility.update", "facility", fid, body.reason, {"fields": sorted(patch.keys())})
        return {"facility_id": fid, "updated": sorted(patch.keys())}

    # -------------------------------------------------------------- bookings
    @router.get("/bookings")
    async def bookings(status: str = "", search: str = "",
                       limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                       authorization: str | None = Header(default=None)) -> dict:
        c = await admin(authorization)
        params: dict = {"select": "*", "order": "created_at.desc", "limit": "2000"}
        if status:
            params["status"] = f"eq.{status}"
        rows = await store.get("bookings", c.jwt, **params)
        facilities = {f["id"]: f.get("name") for f in await store.get("facilities", c.jwt, select="id,name", limit="1000")}
        q = search.strip().lower()
        out = []
        for b in rows:
            b["facility_name"] = facilities.get(b["facility_id"])
            if q and q not in f"{b['id']} {b['user_id']} {b.get('facility_name') or ''}".lower():
                continue
            out.append(b)
        return {"bookings": out[offset:offset + limit], "total": len(out)}

    @router.post("/bookings/{booking_id}/cancel")
    async def cancel_booking(booking_id: str, body: ReasonBody,
                             authorization: str | None = Header(default=None)) -> dict:
        c = await admin(authorization)
        bid = _uuid(booking_id)
        # Money/refund logic lives in the SECURITY DEFINER function (AGENTS.md).
        row = await store.req("POST", "/rest/v1/rpc/admin_cancel_booking", c.jwt,
                              json={"p_booking_id": bid, "p_reason": body.reason})
        return {"booking": row}

    # --------------------------------------------------------------- pricing
    @router.get("/pricing")
    async def pricing(authorization: str | None = Header(default=None)) -> dict:
        c = await admin(authorization)
        rows = await store.get("facilities", c.jwt,
                               select="id,name,city,price_per_hour_cents,available,authorized_capacity,active",
                               order="name.asc", limit="1000")
        settings_rows = await store.get("app_settings", c.jwt, select="key,value", limit="100")
        cfg = {r["key"]: r["value"] for r in settings_rows}
        history = await store.get("audit_logs", c.jwt, select="*", action="eq.pricing.update",
                                  order="created_at.desc", limit="20")
        return {
            "facilities": rows,
            "pricing_min_cents": cfg.get("pricing_min_cents", 100),
            "pricing_max_cents": cfg.get("pricing_max_cents", 100_000),
            "engine": "fixed",  # no dynamic pricing engine exists in this codebase — stated honestly
            "history": history,
        }

    @router.patch("/facilities/{facility_id}/price")
    async def update_price(facility_id: str, body: PriceBody,
                           authorization: str | None = Header(default=None)) -> dict:
        c = await admin(authorization)
        fid = _uuid(facility_id)
        cfg_rows = await store.get("app_settings", c.jwt, select="key,value", limit="100")
        cfg = {r["key"]: r["value"] for r in cfg_rows}
        lo, hi = int(cfg.get("pricing_min_cents", 100)), int(cfg.get("pricing_max_cents", 100_000))
        if not (lo <= body.price_per_hour_cents <= hi):
            raise ValidationFailed(f"Price must stay within configured bounds ({lo}–{hi} cents).")
        await store.req("PATCH", "/rest/v1/facilities", c.jwt, params={"id": f"eq.{fid}"},
                        json={"price_per_hour_cents": body.price_per_hour_cents}, prefer="return=minimal")
        await store.audit(c, "pricing.update", "facility", fid, body.reason,
                          {"price_per_hour_cents": body.price_per_hour_cents})
        return {"facility_id": fid, "price_per_hour_cents": body.price_per_hour_cents}

    # ------------------------------------------------------------------- AI
    @router.get("/ai/status")
    async def ai_status(authorization: str | None = Header(default=None)) -> dict:
        c = await admin(authorization)
        s = settings
        return {
            "flags": FLAGS.snapshot(),
            "metrics": METRICS.snapshot(),
            "services": {
                "muse_spark": {"configured": s.muse_configured, "model": s.muse_spark_model,
                               "base_url_host": _host(s.meta_base_url), "enabled": FLAGS.get("assistant")},
                "muse_voice": {"configured": s.voice_configured, "model": s.muse_voice_model,
                               "enabled": FLAGS.get("voice") and s.muse_voice_enabled},
                "sam": {"configured": s.sam_configured, "model": s.sam_model,
                        "service_host": _host(s.sam_service_url), "enabled": FLAGS.get("vision")},
                "easyocr": {"configured": _easyocr_installed(), "min_confidence": s.ocr_min_confidence,
                            "enabled": FLAGS.get("vision")},
            },
        }

    @router.post("/ai/health/{service}")
    async def ai_health(service: str, authorization: str | None = Header(default=None)) -> dict:
        c = await admin(authorization)
        return await _probe(settings, service)

    @router.post("/ai/toggle")
    async def ai_toggle(body: ToggleBody, authorization: str | None = Header(default=None)) -> dict:
        c = await admin(authorization)
        FLAGS.set(body.feature, body.enabled)
        await store.audit(c, "ai.toggle", "ai", body.feature, body.reason, {"enabled": body.enabled})
        return {"feature": body.feature, "enabled": body.enabled}

    # --------------------------------------------------------------- cameras
    @router.get("/cameras")
    async def cameras(authorization: str | None = Header(default=None)) -> dict:
        c = await admin(authorization)
        rows = await store.get("cameras", c.jwt, select="*", order="created_at.desc", limit="1000")
        events = await store.get("camera_events", c.jwt, select="*", order="created_at.desc", limit="50")
        return {"cameras": rows, "events": events}

    @router.post("/cameras")
    async def create_camera(body: CameraBody, authorization: str | None = Header(default=None)) -> dict:
        c = await admin(authorization)
        payload = body.model_dump()
        if payload.get("facility_id"):
            _uuid(payload["facility_id"])
        rows = await store.req("POST", "/rest/v1/cameras", c.jwt, json=payload, prefer="return=representation")
        row = rows[0] if isinstance(rows, list) and rows else {}
        await store.audit(c, "camera.create", "camera", row.get("id"), None, {"label": body.label})
        return {"camera": row}

    @router.patch("/cameras/{camera_id}")
    async def update_camera(camera_id: str, body: CameraPatch,
                            authorization: str | None = Header(default=None)) -> dict:
        c = await admin(authorization)
        cid = _uuid(camera_id)
        patch = {k: v for k, v in body.model_dump().items() if v is not None and k != "reason"}
        await store.req("PATCH", "/rest/v1/cameras", c.jwt, params={"id": f"eq.{cid}"},
                        json=patch, prefer="return=minimal")
        await store.audit(c, "camera.update", "camera", cid, body.reason, {"fields": sorted(patch.keys())})
        return {"camera_id": cid, "updated": sorted(patch.keys())}

    # -------------------------------------------------------------- payments
    @router.get("/wallets")
    async def wallets(authorization: str | None = Header(default=None)) -> dict:
        c = await admin(authorization)
        rows = await store.get("wallets", c.jwt, select="*", order="updated_at.desc", limit="1000")
        profiles = {p["id"]: p.get("display_name") for p in
                    await store.get("profiles", c.jwt, select="id,display_name", limit="5000")}
        for w in rows:
            w["display_name"] = profiles.get(w["user_id"])
        return {"wallets": rows, "is_demo": True}

    @router.get("/wallets/{user_id}/transactions")
    async def wallet_tx(user_id: str, authorization: str | None = Header(default=None)) -> dict:
        c = await admin(authorization)
        uid = _uuid(user_id)
        rows = await store.get("wallet_transactions", c.jwt, select="*", user_id=f"eq.{uid}",
                               order="created_at.desc", limit="200")
        return {"transactions": rows}

    @router.post("/wallets/{user_id}/adjust")
    async def adjust_wallet(user_id: str, body: AdjustBody,
                            authorization: str | None = Header(default=None)) -> dict:
        c = await admin(authorization)
        uid = _uuid(user_id)
        if body.amount_cents == 0:
            raise ValidationFailed("Adjustment amount cannot be zero.")
        row = await store.req("POST", "/rest/v1/rpc/admin_adjust_wallet", c.jwt,
                              json={"p_user_id": uid, "p_amount_cents": body.amount_cents, "p_reason": body.reason})
        return {"transaction": row}

    # --------------------------------------------------------------- reports
    @router.get("/reports")
    async def reports(days: int = Query(30, ge=1, le=365), authorization: str | None = Header(default=None)) -> dict:
        c = await admin(authorization)
        bookings = await store.get("bookings", c.jwt,
                                   select="id,facility_id,status,total_cents,refunded_cents,created_at",
                                   order="created_at.desc", limit="5000")
        since = datetime.now(timezone.utc) - timedelta(days=days)
        recent = [b for b in bookings
                  if datetime.fromisoformat(str(b["created_at"]).replace("Z", "+00:00")) >= since]
        per_day: dict[str, int] = {}
        per_facility: dict[str, dict] = {}
        cancelled = 0
        for b in recent:
            per_day[str(b["created_at"])[:10]] = per_day.get(str(b["created_at"])[:10], 0) + 1
            f = per_facility.setdefault(b["facility_id"], {"facility_id": b["facility_id"], "bookings": 0, "revenue_cents": 0})
            f["bookings"] += 1
            if b["status"] == "cancelled":
                cancelled += 1
            else:
                f["revenue_cents"] += int(b["total_cents"]) - int(b.get("refunded_cents") or 0)
        names = {f["id"]: f.get("name") for f in await store.get("facilities", c.jwt, select="id,name", limit="1000")}
        for f in per_facility.values():
            f["name"] = names.get(f["facility_id"])
        return {
            "days": days,
            "total": len(recent),
            "cancelled": cancelled,
            "cancellation_rate": round(cancelled / len(recent), 4) if recent else 0,
            "bookings_per_day": [{"date": d, "count": per_day[d]} for d in sorted(per_day)],
            "facility_performance": sorted(per_facility.values(), key=lambda x: -x["bookings"]),
            "revenue_is_demo": True,
        }

    @router.get("/reports/bookings.csv")
    async def bookings_csv(authorization: str | None = Header(default=None)) -> PlainTextResponse:
        c = await admin(authorization)
        rows = await store.get("bookings", c.jwt, select="*", order="created_at.desc", limit="5000")
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["id", "user_id", "facility_id", "start_at", "end_at", "hours", "total_cents", "status", "created_at"])
        for b in rows:
            w.writerow([b["id"], b["user_id"], b["facility_id"], b["start_at"], b["end_at"],
                        b["hours"], b["total_cents"], b["status"], b["created_at"]])
        await store.audit(c, "report.export", "booking", None, "CSV export", {"rows": len(rows)})
        return PlainTextResponse(buf.getvalue(), media_type="text/csv",
                                 headers={"Content-Disposition": "attachment; filename=bookings.csv"})

    # ------------------------------------------------------------- incidents
    @router.get("/incidents")
    async def incidents(status: str = "", authorization: str | None = Header(default=None)) -> dict:
        c = await admin(authorization)
        params: dict = {"select": "*", "order": "created_at.desc", "limit": "200"}
        if status:
            params["status"] = f"eq.{status}"
        return {"incidents": await store.get("incidents", c.jwt, **params)}

    @router.post("/incidents")
    async def create_incident(body: IncidentBody, authorization: str | None = Header(default=None)) -> dict:
        c = await admin(authorization)
        payload = {**body.model_dump(), "reporter_id": c.user_id}
        rows = await store.req("POST", "/rest/v1/incidents", c.jwt, json=payload, prefer="return=representation")
        return {"incident": rows[0] if isinstance(rows, list) and rows else {}}

    @router.patch("/incidents/{incident_id}")
    async def update_incident(incident_id: str, body: IncidentPatch,
                              authorization: str | None = Header(default=None)) -> dict:
        c = await admin(authorization)
        iid = _uuid(incident_id)
        await store.req("PATCH", "/rest/v1/incidents", c.jwt, params={"id": f"eq.{iid}"},
                        json={"status": body.status, "updated_at": datetime.now(timezone.utc).isoformat()},
                        prefer="return=minimal")
        await store.audit(c, "incident.update", "incident", iid, body.reason, {"status": body.status})
        return {"incident_id": iid, "status": body.status}

    # ----------------------------------------------------------------- audit
    @router.get("/audit")
    async def audit_log(action: str = "", limit: int = Query(50, ge=1, le=200),
                        offset: int = Query(0, ge=0), authorization: str | None = Header(default=None)) -> dict:
        c = await admin(authorization)
        params: dict = {"select": "*", "order": "created_at.desc", "limit": "2000"}
        if action:
            params["action"] = f"eq.{action}"
        rows = await store.get("audit_logs", c.jwt, **params)
        return {"entries": rows[offset:offset + limit], "total": len(rows)}

    # -------------------------------------------------------------- settings
    @router.get("/settings")
    async def get_settings(authorization: str | None = Header(default=None)) -> dict:
        c = await admin(authorization)
        rows = await store.get("app_settings", c.jwt, select="key,value,updated_at", limit="100")
        return {"settings": {r["key"]: r["value"] for r in rows}, "flags": FLAGS.snapshot()}

    @router.patch("/settings")
    async def update_settings(body: SettingsBody, authorization: str | None = Header(default=None)) -> dict:
        c = await admin(authorization)
        unknown = set(body.settings) - set(SETTING_KEYS)
        if unknown:
            raise ValidationFailed(f"Unknown settings: {', '.join(sorted(unknown))}. Arbitrary settings are not allowed.")
        for key, value in body.settings.items():
            expected = SETTING_KEYS[key]
            if not isinstance(value, expected) or isinstance(value, bool) and expected is not bool:
                raise ValidationFailed(f"Setting {key} has the wrong type.")
            await store.req("POST", "/rest/v1/app_settings", c.jwt,
                            params={"on_conflict": "key"},
                            json={"key": key, "value": value, "updated_by": c.user_id},
                            prefer="resolution=merge-duplicates,return=minimal")
        await store.audit(c, "settings.update", "settings", None, body.reason, {"keys": sorted(body.settings)})
        return {"updated": sorted(body.settings)}

    return router


def _host(url: str | None) -> str | None:
    if not url:
        return None
    try:
        return url.split("//", 1)[-1].split("/", 1)[0]
    except Exception:
        return None


def _easyocr_installed() -> bool:
    import importlib.util
    return importlib.util.find_spec("easyocr") is not None


async def _probe(settings: Settings, service: str) -> dict:
    """Safe predefined health checks: HTTP reachability only, no inference,
    no tool execution, credentials never returned."""
    targets = {
        "muse_spark": (settings.meta_base_url + "/models" if settings.muse_configured else None,
                       settings.meta_model_api_key),
        "muse_voice": (settings.meta_voice_base_url + "/models" if settings.voice_configured else None,
                       settings.meta_voice_api_key),
        "sam": (settings.sam_service_url, settings.sam_service_api_key),
        "easyocr": (None, None),
    }
    if service not in targets:
        raise ValidationFailed(f"Unknown service: {service}")
    if service == "easyocr":
        return {"service": service, "configured": _easyocr_installed(), "reachable": None,
                "tested_ok": _easyocr_installed(),
                "detail": "EasyOCR package importable in this backend environment."
                if _easyocr_installed() else "EasyOCR is not installed (requirements-vision.txt)."}
    url, key = targets[service]
    if not url:
        return {"service": service, "configured": False, "reachable": False, "tested_ok": False,
                "detail": "Not configured (credentials/URL missing)."}
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            r = await client.get(url, headers=headers)
        return {"service": service, "configured": True, "reachable": True,
                "tested_ok": r.status_code == 200,
                "detail": f"Endpoint responded with HTTP {r.status_code} (no inference performed)."}
    except httpx.HTTPError:
        return {"service": service, "configured": True, "reachable": False, "tested_ok": False,
                "detail": "Endpoint unreachable (network/timeout)."}
