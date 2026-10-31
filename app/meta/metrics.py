"""In-memory AI service metrics — real counters since process start.

Distinguishes *configured* (env present), *reachable* (health probe got an
HTTP response) and *successfully used* (a request actually succeeded here).
Nothing here is persisted; a restart resets the counters, and the admin UI
says so. Never stores prompts, audio, images, or credentials.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Metrics:
    SERVICES = ("muse_spark", "muse_voice", "sam", "easyocr")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started = _now()
        self._d = {s: {"requests": 0, "errors": 0, "latency_ms_total": 0.0,
                       "last_success_at": None, "last_error": None, "last_error_at": None}
                   for s in self.SERVICES}

    def record(self, service: str, ok: bool, latency_ms: float = 0.0, error: str | None = None) -> None:
        if service not in self._d:
            return
        with self._lock:
            m = self._d[service]
            m["requests"] += 1
            m["latency_ms_total"] += latency_ms
            if ok:
                m["last_success_at"] = _now()
            else:
                m["errors"] += 1
                m["last_error"] = (error or "error")[:200]
                m["last_error_at"] = _now()

    def snapshot(self) -> dict:
        with self._lock:
            out = {}
            for s, m in self._d.items():
                n = m["requests"]
                out[s] = {**m, "avg_latency_ms": round(m["latency_ms_total"] / n, 1) if n else None}
            return {"since": self._started, "services": out}


METRICS = Metrics()
_started_perf = time.perf_counter()


def elapsed_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000.0
