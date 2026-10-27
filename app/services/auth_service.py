from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AuthError, ConflictError, ValidationAppError
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.db.models.enums import UserRole
from app.db.models.user import User
from app.repositories import user_repo
from app.schemas.auth import RegisterIn, TokenPair


def _token_pair(user: User) -> TokenPair:
    s = get_settings()
    return TokenPair(
        access_token=create_access_token(user.id, user.role.value),
        refresh_token=create_refresh_token(user.id, user.role.value),
        expires_in=s.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def register(db: AsyncSession, data: RegisterIn) -> User:
    # Public self-registration is for drivers only. Partner-operator and
    # admin accounts are provisioned by ParkSpot operations (seed/admin
    # tooling), never through the public consumer sign-up.
    if data.role != UserRole.driver:
        raise ValidationAppError(
            "public registration is for drivers; partner and admin accounts are provisioned by ParkSpot operations",
            code="role_not_allowed",
        )
    if "@" not in data.email:
        raise ValidationAppError("invalid email")
    if await user_repo.get_by_email(db, data.email):
        raise ConflictError("email already taken", code="email_taken")
    hashed = await asyncio.to_thread(hash_password, data.password)
    user = User(email=data.email.lower(), hashed_password=hashed, full_name=data.full_name, phone=data.phone, role=data.role)
    await user_repo.create(db, user)
    await db.commit()
    await db.refresh(user)
    return user


async def login(db: AsyncSession, email: str, password: str) -> TokenPair:
    user = await user_repo.get_by_email(db, email)
    if user is None or not user.is_active:
        raise AuthError("invalid credentials")
    ok = await asyncio.to_thread(verify_password, password, user.hashed_password)
    if not ok:
        raise AuthError("invalid credentials")
    return _token_pair(user)


async def refresh(db: AsyncSession, refresh_token: str) -> TokenPair:
    payload = decode_token(refresh_token, "refresh")
    user = await user_repo.get_by_id(db, int(payload["sub"]))
    if user is None or not user.is_active:
        raise AuthError("invalid or expired token")
    return _token_pair(user)
