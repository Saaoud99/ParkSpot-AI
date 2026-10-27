from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.db.models.enums import UserRole
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.vision import VerifyQrIn
from app.services import access_service

router = APIRouter(prefix="/access", tags=["access"])


@router.post("/verify-qr")
async def verify_qr(data: VerifyQrIn, user: User = Depends(require_role(UserRole.host, UserRole.admin)), db: AsyncSession = Depends(get_db)):
    return await access_service.verify_qr(db, user, data.token)
