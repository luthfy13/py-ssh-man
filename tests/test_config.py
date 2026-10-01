"""Tests for config: data paths per platform, folder creation and permissions."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from pyssh import config

HOME = Path("/home/tester")


def test_pyssh_home_overrides_everything(tmp_path: Path) -> None:
    for platform in ("win32", "darwin", "linux"):
        paths = config.get_paths(
            platform=platform, env={"PYSSH_HOME": str(tmp_path), "APPDATA": "x"}, home=HOME
        )
        assert paths.root == tmp_path


def test_windows_uses_appdata() -> None:
    paths = config.get_paths(
        platform="win32", env={"APPDATA": "C:/Users/t/AppData/Roaming"}, home=HOME
    )
    assert paths.root == Path("C:/Users/t/AppData/Roaming") / "PySSH"


def test_windows_without_appdata_falls_back_to_profile() -> None:
    paths = config.get_paths(platform="win32", env={}, home=HOME)
    assert paths.root == HOME / "AppData" / "Roaming" / "PySSH"


def test_macos_application_support() -> None:
    paths = config.get_paths(platform="darwin", env={}, home=HOME)
    assert paths.root == HOME / "Library" / "Application Support" / "PySSH"


def test_linux_xdg_data_home() -> None:
    paths = config.get_paths(platform="linux", env={"XDG_DATA_HOME": "/data/x"}, home=HOME)
    assert paths.root == Path("/data/x/pyssh")


def test_linux_without_xdg() -> None:
    for env in ({}, {"XDG_DATA_HOME": ""}):
        paths = config.get_paths(platform="linux", env=env, home=HOME)
        assert paths.root == HOME / ".local" / "share" / "pyssh"


def test_empty_pyssh_home_is_ignored() -> None:
    paths = config.get_paths(platform="linux", env={"PYSSH_HOME": ""}, home=HOME)
    assert paths.root == HOME / ".local" / "share" / "pyssh"


def test_default_reads_environment(pyssh_home: Path) -> None:
    assert config.get_paths().root == pyssh_home


def test_app_paths_structure(tmp_path: Path) -> None:
    paths = config.AppPaths.from_root(tmp_path)
    assert paths.db_file == tmp_path / "pyssh.db"
    assert paths.settings_file == tmp_path / "settings.json"
    assert paths.known_hosts_file == tmp_path / "known_hosts"
    assert paths.log_dir == tmp_path / "logs"
    assert paths.log_file == tmp_path / "logs" / "pyssh.log"


def test_ensure_dirs_creates_folders(tmp_path: Path) -> None:
    paths = config.AppPaths.from_root(tmp_path / "a" / "b")
    config.ensure_dirs(paths)
    config.ensure_dirs(paths)  # idempotent
    assert paths.root.is_dir()
    assert paths.log_dir.is_dir()


@pytest.mark.skipif(config.IS_WINDOWS, reason="POSIX permissions")
def test_posix_permissions(tmp_path: Path) -> None:
    paths = config.AppPaths.from_root(tmp_path / "data")
    config.ensure_dirs(paths)
    assert stat.S_IMODE(paths.root.stat().st_mode) == 0o700
    assert stat.S_IMODE(paths.log_dir.stat().st_mode) == 0o700
    paths.db_file.write_bytes(b"")
    paths.db_file.chmod(0o644)
    config.restrict_file(paths.db_file)
    assert stat.S_IMODE(paths.db_file.stat().st_mode) == 0o600


def test_platform_flags_are_consistent() -> None:
    assert sum([config.IS_WINDOWS, config.IS_MAC, config.IS_LINUX]) <= 1
    assert config.APP_NAME == "PySSH"
