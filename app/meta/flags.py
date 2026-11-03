"""Runtime on/off switches for each AI integration module.

Modules match the dashboard cards one-to-one:

    muse_spark   Muse Spark assistant (Meta Model API chat)
    muse_voice   Muse Voice Transcribe
    sam          SAM 3.1 vision (self-hosted segmentation service)
    easyocr      EasyOCR plate reading

A module runs only if (env configured) AND (switch on). Switches never
touch ``.env`` or credentials; they are an admin-controlled master switch
layered on top of configuration.

Persistence: the current switch state is written atomically to a small
JSON file (``AI_FLAGS_STATE_PATH``, default ``.ai_flags.json`` next to
``.env``) so an admin's toggles survive a backend restart. Set the
variable to an empty string for memory-only switches that reset on
restart. ``AI_MODULES_DEFAULT_OFF`` (comma-separated module names) picks
which modules start disabled when no state file exists.

Legacy aliases ``assistant`` / ``voice`` / ``vision`` are still accepted
(``vision`` maps to both ``sam`` and ``easyocr``) so older clients and
audit entries keep working.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("parkspot.meta.flags")

MODULES: tuple[str, ...] = ("muse_spark", "muse_voice", "sam", "easyocr")
LABELS: dict[str, str] = {
    "muse_spark": "Muse Spark",
    "muse_voice": "Muse Voice Transcribe",
    "sam": "SAM 3.1",
    "easyocr": "EasyOCR",
}
ALIASES: dict[str, tuple[str, ...]] = {
    "assistant": ("muse_spark",),
    "voice": ("muse_voice",),
    "vision": ("sam", "easyocr"),
}
KEYS: tuple[str, ...] = MODULES + tuple(ALIASES)
_STATE_VERSION = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def resolve(key: str) -> tuple[str, ...]:
    """Map a module name or legacy alias to the modules it controls."""
    if key in MODULES:
        return (key,)
    if key in ALIASES:
        return ALIASES[key]
    raise KeyError(key)


def default_state_path() -> Path:
    # Same directory the dotenv loader uses for `.env` (repo root).
    return Path(__file__).resolve().parents[2] / ".ai_flags.json"


class FeatureFlags:
    KEYS = KEYS  # kept for callers that introspect the old attribute

    def __init__(self, state_path: Path | str | None = None,
                 default_off: set[str] | frozenset[str] | None = None) -> None:
        self._lock = threading.Lock()
        self._path: Path | None = Path(state_path) if state_path else None
        self._default_off = {m for m in (default_off or ()) if m in MODULES}
        self._flags: dict[str, bool] = {m: m not in self._default_off for m in MODULES}
        self._meta: dict[str, dict] = {m: {"updated_at": None, "updated_by": None} for m in MODULES}
        self.loaded_from = "defaults"
        self.persisted: bool | None = None  # None = persistence disabled
        self.last_error: str | None = None
        if self._path is not None:
            self._load()

    # ----------------------------------------------------------- construction
    @classmethod
    def from_env(cls) -> "FeatureFlags":
        from .config import _load_dotenv  # local import: config imports nothing from here
        _load_dotenv()
        raw_path = os.environ.get("AI_FLAGS_STATE_PATH")
        if raw_path is None:
            path: Path | None = default_state_path()
        else:
            path = Path(raw_path.strip()) if raw_path.strip() else None
        off = {m.strip().lower() for m in os.environ.get("AI_MODULES_DEFAULT_OFF", "").split(",") if m.strip()}
        unknown = off - set(MODULES)
        if unknown:
            log.warning("AI_MODULES_DEFAULT_OFF ignores unknown modules: %s", ", ".join(sorted(unknown)))
        return cls(path, off)

    def configure(self, state_path: Path | str | None, default_off: set[str] | None = None) -> None:
        """Re-point the singleton (tests / embedding); reloads from disk."""
        with self._lock:
            self.__init__(state_path, default_off)  # type: ignore[misc]

    # ------------------------------------------------------------------ reads
    def get(self, key: str) -> bool:
        """True only if every module behind ``key`` is enabled."""
        modules = resolve(key) if key in KEYS else ()
        if not modules:
            return False
        with self._lock:
            return all(self._flags[m] for m in modules)

    def snapshot(self) -> dict[str, bool]:
        with self._lock:
            return dict(self._flags)

    def details(self) -> dict[str, dict]:
        with self._lock:
            return {m: {"enabled": self._flags[m], "label": LABELS[m], **self._meta[m]} for m in MODULES}

    def state_info(self) -> dict:
        """How the switches are stored, for the dashboard's honesty line."""
        return {
            "persistent": self._path is not None,
            "persisted": self.persisted,
            "loaded_from": self.loaded_from,
            "state_file": self._path.name if self._path is not None else None,
            "last_error": self.last_error,
            "default_off": sorted(self._default_off),
        }

    # ----------------------------------------------------------------- writes
    def set(self, key: str, enabled: bool, actor: str | None = None) -> list[str]:
        """Switch a module (or alias group). Returns the modules changed."""
        modules = resolve(key)  # KeyError for unknown keys, as before
        stamp = _now()
        with self._lock:
            for m in modules:
                self._flags[m] = bool(enabled)
                self._meta[m] = {"updated_at": stamp, "updated_by": actor}
            self._save_locked()
        return list(modules)

    # ------------------------------------------------------------ persistence
    def _load(self) -> None:
        assert self._path is not None
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            self.loaded_from = "defaults"
            return
        except OSError as e:
            self.loaded_from = "defaults"
            self.last_error = f"state file unreadable: {e.__class__.__name__}"
            log.warning("AI flags state file %s unreadable (%s); using defaults", self._path, e)
            return
        try:
            data = json.loads(raw)
            modules = data.get("modules") if isinstance(data, dict) else None
            if not isinstance(modules, dict):
                raise ValueError("missing modules map")
        except ValueError as e:
            self.loaded_from = "defaults"
            self.last_error = "state file corrupt; defaults applied"
            log.warning("AI flags state file %s corrupt (%s); using defaults", self._path, e)
            return
        for m in MODULES:
            entry = modules.get(m)
            if isinstance(entry, bool):
                self._flags[m] = entry
            elif isinstance(entry, dict) and isinstance(entry.get("enabled"), bool):
                self._flags[m] = entry["enabled"]
                self._meta[m] = {"updated_at": entry.get("updated_at"), "updated_by": entry.get("updated_by")}
        self.loaded_from = "file"
        self.persisted = True

    def _save_locked(self) -> None:
        if self._path is None:
            return
        payload = {
            "version": _STATE_VERSION,
            "updated_at": _now(),
            "modules": {m: {"enabled": self._flags[m], **self._meta[m]} for m in MODULES},
        }
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            os.replace(tmp, self._path)
            self.persisted = True
            self.last_error = None
        except OSError as e:
            # The switch still applies in memory; the dashboard is told it
            # will not survive a restart.
            self.persisted = False
            self.last_error = f"state file not writable: {e.__class__.__name__}"
            log.warning("could not persist AI flags to %s: %s", self._path, e)
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass


FLAGS = FeatureFlags.from_env()
