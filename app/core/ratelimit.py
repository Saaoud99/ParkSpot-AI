"""Small in-process sliding-window rate limiter.

Single-process deployments (the bundled SQLite demo) get real brute-force /
abuse protection from this. Multi-process production deployments must also
enforce limits at the gateway / with a shared store — this is defence in
depth, not a distributed limiter.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.exceptions import RateLimitError

_hits: dict[str, deque[float]] = defaultdict(deque)


def _client_key(request: Request, scope: str, identity: str = "") -> str:
    ip = request.client.host if request.client else "unknown"
    return f"{scope}:{ip}:{identity}"


def check_rate_limit(request: Request, scope: str, limit: int, window_seconds: int, identity: str = "") -> None:
    key = _client_key(request, scope, identity.lower())
    now = time.monotonic()
    bucket = _hits[key]
    while bucket and bucket[0] <= now - window_seconds:
        bucket.popleft()
    if len(bucket) >= limit:
        raise RateLimitError("too many attempts — please wait a moment and try again", code="rate_limited")
    bucket.append(now)
    # Opportunistic cleanup so distinct keys don't grow without bound.
    if len(_hits) > 10_000:
        stale = [k for k, v in _hits.items() if not v or v[-1] <= now - window_seconds]
        for k in stale[:1000]:
            _hits.pop(k, None)


def reset_rate_limits() -> None:
    _hits.clear()
