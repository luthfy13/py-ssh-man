"""Read and write ``settings.json`` with defaults and clamping (SPEC §6.4, §7.7)."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, fields
from datetime import datetime
from pathlib import Path
from typing import Any

from pyssh import config
from pyssh.models import AppSettings, default_settings

log = logging.getLogger(__name__)

FILE_VERSION = 1

# field name -> (minimum, maximum)
CLAMP_RANGES: dict[str, tuple[int, int]] = {
    "font_size": (6, 32),
    "scrollback_lines": (100, 100_000),
    "keepalive_seconds": (0, 600),
    "connect_timeout_seconds": (3, 120),
}
_BOOL_FIELDS = {"copy_on_select", "bold_is_bright", "confirm_on_close", "mac_option_as_meta"}
_STR_FIELDS = {"font_family"}
_OPTIONAL_STR_FIELDS = {"window_geometry", "window_state", "splitter_state"}


def write_json_atomic(path: Path, data: Any) -> None:
    """Write JSON atomically: ``.tmp`` → flush → fsync → ``os.replace`` (rule A9)."""
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _clamp(name: str, value: int) -> int:
    low, high = CLAMP_RANGES[name]
    clamped = min(max(value, low), high)
    if clamped != value:
        log.warning("setting %s=%d out of range, clamped to %d", name, value, clamped)
    return clamped


def _coerce(name: str, value: Any, default: Any) -> Any:
    """Validate one value; wrong type → default (logged), out of range → clamped."""
    if name in CLAMP_RANGES:
        if isinstance(value, bool) or not isinstance(value, int):
            log.warning("setting %s has wrong type, using default", name)
            return default
        return _clamp(name, value)
    if name in _BOOL_FIELDS:
        ok = isinstance(value, bool)
    elif name in _STR_FIELDS:
        ok = isinstance(value, str)
    elif name in _OPTIONAL_STR_FIELDS:
        ok = value is None or isinstance(value, str)
    else:  # pragma: no cover - every AppSettings field is listed above
        ok = False
    if not ok:
        log.warning("setting %s has wrong type, using default", name)
        return default
    return value


class SettingsStore:
    """Application settings backed by a JSON file."""

    def __init__(self, path: Path, *, mac: bool = config.IS_MAC) -> None:
        """Remember the file path; ``current`` starts with the platform defaults."""
        self._path = path
        self._mac = mac
        self._current = default_settings(mac=mac)

    @property
    def current(self) -> AppSettings:
        """The settings loaded or saved most recently."""
        return self._current

    def load(self) -> AppSettings:
        """Load settings; missing file → defaults; unreadable file → backup + defaults."""
        defaults = default_settings(mac=self._mac)
        if not self._path.exists():
            self._current = defaults
            return self._current
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if (
                not isinstance(data, dict)
                or data.get("version") != FILE_VERSION
                or not isinstance(data.get("settings"), dict)
            ):
                raise ValueError("unexpected settings.json structure")
        except (OSError, ValueError) as exc:
            log.warning("settings.json unreadable (%s); using defaults", exc)
            self._move_aside()
            self._current = defaults
            return self._current

        raw = data["settings"]
        values = {}
        for f in fields(AppSettings):
            default = getattr(defaults, f.name)
            values[f.name] = _coerce(f.name, raw[f.name], default) if f.name in raw else default
        self._current = AppSettings(**values)
        return self._current

    def save(self, settings: AppSettings) -> None:
        """Save atomically and restrict the file permissions."""
        write_json_atomic(self._path, {"version": FILE_VERSION, "settings": asdict(settings)})
        config.restrict_file(self._path)
        self._current = settings

    def _move_aside(self) -> None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = self._path.with_name(f"{self._path.name}.corrupt-{stamp}")
        try:
            self._path.replace(backup)
        except OSError as exc:
            log.warning("could not move unreadable settings.json aside: %s", exc)
