from __future__ import annotations

import json
import re

from app.core.config import get_settings
from app.core.exceptions import UpstreamError


def get_llama_client():  # type: ignore[no-untyped-def]
    from openai import AsyncOpenAI

    s = get_settings()
    return AsyncOpenAI(base_url=s.LLAMA_BASE_URL, api_key=s.LLAMA_API_KEY or "none", timeout=s.LLAMA_TIMEOUT_SECONDS, max_retries=1)


async def chat_json(system: str, user: str) -> dict:
    s = get_settings()
    client = get_llama_client()
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    try:
        try:
            resp = await client.chat.completions.create(model=s.LLAMA_MODEL, messages=messages, response_format={"type": "json_object"}, temperature=0.2)
        except Exception:
            resp = await client.chat.completions.create(model=s.LLAMA_MODEL, messages=messages, temperature=0.2)
        content = resp.choices[0].message.content or ""
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise UpstreamError("llm returned no JSON")
        return json.loads(match.group(0))
    except UpstreamError:
        raise
    except Exception as exc:
        raise UpstreamError(f"llm call failed: {exc}") from exc
