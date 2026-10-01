"""Application constants, platform flags and data folder locations (SPEC §6.1, §7.1).

This is the only module allowed to inspect ``sys.platform`` (rule A12).
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "PySSH"
APP_ORG = "PySSH"

IS_WINDOWS = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

DIR_MODE = 0o700
FILE_MODE = 0o600


@dataclass(frozen=True)
class AppPaths:
    """Locations of every file in the data folder."""

    root: Path
    db_file: Path
    settings_file: Path
    known_hosts_file: Path
    log_dir: Path
    log_file: Path

    @classmethod
    def from_root(cls, root: Path) -> AppPaths:
        """Build all paths below ``root``."""
        log_dir = root / "logs"
        return cls(
            root=root,
            db_file=root / "pyssh.db",
            settings_file=root / "settings.json",
            known_hosts_file=root / "known_hosts",
            log_dir=log_dir,
            log_file=log_dir / "pyssh.log",
        )


def _data_root(platform: str, env: Mapping[str, str], home: Path) -> Path:
    if env.get("PYSSH_HOME"):
        return Path(env["PYSSH_HOME"])
    if platform == "win32":
        appdata = env.get("APPDATA")
        base = Path(appdata) if appdata else home / "AppData" / "Roaming"
        return base / APP_NAME
    if platform == "darwin":
        return home / "Library" / "Application Support" / APP_NAME
    xdg = env.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else home / ".local" / "share"
    return base / APP_NAME.lower()


def get_paths(
    *,
    platform: str = sys.platform,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> AppPaths:
    """Return the data paths: ``PYSSH_HOME`` first, otherwise the per-OS default (SPEC §6.1)."""
    env = os.environ if env is None else env
    home = Path.home() if home is None else home
    return AppPaths.from_root(_data_root(platform, env, home))


def ensure_dirs(paths: AppPaths) -> None:
    """Create the data and log folders; mode ``0o700`` on POSIX."""
    for directory in (paths.root, paths.log_dir):
        directory.mkdir(parents=True, exist_ok=True)
        if not IS_WINDOWS:
            directory.chmod(DIR_MODE)


def restrict_file(path: Path) -> None:
    """Restrict a file to its owner (``0o600``) on POSIX; no-op on Windows."""
    if not IS_WINDOWS:
        path.chmod(FILE_MODE)
