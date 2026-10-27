from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.exceptions import AuthError

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _create_token(claims: dict[str, Any], expires: timedelta, token_type: str) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload = {**claims, "type": token_type, "iat": now, "exp": now + expires}
    return jwt.encode(payload, s.SECRET_KEY, algorithm="HS256")


def create_access_token(user_id: int, role: str) -> str:
    s = get_settings()
    return _create_token({"sub": str(user_id), "role": role}, timedelta(minutes=s.ACCESS_TOKEN_EXPIRE_MINUTES), "access")


def create_refresh_token(user_id: int, role: str) -> str:
    s = get_settings()
    return _create_token({"sub": str(user_id), "role": role}, timedelta(days=s.REFRESH_TOKEN_EXPIRE_DAYS), "refresh")


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    s = get_settings()
    try:
        payload = jwt.decode(token, s.SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise AuthError("invalid or expired token") from exc
    if payload.get("type") != expected_type:
        raise AuthError("invalid or expired token")
    return payload


def create_access_pass_token(booking_id: int, plate: str, spot_id: int, start: datetime, end: datetime) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload = {
        "type": "access_pass", "bid": booking_id, "plate": plate, "spot": spot_id,
        "iat": now, "nbf": start - timedelta(minutes=s.ARRIVAL_GRACE_MINUTES),
        "exp": end + timedelta(minutes=s.ARRIVAL_GRACE_MINUTES),
    }
    return jwt.encode(payload, s.SECRET_KEY, algorithm="HS256")


def decode_access_pass(token: str) -> dict[str, Any]:
    s = get_settings()
    try:
        payload = jwt.decode(token, s.SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise AuthError("invalid or expired token") from exc
    if payload.get("type") != "access_pass":
        raise AuthError("invalid or expired token")
    return payload
