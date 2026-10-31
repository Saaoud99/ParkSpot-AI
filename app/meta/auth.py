"""Authenticated caller identity — always from the Supabase JWT, never
from anything the model or request body claims."""
from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from .config import Settings
from .errors import NotConfigured, Unauthorized


@dataclass
class Caller:
    user_id: str
    jwt: str
    roles: list[str] = field(default_factory=list)

    @property
    def is_ops(self) -> bool:
        return "admin" in self.roles or "partner" in self.roles


class Authenticator:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self._s = settings
        self._transport = transport

    async def require_user(self, authorization: str | None) -> Caller:
        if not authorization or not authorization.startswith("Bearer "):
            raise Unauthorized("Sign in required.")
        jwt = authorization[7:].strip()
        if not jwt or jwt.count(".") != 2:
            raise Unauthorized("Invalid session token.")
        if not (self._s.supabase_url and self._s.supabase_publishable_key):
            raise NotConfigured("Auth is not configured (SUPABASE_URL / SUPABASE_PUBLISHABLE_KEY missing).")
        headers = {"apikey": self._s.supabase_publishable_key, "Authorization": f"Bearer {jwt}"}
        try:
            async with httpx.AsyncClient(base_url=self._s.supabase_url, headers=headers,
                                         timeout=self._s.provider_timeout_s, transport=self._transport) as c:
                me = await c.get("/auth/v1/user")
                if me.status_code != 200:
                    raise Unauthorized("Session expired or invalid.")
                user_id = me.json().get("id")
                if not user_id:
                    raise Unauthorized("Session expired or invalid.")
                roles_resp = await c.get("/rest/v1/user_roles", params={"select": "role", "user_id": f"eq.{user_id}"})
                profile_resp = await c.get("/rest/v1/profiles", params={"select": "status", "id": f"eq.{user_id}", "limit": "1"})
        except Unauthorized:
            raise
        except httpx.HTTPError:
            raise Unauthorized("Could not verify session.")
        if profile_resp.status_code == 200 and isinstance(profile_resp.json(), list) and profile_resp.json():
            if profile_resp.json()[0].get("status") == "suspended":
                from .errors import Forbidden
                raise Forbidden("This account is suspended. Contact ParkSpot support.")
        roles = [r["role"] for r in roles_resp.json()] if roles_resp.status_code == 200 and isinstance(roles_resp.json(), list) else []
        return Caller(user_id=str(user_id), jwt=jwt, roles=roles)

    async def require_ops(self, authorization: str | None) -> Caller:
        caller = await self.require_user(authorization)
        if not caller.is_ops:
            from .errors import Forbidden
            raise Forbidden("Partner or admin role required.")
        return caller
