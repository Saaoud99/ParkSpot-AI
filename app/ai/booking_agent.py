from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.ai.llama_client import get_llama_client
from app.ai.prompts import build_system_prompt
from app.ai.tools import TOOL_SPECS, execute_tool
from app.ai.tools.context import ToolContext
from app.repositories import chat_repo
from app.services import booking_service


@dataclass(slots=True)
class ToolAction:
    tool: str
    arguments: dict
    ok: bool
    summary: str


@dataclass(slots=True)
class AgentResult:
    reply: str
    actions: list = field(default_factory=list)
    spots: list | None = None
    booking: object | None = None
    messages_to_persist: list = field(default_factory=list)


def summarize(result: dict) -> str:
    if not result.get("ok", False):
        return f"{result.get('error', 'error')}: {result.get('detail', '')}"[:120]
    if "count" in result:
        return f"found {result['count']} spots"[:120]
    if "booking_id" in result:
        return f"booking {result['booking_id']} {result.get('status', '')} total {result.get('total', '')}"[:120]
    if "start" in result:
        return f"{result['start']} to {result.get('end', '')}"[:120]
    if "total" in result:
        return f"total {result['total']}"[:120]
    return "ok"[:120]


async def run_booking_agent(message: str, ctx: ToolContext, session) -> AgentResult:  # type: ignore[no-untyped-def]
    history = await chat_repo.last_messages(ctx.db, session.id, limit=20)
    messages: list[dict] = [{"role": "system", "content": build_system_prompt(ctx)}, *history, {"role": "user", "content": message}]
    base_len = len(messages)
    actions: list[ToolAction] = []
    spots, booking, reply = None, None, "Done."
    client = get_llama_client()
    for _ in range(ctx.settings.LLAMA_MAX_TOOL_ROUNDS):
        resp = await client.chat.completions.create(model=ctx.settings.LLAMA_MODEL, messages=messages, tools=TOOL_SPECS, tool_choice="auto", temperature=ctx.settings.LLAMA_TEMPERATURE)
        msg = resp.choices[0].message
        if not msg.tool_calls:
            reply = (msg.content or "").strip() or "Done."
            messages.append({"role": "assistant", "content": reply})
            break
        messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [tc.model_dump() for tc in msg.tool_calls]})
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args, result = {}, {"ok": False, "error": "malformed_arguments"}
            else:
                result = await execute_tool(tc.function.name, args, ctx)
            actions.append(ToolAction(tool=tc.function.name, arguments=args, ok=bool(result.get("ok", False)), summary=summarize(result)))
            if tc.function.name == "search_parking_spots" and result.get("ok"):
                spots = result["spots"]
            if tc.function.name in ("hold_spot", "confirm_booking") and result.get("ok"):
                booking = await booking_service.get_for_user(ctx.db, result["booking_id"], ctx.user)
            messages.append({"role": "tool", "tool_call_id": tc.id, "name": tc.function.name, "content": json.dumps(result, default=str)[:4000]})
    else:
        reply = "I couldn't finish that in time. Could you rephrase or try again?"
    return AgentResult(reply=reply, actions=actions, spots=spots, booking=booking, messages_to_persist=messages[base_len:])
