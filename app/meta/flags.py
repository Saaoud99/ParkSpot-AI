"""Runtime feature flags an admin can toggle from the dashboard.

These are process-local master switches layered ON TOP of env config:
a feature runs only if (env configured) AND (flag on). They are not a
replacement for environment secrets, and changing them never touches
`.env`. A backend restart restores the defaults (all on).
"""
from __future__ import annotations

import threading


class FeatureFlags:
    KEYS = ("assistant", "voice", "vision")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._flags = {k: True for k in self.KEYS}

    def get(self, key: str) -> bool:
        with self._lock:
            return self._flags.get(key, False)

    def set(self, key: str, enabled: bool) -> None:
        if key not in self.KEYS:
            raise KeyError(key)
        with self._lock:
            self._flags[key] = bool(enabled)

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._flags)


FLAGS = FeatureFlags()
