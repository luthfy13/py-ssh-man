"""Tests for core.settings_store (SPEC §6.4, §7.7)."""

from __future__ import annotations

import json
import stat
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from pyssh import config
from pyssh.core.settings_store import SettingsStore
from pyssh.models import AppSettings


def _write(path: Path, settings: dict, version: int = 1) -> None:
    path.write_text(json.dumps({"version": version, "settings": settings}), encoding="utf-8")


def test_missing_file_gives_defaults(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "settings.json", mac=False)
    assert store.load() == AppSettings()
    assert store.current == AppSettings()
    assert SettingsStore(tmp_path / "s.json", mac=True).load().font_size == 12


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    store = SettingsStore(path, mac=False)
    custom = replace(AppSettings(), font_family="Menlo", font_size=14, window_geometry="AAA=")
    store.save(custom)
    assert store.current == custom
    assert SettingsStore(path, mac=False).load() == custom
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert data["settings"] == asdict(custom)
    assert not path.with_name("settings.json.tmp").exists()


@pytest.mark.skipif(config.IS_WINDOWS, reason="POSIX permissions")
def test_saved_file_is_private(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    SettingsStore(path, mac=False).save(AppSettings())
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_partial_file_uses_defaults_for_missing(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    _write(path, {"font_size": 15, "unknown_key": 1})
    loaded = SettingsStore(path, mac=False).load()
    assert loaded == replace(AppSettings(), font_size=15)


@pytest.mark.parametrize(
    ("name", "value", "expected"),
    [
        ("font_size", 2, 6),
        ("font_size", 99, 32),
        ("scrollback_lines", 10, 100),
        ("scrollback_lines", 10**7, 100_000),
        ("keepalive_seconds", -5, 0),
        ("keepalive_seconds", 601, 600),
        ("connect_timeout_seconds", 1, 3),
        ("connect_timeout_seconds", 500, 120),
    ],
)
def test_out_of_range_values_are_clamped(
    tmp_path: Path, name: str, value: int, expected: int
) -> None:
    path = tmp_path / "settings.json"
    _write(path, {name: value})
    assert getattr(SettingsStore(path, mac=False).load(), name) == expected


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("font_size", "11"),
        ("font_size", True),
        ("font_size", 11.5),
        ("copy_on_select", 1),
        ("font_family", 5),
        ("window_geometry", 7),
        ("mac_option_as_meta", "yes"),
    ],
)
def test_wrong_type_uses_default(tmp_path: Path, name: str, value: object) -> None:
    path = tmp_path / "settings.json"
    _write(path, {name: value})
    assert getattr(SettingsStore(path, mac=False).load(), name) == getattr(AppSettings(), name)


@pytest.mark.parametrize(
    "content",
    [
        "{not json",
        "[1, 2]",
        json.dumps({"version": 2, "settings": {}}),
        json.dumps({"version": 1, "settings": []}),
    ],
)
def test_unreadable_file_is_backed_up(tmp_path: Path, content: str) -> None:
    path = tmp_path / "settings.json"
    path.write_text(content, encoding="utf-8")
    store = SettingsStore(path, mac=False)
    assert store.load() == AppSettings()
    backups = list(tmp_path.glob("settings.json.corrupt-*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == content
    assert not path.exists()
