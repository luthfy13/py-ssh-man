"""Generate ``src/pyssh/resources/ansi_demo.txt`` (SPEC §8.6).

Run: ``python tools/make_ansi_demo.py``. Lines are separated with ``\\n``; the demo backend
converts them to CR LF when displaying.
"""

from __future__ import annotations

import sys
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent.parent / "src" / "pyssh" / "resources" / "ansi_demo.txt"
ESC = "\x1b"
RESET = f"{ESC}[0m"
NAMES = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]


def _sgr(*codes: int) -> str:
    return f"{ESC}[" + ";".join(str(c) for c in codes) + "m"


LIGHT_BACKGROUNDS = {3, 6, 7, 10, 11, 14, 15}


def _label_fg(index: int) -> int:
    """Black text on light background samples, bright white on dark ones."""
    return 30 if index in LIGHT_BACKGROUNDS else 97


def build_demo() -> str:
    """Return the demo text."""
    lines: list[str] = [f"{_sgr(1)}Demo terminal{RESET}", ""]

    lines.append("16 warna latar depan (normal / terang):")
    lines.append(" ".join(f"{_sgr(30 + i)}{NAMES[i]:<7}{RESET}" for i in range(8)))
    lines.append(" ".join(f"{_sgr(90 + i)}{NAMES[i]:<7}{RESET}" for i in range(8)))
    lines.append("16 warna latar belakang (normal / terang):")
    lines.append("".join(f"{_sgr(40 + i, _label_fg(i))}  {i:<2}  {RESET}" for i in range(8)))
    lines.append(
        "".join(f"{_sgr(100 + i, _label_fg(i + 8))}  {i + 8:<2}  {RESET}" for i in range(8))
    )
    lines.append("")

    lines.append("Grid 256 warna:")
    lines.append("".join(f"{ESC}[48;5;{i}m  " for i in range(16)) + RESET)
    for row in range(6):
        cells = []
        for col in range(36):
            index = 16 + row * 36 + col
            cells.append(f"{ESC}[48;5;{index}m ")
        lines.append("".join(cells) + RESET)
    lines.append("".join(f"{ESC}[48;5;{i}m  " for i in range(232, 256)) + RESET)
    lines.append("")

    lines.append("Gradasi truecolor:")
    gradient = []
    for i in range(72):
        r = int(255 * i / 71)
        g = int(255 * (1 - abs(i - 36) / 36))
        b = 255 - r
        gradient.append(f"{ESC}[48;2;{r};{g};{b}m ")
    lines.append("".join(gradient) + RESET)
    lines.append("")

    lines.append("Atribut teks:")
    lines.append(
        f"{_sgr(1)}tebal{RESET}  {_sgr(3)}miring{RESET}  {_sgr(4)}garis bawah{RESET}  "
        f"{_sgr(7)}terbalik{RESET}  {_sgr(9)}coret{RESET}  {_sgr(1, 31)}tebal merah{RESET}"
    )
    lines.append("")

    lines.append("Box drawing:")
    lines.append("┌─────┬─────┐")
    lines.append("│ abc │ def │")
    lines.append("├─────┼─────┤")
    lines.append("│ 123 │ 456 │")
    lines.append("└─────┴─────┘")
    lines.append("")

    lines.append("Bahasa Indonesia: Selamat datang! Koneksi SSH siap dipakai, Bapak/Ibu.")
    lines.append("Karakter lebar: 漢字 (setiap karakter 2 kolom) |漢字|")
    lines.append("")
    lines.append("Baris panjang yang di-wrap: " + " ".join(f"kata{i:02d}" for i in range(40)))
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    """Write the demo file."""
    OUTPUT.write_text(build_demo(), encoding="utf-8", newline="\n")
    sys.stdout.write(f"wrote {OUTPUT}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
