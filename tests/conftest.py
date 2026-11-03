"""Shared test setup.

Runtime AI switches persist to a JSON state file by default. Tests must
never write that file into the repository, so the path is redirected to a
throwaway directory *before* ``app.meta.flags`` is imported anywhere.
"""
from __future__ import annotations

import os
import tempfile

os.environ["AI_FLAGS_STATE_PATH"] = os.path.join(tempfile.mkdtemp(prefix="parkspot-flags-"), "ai_flags.json")
os.environ.pop("AI_MODULES_DEFAULT_OFF", None)
