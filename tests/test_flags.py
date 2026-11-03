"""Runtime AI module switches: aliases, persistence, honest degradation."""
from __future__ import annotations

import json
import os
import stat

import pytest

from app.meta.flags import ALIASES, LABELS, MODULES, FeatureFlags, resolve


def test_modules_match_dashboard_cards():
    assert MODULES == ("muse_spark", "muse_voice", "sam", "easyocr")
    assert set(LABELS) == set(MODULES)
    assert resolve("vision") == ("sam", "easyocr")
    assert resolve("assistant") == ("muse_spark",)
    with pytest.raises(KeyError):
        resolve("nope")


def test_defaults_all_on_memory_only():
    f = FeatureFlags(None)
    assert f.snapshot() == {m: True for m in MODULES}
    assert f.state_info()["persistent"] is False
    assert f.persisted is None
    assert f.get("unknown") is False


def test_module_toggle_is_independent_and_alias_groups(tmp_path):
    f = FeatureFlags(tmp_path / "flags.json")
    assert f.set("sam", False, actor="u1") == ["sam"]
    assert f.get("sam") is False
    assert f.get("easyocr") is True
    assert f.get("vision") is False  # group is on only if every member is on
    assert f.set("vision", True) == ["sam", "easyocr"]
    assert f.get("vision") is True
    details = f.details()
    assert details["sam"]["updated_at"] is not None
    assert details["sam"]["label"] == "SAM 3.1"


def test_toggles_survive_restart(tmp_path):
    path = tmp_path / "flags.json"
    first = FeatureFlags(path)
    first.set("muse_voice", False, actor="admin-1")
    assert first.persisted is True
    data = json.loads(path.read_text())
    assert data["modules"]["muse_voice"]["enabled"] is False
    assert data["modules"]["muse_voice"]["updated_by"] == "admin-1"

    restarted = FeatureFlags(path)  # simulates a new backend process
    assert restarted.get("muse_voice") is False
    assert restarted.get("muse_spark") is True
    assert restarted.loaded_from == "file"
    assert restarted.details()["muse_voice"]["updated_by"] == "admin-1"


def test_default_off_applies_only_without_state_file(tmp_path):
    path = tmp_path / "flags.json"
    f = FeatureFlags(path, {"sam", "easyocr", "bogus"})
    assert f.snapshot() == {"muse_spark": True, "muse_voice": True, "sam": False, "easyocr": False}
    assert f.state_info()["default_off"] == ["easyocr", "sam"]
    f.set("sam", True)
    again = FeatureFlags(path, {"sam", "easyocr"})
    assert again.get("sam") is True  # persisted admin choice wins over env default


def test_corrupt_state_file_falls_back_to_defaults(tmp_path):
    path = tmp_path / "flags.json"
    path.write_text("{not json")
    f = FeatureFlags(path)
    assert f.snapshot() == {m: True for m in MODULES}
    assert f.loaded_from == "defaults"
    assert "corrupt" in (f.last_error or "")
    path.write_text(json.dumps({"modules": {"sam": False, "easyocr": "yes"}}))
    g = FeatureFlags(path)
    assert g.get("sam") is False
    assert g.get("easyocr") is True  # malformed entry ignored


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_unwritable_state_still_toggles_in_memory(tmp_path):
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        f = FeatureFlags(locked / "flags.json")
        f.set("easyocr", False)
        assert f.get("easyocr") is False
        assert f.persisted is False
        assert "not writable" in (f.last_error or "")
        assert f.state_info()["persistent"] is True
    finally:
        locked.chmod(stat.S_IRWXU)


def test_from_env_reads_path_and_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_FLAGS_STATE_PATH", str(tmp_path / "x.json"))
    monkeypatch.setenv("AI_MODULES_DEFAULT_OFF", "muse_voice, SAM")
    f = FeatureFlags.from_env()
    assert f.get("muse_voice") is False and f.get("sam") is False and f.get("muse_spark") is True
    monkeypatch.setenv("AI_FLAGS_STATE_PATH", "")
    assert FeatureFlags.from_env().state_info()["persistent"] is False
