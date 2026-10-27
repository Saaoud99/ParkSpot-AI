from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.models.enums import ChatRole
from app.db.models.user import User
from app.db.session import get_db
from app.repositories import chat_repo
from app.schemas.chat import ChatIn, ChatMessageOut, ChatResponse, ChatSessionOut
from app.services import chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(data: ChatIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await chat_service.handle_message(db, user, data)


@router.get("/sessions", response_model=list[ChatSessionOut])
async def sessions(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await chat_repo.list_sessions(db, user.id)


@router.get("/sessions/{session_id}", response_model=list[ChatMessageOut])
async def session_messages(session_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    session = await chat_repo.get_session(db, session_id)
    if session is None:
        raise NotFoundError("chat session not found")
    if session.user_id != user.id:
        raise ForbiddenError("forbidden")
    msgs = await chat_repo.list_messages(db, session_id)
    return [{"id": m.id, "session_id": m.session_id, "role": m.role.value, "content": m.content, "created_at": m.created_at} for m in msgs if m.role in (ChatRole.user, ChatRole.assistant)]
