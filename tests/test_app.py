"""Tests for app.main(): --version, startup files, database errors (SPEC §9.2, AC-1.4)."""

from __future__ import annotations

import sqlite3
import sys
import threading
from pathlib import Path

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from pyssh import app as app_module
from pyssh.logging_setup import shutdown_logging


@pytest.fixture(autouse=True)
def _restore_hooks(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    yield
    shutdown_logging()


def _close_windows_soon() -> None:
    def close_all() -> None:
        for widget in QApplication.topLevelWidgets():
            widget.close()

    QTimer.singleShot(50, close_all)


def test_version_prints_and_exits(capsys: pytest.CaptureFixture[str], pyssh_home: Path) -> None:
    assert app_module.main(["--version"]) == 0
    assert capsys.readouterr().out == "PySSH 0.1.0\n"
    assert list(pyssh_home.iterdir()) == []  # nothing created


def test_startup_creates_data_and_logs_startup_ms(qapp, pyssh_home: Path) -> None:
    _close_windows_soon()
    assert app_module.main([]) == 0
    assert (pyssh_home / "pyssh.db").is_file()
    log_text = (pyssh_home / "logs" / "pyssh.log").read_text(encoding="utf-8")
    assert "startup startup_ms=" in log_text


def test_newer_database_exits_with_code_2(
    qapp, pyssh_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = sqlite3.connect(pyssh_home / "pyssh.db")
    conn.execute("PRAGMA user_version = 7")
    conn.commit()
    conn.close()
    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: shown.append(a[2]))
    assert app_module.main([]) == app_module.EXIT_DB_VERSION == 2
    assert len(shown) == 1
    assert "lebih baru" in shown[0]


def test_corrupt_database_warning_is_shown(
    qapp, pyssh_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (pyssh_home / "pyssh.db").write_bytes(b"garbage" * 300)
    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: shown.append(a[2]))
    _close_windows_soon()
    assert app_module.main(["--debug"]) == 0
    assert len(shown) == 1
    assert "corrupt" in shown[0]


def test_excepthook_logs_and_shows_message(
    qapp, pyssh_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: shown.append(a[2]))
    app_module.install_excepthooks("/tmp/x.log")
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        sys.excepthook(*sys.exc_info())
    assert shown and "RuntimeError" in shown[0]

    def fail() -> None:
        raise ValueError("thread boom")

    t = threading.Thread(target=fail, name="t-test")
    t.start()
    t.join()
    assert len(shown) == 1  # worker threads only log
