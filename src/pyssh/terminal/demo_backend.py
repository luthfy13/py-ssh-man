"""Local backend for ``--demo`` mode with a key inspector (SPEC §8.6)."""

from __future__ import annotations

from importlib import resources

from PySide6.QtCore import QObject

from pyssh import strings
from pyssh.terminal.widget import TerminalWidget

DEMO_RESOURCE = "ansi_demo.txt"
_CYAN = "\x1b[36m"
_RESET = "\x1b[0m"


def load_demo_text() -> bytes:
    """Content of ``resources/ansi_demo.txt`` with line feeds turned into CR LF."""
    data = resources.files("pyssh").joinpath("resources", DEMO_RESOURCE).read_bytes()
    return data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")


def render_input(data: bytes) -> bytes:
    """Key inspector view of input bytes: printable as-is, others as cyan ``\\xNN``."""
    out: list[str] = []
    for char in data.decode("utf-8", errors="surrogateescape"):
        if char == "\r":
            out.append("\r\n")
        elif char.isprintable():
            out.append(char)
        else:
            raw = char.encode("utf-8", errors="surrogateescape")
            out.append(_CYAN + "".join(f"\\x{byte:02x}" for byte in raw) + _RESET)
    return "".join(out).encode("utf-8", errors="surrogateescape")


class DemoBackend(QObject):
    """Shows the ANSI demo, then echoes every input byte in inspector notation."""

    def __init__(self, terminal: TerminalWidget) -> None:
        """Attach to ``terminal`` (the terminal owns this object)."""
        super().__init__(terminal)
        self._terminal = terminal
        terminal.input_bytes.connect(self._on_input)

    def start(self) -> None:
        """Display the demo text and the inspector header."""
        self._terminal.feed(load_demo_text())
        self._terminal.write_local(strings.DEMO_INSPECTOR_HEADER, "cyan")

    def _on_input(self, data: bytes) -> None:
        self._terminal.feed(render_input(data))
