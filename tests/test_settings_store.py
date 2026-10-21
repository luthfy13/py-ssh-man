"""Tests for core.settings_store (SPEC §6.4, §7.7)."""

from __future__ import annotations

import json
import stat
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from pyssh import config
from pyssh.core.settings_store import SettingsStore, read_language
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
        ("language", 1),
        ("language", None),
        ("language", ["en"]),
        ("language", "fr"),
        ("language", "EN"),
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


def test_language_defaults_to_indonesian_and_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    assert AppSettings().language == "id"
    store = SettingsStore(path, mac=False)
    store.save(replace(AppSettings(), language="en"))
    assert SettingsStore(path, mac=False).load().language == "en"
    assert read_language(path) == "en"


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (None, "id"),  # no file
        (json.dumps({"version": 1, "settings": {"language": "en"}}), "en"),
        (json.dumps({"version": 1, "settings": {"language": "id"}}), "id"),
        (json.dumps({"version": 1, "settings": {"language": "fr"}}), "id"),
        (json.dumps({"version": 1, "settings": {"language": 3}}), "id"),
        (json.dumps({"version": 1, "settings": {}}), "id"),
        (json.dumps({"version": 2, "settings": {"language": "en"}}), "id"),
        (json.dumps({"version": 1, "settings": []}), "id"),
        ("{not json", "id"),
        ("[1, 2]", "id"),
    ],
)
def test_read_language_matches_load_without_side_effects(
    tmp_path: Path, content: str | None, expected: str
) -> None:
    folder = tmp_path / "data"
    folder.mkdir()
    path = folder / "settings.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    assert read_language(path) == expected
    assert [p.name for p in folder.iterdir()] == ([] if content is None else [path.name])
    assert SettingsStore(path, mac=False).load().language == expected


def test_read_language_on_undecodable_file(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_bytes(b"\xff\xfe\x00garbage")
    assert read_language(path) == "id"
    assert path.exists()


# ----- highlight_prompt (design B.4) -------------------------------------------------------


def test_highlight_prompt_defaults_to_true(tmp_path: Path) -> None:
    assert AppSettings().highlight_prompt is True
    assert SettingsStore(tmp_path / "settings.json", mac=False).load().highlight_prompt is True
    assert SettingsStore(tmp_path / "mac.json", mac=True).load().highlight_prompt is True


def test_file_without_highlight_prompt_gets_true_and_keeps_other_values(tmp_path: Path) -> None:
    """A settings file written by an older PySSH has no such key."""
    path = tmp_path / "settings.json"
    _write(path, {"font_size": 15, "bold_is_bright": False})
    loaded = SettingsStore(path, mac=False).load()
    assert loaded.highlight_prompt is True
    assert loaded == replace(AppSettings(), font_size=15, bold_is_bright=False)


@pytest.mark.parametrize("value", [True, False])
def test_highlight_prompt_round_trips(tmp_path: Path, value: bool) -> None:
    path = tmp_path / "settings.json"
    SettingsStore(path, mac=False).save(replace(AppSettings(), highlight_prompt=value))
    assert json.loads(path.read_text(encoding="utf-8"))["settings"]["highlight_prompt"] is value
    assert SettingsStore(path, mac=False).load().highlight_prompt is value


@pytest.mark.parametrize("value", [False, True])
def test_highlight_prompt_loaded_from_json_boolean(tmp_path: Path, value: bool) -> None:
    path = tmp_path / "settings.json"
    _write(path, {"highlight_prompt": value})
    assert SettingsStore(path, mac=False).load().highlight_prompt is value


@pytest.mark.parametrize(
    "value",
    [0, 1, "false", "true", "no", "", None, 1.0, [], [False], {}],
)
def test_highlight_prompt_wrong_type_uses_default_true(tmp_path: Path, value: object) -> None:
    path = tmp_path / "settings.json"
    _write(path, {"highlight_prompt": value, "font_size": 15})
    loaded = SettingsStore(path, mac=False).load()
    assert loaded.highlight_prompt is True  # also for 0/"false": only a real bool counts
    assert loaded.font_size == 15  # the rest of the file is still used
    assert not list(tmp_path.glob("settings.json.corrupt-*"))  # not treated as a broken file


def test_highlight_prompt_is_independent_of_other_flags(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    custom = replace(
        AppSettings(), highlight_prompt=False, bold_is_bright=True, copy_on_select=False
    )
    SettingsStore(path, mac=False).save(custom)
    loaded = SettingsStore(path, mac=False).load()
    assert (loaded.highlight_prompt, loaded.bold_is_bright, loaded.copy_on_select) == (
        False,
        True,
        False,
    )
