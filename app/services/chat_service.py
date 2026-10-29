from __future__ import annotations

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.booking_agent import run_booking_agent
from app.ai.tools.context import ToolContext
from app.core.config import get_settings
from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.models.chat import ChatSession
from app.db.models.enums import ChatRole
from app.db.models.user import User
from app.repositories import chat_repo
from app.schemas.chat import ChatIn
from app.services import booking_service
from app.utils.timeutil import utcnow

logger = logging.getLogger(__name__)


async def handle_message(db: AsyncSession, user: User, data: ChatIn) -> dict:
    session: ChatSession | None = None
    if data.session_id is not None:
        session = await chat_repo.get_session(db, data.session_id)
        if session is None:
            raise NotFoundError("chat session not found")
        if session.user_id != user.id:
            raise ForbiddenError("forbidden")
    else:
        session = await chat_repo.create_session(db, user.id, title=data.message[:80])
        await db.commit()
        await db.refresh(session)
    await chat_repo.add_message(db, session.id, ChatRole.user, data.message)
    await db.commit()

    settings = get_settings()
    ctx = ToolContext(db=db, user=user, settings=settings, now=utcnow(), timezone=data.timezone or "UTC",
                      location=(data.location.lat, data.location.lng) if data.location else None)
    degraded = False
    if not settings.LLAMA_API_KEY:
        # No provider configured: say so immediately and honestly instead
        # of firing a doomed request and dressing the fallback up as AI.
        degraded = True
        reply = (
            "The AI assistant isn't configured on this deployment (no Llama provider key), "
            "so I can't search by chat right now. Use the destination search and filters on the "
            "home page — they query the same live ParkSpot inventory."
        )
        await chat_repo.add_message(db, session.id, ChatRole.assistant, reply)
        await db.commit()
        return {"session_id": session.id, "reply": reply, "actions": [], "spots": None, "booking": None, "degraded": True}
    try:
        result = await run_booking_agent(data.message, ctx, session)
        reply, actions, spots, booking = result.reply, result.actions, result.spots, result.booking
        for m in result.messages_to_persist:
            role = m.get("role")
            if role == "assistant":
                tcs = json.dumps(m["tool_calls"]) if m.get("tool_calls") else None
                await chat_repo.add_message(db, session.id, ChatRole.assistant, m.get("content", ""), tool_calls_json=tcs)
            elif role == "tool":
                await chat_repo.add_message(db, session.id, ChatRole.tool, m.get("content", ""), tool_name=m.get("name"), tool_call_id=m.get("tool_call_id"))
        # Final reply persisted if not already the last assistant message.
        msgs = await chat_repo.list_messages(db, session.id)
        if not msgs or msgs[-1].content != reply:
            await chat_repo.add_message(db, session.id, ChatRole.assistant, reply)
        await db.commit()
    except Exception:
        logger.exception("booking agent failed")
        degraded = True
        reply = "The booking assistant is temporarily unavailable. You can still book from the map."
        actions, spots, booking = [], None, None
        await chat_repo.add_message(db, session.id, ChatRole.assistant, reply)
        await db.commit()

    booking_out = None
    if booking is not None:
        booking_out = booking_service.serialize(booking, user)
    return {
        "session_id": session.id, "reply": reply,
        "actions": [{"tool": a.tool, "arguments": a.arguments, "ok": a.ok, "summary": a.summary} for a in actions],
        "spots": spots, "booking": booking_out, "degraded": degraded,
    }
