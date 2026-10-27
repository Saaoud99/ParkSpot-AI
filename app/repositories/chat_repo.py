from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.chat import ChatMessage, ChatSession
from app.db.models.enums import ChatRole


async def create_session(db: AsyncSession, user_id: int, title: str | None = None) -> ChatSession:
    s = ChatSession(user_id=user_id, title=title)
    db.add(s)
    await db.flush()
    return s


async def get_session(db: AsyncSession, session_id: int) -> ChatSession | None:
    return await db.get(ChatSession, session_id)


async def list_sessions(db: AsyncSession, user_id: int) -> list[ChatSession]:
    return list((await db.execute(select(ChatSession).where(ChatSession.user_id == user_id).order_by(ChatSession.created_at.desc()))).scalars().all())


async def add_message(db: AsyncSession, session_id: int, role: ChatRole, content: str, tool_name: str | None = None, tool_call_id: str | None = None, tool_calls_json: str | None = None) -> ChatMessage:
    m = ChatMessage(session_id=session_id, role=role, content=content, tool_name=tool_name, tool_call_id=tool_call_id, tool_calls_json=tool_calls_json)
    db.add(m)
    await db.flush()
    return m


async def list_messages(db: AsyncSession, session_id: int) -> list[ChatMessage]:
    return list((await db.execute(select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.id))).scalars().all())


async def last_messages(db: AsyncSession, session_id: int, limit: int = 20) -> list[dict]:
    rows = list((await db.execute(select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.id.desc()).limit(limit))).scalars().all())
    rows.reverse()
    out: list[dict] = []
    for m in rows:
        if m.role == ChatRole.tool:
            out.append({"role": "tool", "tool_call_id": m.tool_call_id or "", "name": m.tool_name or "", "content": m.content})
        elif m.role == ChatRole.assistant and m.tool_calls_json:
            try:
                tcs = json.loads(m.tool_calls_json)
            except Exception:
                tcs = None
            msg: dict = {"role": "assistant", "content": m.content or ""}
            if tcs:
                msg["tool_calls"] = tcs
            out.append(msg)
        elif m.role in (ChatRole.user, ChatRole.assistant, ChatRole.system):
            out.append({"role": m.role.value, "content": m.content})
    return out
