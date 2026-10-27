from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends, Header, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AuthError, ForbiddenError
from app.core.security import decode_token
from app.db.models.enums import UserRole
from app.db.models.user import User
from app.db.session import get_db
from app.repositories import user_repo

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


async def get_current_user(token: str | None = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    if not token:
        raise AuthError("not authenticated")
    payload = decode_token(token, "access")
    user = await user_repo.get_by_id(db, int(payload["sub"]))
    if user is None or not user.is_active:
        raise AuthError("invalid or expired token")
    return user


async def get_optional_user(token: str | None = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User | None:
    if not token:
        return None
    try:
        payload = decode_token(token, "access")
        user = await user_repo.get_by_id(db, int(payload["sub"]))
        return user if user and user.is_active else None
    except Exception:
        return None


def require_role(*roles: UserRole) -> Callable[..., Coroutine[Any, Any, User]]:
    async def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role == UserRole.admin:
            return user
        if user.role not in roles:
            raise ForbiddenError("forbidden")
        return user

    return _dep


async def camera_auth(
    request: Request,
    x_camera_key: str | None = Header(default=None),
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    settings = get_settings()
    if x_camera_key and settings.CAMERA_SHARED_KEY and x_camera_key == settings.CAMERA_SHARED_KEY:
        return None
    if not token:
        raise AuthError("camera authentication required")
    payload = decode_token(token, "access")
    user = await user_repo.get_by_id(db, int(payload["sub"]))
    if user is None or not user.is_active:
        raise AuthError("invalid or expired token")
    if user.role not in (UserRole.host, UserRole.admin):
        raise ForbiddenError("forbidden")
    return user
