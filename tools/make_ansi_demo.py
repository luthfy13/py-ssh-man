"""Generate the demo files ``ansi_demo.txt`` (Indonesian) and ``ansi_demo_en.txt`` (SPEC §8.6).

Run: ``python tools/make_ansi_demo.py``. Lines are separated with ``\\n``; the demo backend
converts them to CR LF when displaying and picks the file of the active UI language.
"""

from __future__ import annotations

import sys
from pathlib import Path

RESOURCES = Path(__file__).resolve().parent.parent / "src" / "pyssh" / "resources"
OUTPUTS = {"id": RESOURCES / "ansi_demo.txt", "en": RESOURCES / "ansi_demo_en.txt"}
ESC = "\x1b"
RESET = f"{ESC}[0m"
NAMES = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]


def _sgr(*codes: int) -> str:
    return f"{ESC}[" + ";".join(str(c) for c in codes) + "m"


LIGHT_BACKGROUNDS = {3, 6, 7, 10, 11, 14, 15}


def _label_fg(index: int) -> int:
    """Black text on light background samples, bright white on dark ones."""
    return 30 if index in LIGHT_BACKGROUNDS else 97


# Both languages keep the Indonesian sample line: SPEC §8.6 requires Indonesian text in the demo.
LABELS = {
    "id": {
        "title": "Demo terminal",
        "fg": "16 warna latar depan (normal / terang):",
        "bg": "16 warna latar belakang (normal / terang):",
        "grid": "Grid 256 warna:",
        "gradient": "Gradasi truecolor:",
        "attributes": "Atribut teks:",
        "attribute_names": ("tebal", "miring", "garis bawah", "terbalik", "coret", "tebal merah"),
        "box": "Box drawing:",
        "sample": "Bahasa Indonesia:",
        "wide": "Karakter lebar: 漢字 (setiap karakter 2 kolom) |漢字|",
        "long": "Baris panjang yang di-wrap:",
        "word": "kata",
    },
    "en": {
        "title": "Terminal demo",
        "fg": "16 foreground colors (normal / bright):",
        "bg": "16 background colors (normal / bright):",
        "grid": "256-color grid:",
        "gradient": "Truecolor gradient:",
        "attributes": "Text attributes:",
        "attribute_names": ("bold", "italic", "underline", "reverse", "strikethrough", "bold red"),
        "box": "Box drawing:",
        "sample": "Indonesian sample:",
        "wide": "Wide characters: 漢字 (each character is 2 columns) |漢字|",
        "long": "Long wrapped line:",
        "word": "word",
    },
}
INDONESIAN_SAMPLE = "Selamat datang! Koneksi SSH siap dipakai, Bapak/Ibu."


def build_demo(language: str = "id") -> str:
    """Return the demo text with labels in ``language`` ("id" or "en")."""
    label = LABELS[language]
    lines: list[str] = [f"{_sgr(1)}{label['title']}{RESET}", ""]

    lines.append(label["fg"])
    lines.append(" ".join(f"{_sgr(30 + i)}{NAMES[i]:<7}{RESET}" for i in range(8)))
    lines.append(" ".join(f"{_sgr(90 + i)}{NAMES[i]:<7}{RESET}" for i in range(8)))
    lines.append(label["bg"])
    lines.append("".join(f"{_sgr(40 + i, _label_fg(i))}  {i:<2}  {RESET}" for i in range(8)))
    lines.append(
        "".join(f"{_sgr(100 + i, _label_fg(i + 8))}  {i + 8:<2}  {RESET}" for i in range(8))
    )
    lines.append("")

    lines.append(label["grid"])
    lines.append("".join(f"{ESC}[48;5;{i}m  " for i in range(16)) + RESET)
    for row in range(6):
        cells = []
        for col in range(36):
            index = 16 + row * 36 + col
            cells.append(f"{ESC}[48;5;{index}m ")
        lines.append("".join(cells) + RESET)
    lines.append("".join(f"{ESC}[48;5;{i}m  " for i in range(232, 256)) + RESET)
    lines.append("")

    lines.append(label["gradient"])
    gradient = []
    for i in range(72):
        r = int(255 * i / 71)
        g = int(255 * (1 - abs(i - 36) / 36))
        b = 255 - r
        gradient.append(f"{ESC}[48;2;{r};{g};{b}m ")
    lines.append("".join(gradient) + RESET)
    lines.append("")

    lines.append(label["attributes"])
    styles = ((1,), (3,), (4,), (7,), (9,), (1, 31))
    names = label["attribute_names"]
    lines.append(
        "  ".join(f"{_sgr(*codes)}{name}{RESET}" for codes, name in zip(styles, names, strict=True))
    )
    lines.append("")

    lines.append(label["box"])
    lines.append("┌─────┬─────┐")
    lines.append("│ abc │ def │")
    lines.append("├─────┼─────┤")
    lines.append("│ 123 │ 456 │")
    lines.append("└─────┴─────┘")
    lines.append("")

    lines.append(f"{label['sample']} {INDONESIAN_SAMPLE}")
    lines.append(label["wide"])
    lines.append("")
    lines.append(label["long"] + " " + " ".join(f"{label['word']}{i:02d}" for i in range(40)))
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    """Write the demo file of every language."""
    for language, output in OUTPUTS.items():
        output.write_text(build_demo(language), encoding="utf-8", newline="\n")
        sys.stdout.write(f"wrote {output}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
