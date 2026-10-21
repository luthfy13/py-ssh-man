"""Re-record the nano scroll fixtures in ``tests/data/`` (Linux only, needs ``nano``).

``tests/test_emulator_scroll.py`` replays raw byte streams captured from a real nano 7.2
(ncurses, ``TERM=xterm-256color``, 80x24, through a pty). nano scrolls with ``CSI n S`` (SU)
and ``CSI n T`` (SD) when several Down/Up keys arrive at once, e.g. when a key is held down
over SSH; single key presses scroll with LF, which was always handled.

The edited file has 300 lines ``baris NNN isi teks contoh``. Each scenario sends its key
presses to nano in batches (one ``write`` per batch) and the output is saved *before* nano is
closed, so the recording ends with nano's alternate screen still showing.

nano is started with the relative name ``sample.txt`` inside a temporary folder, so its title bar
shows just ``sample.txt`` and the fixtures carry no path of the machine that made them.

Run: ``python tools/record_nano_scroll.py [--out DIR]`` (default ``tests/data``). Afterwards
every recording is replayed through ``TerminalEmulator`` and checked; the exit status is 1
when a check fails. Nothing runs on import.
"""

from __future__ import annotations

import argparse
import os
import re
import select
import shutil
import struct
import sys
import tempfile
import time
from collections import Counter
from itertools import pairwise
from pathlib import Path
from typing import NamedTuple

COLS = 80
ROWS = 24
FILE_LINES = 300
FILE_NAME = "sample.txt"
DOWN = b"\x1b[B"
UP = b"\x1b[A"
PAGE_DOWN = b"\x1b[6~"
CTRL_X = b"\x18"
STARTUP_QUIET = 0.5  # seconds without output that mean "nano has drawn its first screen"
BATCH_QUIET = 0.15  # same, after each batch of keys
BODY_ROWS = range(1, 21)  # screen rows (0-based) holding the 20 text lines of nano

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "tests" / "data"


class Scenario(NamedTuple):
    """One recording: ``writes`` writes of ``per_write`` key presses each."""

    name: str
    key: bytes
    per_write: int
    writes: int
    page_downs: int = 0  # PgDn presses sent first (one write), to start in the middle of the file
    expect: bytes = b""  # CSI final byte that must appear in the recording ("" = none needed)


SCENARIOS = (
    Scenario("nano_down_single", DOWN, 1, 80),
    Scenario("nano_down_batch2", DOWN, 2, 25, expect=b"S"),
    Scenario("nano_down_batch3", DOWN, 3, 25, expect=b"S"),
    Scenario("nano_down_batch5", DOWN, 5, 25, expect=b"S"),
    Scenario("nano_up_batch3", UP, 3, 20, page_downs=6, expect=b"T"),
)


def make_text() -> str:
    """The 300-line file that nano opens."""
    return "".join(f"baris {n:03d} isi teks contoh\n" for n in range(1, FILE_LINES + 1))


def _drain(fd: int, out: bytearray, quiet: float, limit: float = 10.0) -> None:
    """Read from ``fd`` into ``out`` until ``quiet`` seconds pass without data."""
    started = last = time.monotonic()
    while time.monotonic() - last < quiet and time.monotonic() - started < limit:
        ready, _, _ = select.select([fd], [], [], 0.02)
        if not ready:
            continue
        try:
            chunk = os.read(fd, 65536)
        except OSError:  # EIO: nano exited
            return
        if not chunk:
            return
        out.extend(chunk)
        last = time.monotonic()


def record(scenario: Scenario, workdir: Path) -> bytes:
    """Run nano in a pty and return everything it printed for ``scenario``."""
    import fcntl  # Linux/macOS only, hence not imported at module level
    import pty
    import signal
    import termios

    pid, fd = pty.fork()
    if pid == 0:  # child: become nano
        try:
            os.chdir(workdir)
            fcntl.ioctl(0, termios.TIOCSWINSZ, struct.pack("HHHH", ROWS, COLS, 0, 0))
            os.environ.update(TERM="xterm-256color", LANG="C.UTF-8")
            os.execvp("nano", ["nano", "--ignorercfiles", FILE_NAME])
        finally:
            os._exit(127)
    out = bytearray()
    try:
        _drain(fd, out, STARTUP_QUIET)
        if scenario.page_downs:
            os.write(fd, PAGE_DOWN * scenario.page_downs)
            _drain(fd, out, BATCH_QUIET)
        for _ in range(scenario.writes):
            os.write(fd, scenario.key * scenario.per_write)
            _drain(fd, out, BATCH_QUIET)
        data = bytes(out)
        os.write(fd, CTRL_X)  # file is unmodified, so nano quits without asking
        _drain(fd, bytearray(), BATCH_QUIET)
    finally:
        os.close(fd)
        try:
            if os.waitpid(pid, os.WNOHANG) == (0, 0):
                os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
        except ChildProcessError:
            pass
    return data


def check(scenario: Scenario, data: bytes, workdir: Path | None = None) -> list[str]:
    """Replay ``data`` through ``TerminalEmulator``; return a list of problems (empty = fine).

    ``workdir`` is the temporary folder nano ran in; its path must not appear in ``data``.
    """
    from pyssh.terminal.emulator import TerminalEmulator

    problems = []
    if FILE_NAME.encode() not in data:
        problems.append(f"the title bar does not show {FILE_NAME}")
    if workdir is not None and str(workdir).encode() in data:
        problems.append(f"the recording contains the local path {workdir}")
    finals = Counter(re.findall(rb"\x1b\[\d*([ST])", data))
    if scenario.expect and not finals[scenario.expect]:
        problems.append(
            f"no CSI n {scenario.expect.decode()} in the recording: the keys were not batched"
        )
    emulator = TerminalEmulator(COLS, ROWS, 1000)
    emulator.feed(data)
    numbers = []
    for text in emulator.screen_lines_text()[BODY_ROWS.start : BODY_ROWS.stop]:
        match = re.match(r"baris (\d{3}) ", text)
        numbers.append(int(match.group(1)) if match else None)
    if None in numbers or any(b - a != 1 for a, b in pairwise(numbers)):
        problems.append(f"screen lines are not consecutive: {numbers}")
    return problems


def main(argv: list[str] | None = None) -> int:
    """Record every scenario into ``--out`` and verify the result."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="target folder")
    args = parser.parse_args(argv)
    if not sys.platform.startswith("linux"):
        sys.stderr.write("record_nano_scroll.py only works on Linux\n")
        return 2
    if shutil.which("nano") is None:
        sys.stderr.write("nano was not found in PATH\n")
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    failed = False
    with tempfile.TemporaryDirectory(prefix="pyssh-nano-") as tmp:
        workdir = Path(tmp)
        (workdir / FILE_NAME).write_text(make_text(), encoding="utf-8")
        for scenario in SCENARIOS:
            data = record(scenario, workdir)
            target = args.out / f"{scenario.name}.bin"
            target.write_bytes(data)
            problems = check(scenario, data, workdir)
            failed = failed or bool(problems)
            status = "OK" if not problems else "PROBLEM"
            sys.stdout.write(f"{target} ({len(data)} bytes): {status}\n")
            for problem in problems:
                sys.stdout.write(f"  - {problem}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
