"""Process identity for the backend: lets clients tell "restarted" from
"unreachable" and explains why in-memory counters and flags reset.

``INSTANCE_ID`` is a fresh random id per process start. The dashboard
remembers the last id it saw: a different id on the next poll means the
backend restarted; no response at all means it is unreachable.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

INSTANCE_ID: str = uuid.uuid4().hex[:12]
STARTED_AT: str = datetime.now(timezone.utc).isoformat(timespec="seconds")
_STARTED_MONO: float = time.monotonic()
VERSION = "1.1.0"


def uptime_s() -> int:
    return int(time.monotonic() - _STARTED_MONO)


def info() -> dict:
    """Safe-to-publish process facts (no hostnames, paths, or secrets)."""
    return {
        "instance_id": INSTANCE_ID,
        "started_at": STARTED_AT,
        "uptime_s": uptime_s(),
        "version": VERSION,
    }
