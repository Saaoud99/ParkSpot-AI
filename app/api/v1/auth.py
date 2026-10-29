from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.ratelimit import check_rate_limit
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import LoginIn, RefreshIn, RegisterIn, TokenPair, UserOut
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
async def register(data: RegisterIn, request: Request, db: AsyncSession = Depends(get_db)) -> User:
    check_rate_limit(request, "register", limit=300, window_seconds=3600)
    return await auth_service.register(db, data)


@router.post("/login", response_model=TokenPair)
async def login(data: LoginIn, request: Request, db: AsyncSession = Depends(get_db)) -> TokenPair:
    # Keyed per account + IP so credential stuffing against one account is
    # throttled without locking out a shared-NAT office of other users.
    check_rate_limit(request, "login", limit=15, window_seconds=300, identity=data.email)
    return await auth_service.login(db, data.email, data.password)


@router.post("/token", response_model=TokenPair)
async def token(request: Request, username: str = Form(...), password: str = Form(...), db: AsyncSession = Depends(get_db)) -> TokenPair:
    check_rate_limit(request, "login", limit=15, window_seconds=300, identity=username)
    return await auth_service.login(db, username, password)


@router.post("/refresh", response_model=TokenPair)
async def refresh(data: RefreshIn, db: AsyncSession = Depends(get_db)) -> TokenPair:
    return await auth_service.refresh(db, data.refresh_token)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> User:
    return user
