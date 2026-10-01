"""Tests for terminal.demo_backend and tools/make_ansi_demo.py (SPEC §8.6)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from pyssh.models import AppSettings
from pyssh.terminal.demo_backend import DemoBackend, load_demo_text, render_input
from pyssh.terminal.widget import TerminalWidget

ROOT = Path(__file__).resolve().parent.parent


def _load_tool():
    spec = importlib.util.spec_from_file_location(
        "make_ansi_demo", ROOT / "tools" / "make_ansi_demo.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_render_input() -> None:
    assert render_input(b"abc") == b"abc"
    assert render_input(b"\x1b[A") == b"\x1b[36m\\x1b\x1b[0m[A"
    assert render_input(b"\r") == b"\r\n"
    assert render_input(b"\x03") == b"\x1b[36m\\x03\x1b[0m"
    assert render_input("é".encode()) == "é".encode()
    assert render_input(b"\xff") == b"\x1b[36m\\xff\x1b[0m"


def test_demo_resource_matches_generator() -> None:
    tool = _load_tool()
    resource = ROOT / "src" / "pyssh" / "resources" / "ansi_demo.txt"
    assert resource.read_text(encoding="utf-8") == tool.build_demo()


def test_demo_content() -> None:
    text = load_demo_text().decode("utf-8")
    assert "\r\n" in text and "\n" not in text.replace("\r\n", "")
    for needle in ("\x1b[48;5;", "\x1b[48;2;", "\x1b[9m", "┌", "漢字", "Bahasa Indonesia"):
        assert needle in text


def test_backend_shows_demo_and_echoes_keys(qtbot) -> None:
    terminal = TerminalWidget(AppSettings())
    qtbot.addWidget(terminal)
    terminal.resize(1000, 800)
    terminal.show()
    qtbot.waitExposed(terminal)
    backend = DemoBackend(terminal)
    backend.start()
    terminal.flush_pending()
    lines = [terminal.emulator.line_text(i) for i in range(terminal.emulator.total_lines)]
    assert any("Box drawing" in line for line in lines)
    terminal.input_bytes.emit(b"\x1b[A")
    terminal.flush_pending()
    assert terminal.emulator.screen_lines_text()[terminal.emulator.cursor.y].endswith("\\x1b[A")
