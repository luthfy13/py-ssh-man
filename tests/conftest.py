"""Shared pytest fixtures (SPEC §10.1)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Must run before Qt is imported: headless Linux has no display server.
if (
    sys.platform.startswith("linux")
    and not os.environ.get("DISPLAY")
    and not os.environ.get("WAYLAND_DISPLAY")
):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def pyssh_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate every test in its own data folder via ``PYSSH_HOME``."""
    home = tmp_path / "pyssh_home"
    home.mkdir()
    monkeypatch.setenv("PYSSH_HOME", str(home))
    return home
