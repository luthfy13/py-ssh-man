"""Benchmark ``TerminalEmulator`` throughput (SPEC §11.6 task 3.9).

Feeds 5 MB of ASCII text into a 120×40 emulator and prints MB/s.
Run: ``python tools/bench_emulator.py``.
"""

from __future__ import annotations

import sys
import time

from pyssh.terminal.emulator import TerminalEmulator

TOTAL_BYTES = 5 * 1000 * 1000
CHUNK = 16 * 1024


def build_payload(total: int = TOTAL_BYTES) -> bytes:
    """ASCII lines similar to ``seq``/log output, ``total`` bytes long."""
    lines = []
    size = 0
    n = 0
    while size < total:
        line = f"{n:>8} the quick brown fox jumps over the lazy dog {n * 7919 % 100000}\r\n"
        lines.append(line)
        size += len(line)
        n += 1
    return "".join(lines).encode("ascii")[:total]


def run(payload: bytes) -> float:
    """Feed the payload in 16 KiB chunks; return seconds."""
    emulator = TerminalEmulator(120, 40, 5000)
    started = time.perf_counter()
    for offset in range(0, len(payload), CHUNK):
        emulator.feed(payload[offset : offset + CHUNK])
    return time.perf_counter() - started


def main() -> int:
    """Run the benchmark and print the throughput."""
    payload = build_payload()
    seconds = run(payload)
    mb = len(payload) / 1_000_000
    sys.stdout.write(f"fed {mb:.1f} MB in {seconds:.2f} s -> {mb / seconds:.3f} MB/s\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
