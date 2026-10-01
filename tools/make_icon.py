"""Generate ``src/pyssh/resources/icon.png`` with QPainter (SPEC §11.11, task 8.5).

Run: ``python tools/make_icon.py`` (uses the offscreen platform when no display is set).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

if sys.platform.startswith("linux") and not (
    os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPen

OUTPUT = Path(__file__).resolve().parent.parent / "src" / "pyssh" / "resources" / "icon.png"
SIZE = 256


def draw_icon(size: int = SIZE) -> QImage:
    """Dark rounded square with a green ">_" prompt."""
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    margin = size * 0.06
    rect = QRectF(margin, margin, size - 2 * margin, size - 2 * margin)
    painter.setPen(QPen(QColor("#3A96DD"), size * 0.03))
    painter.setBrush(QColor("#0C0C0C"))
    painter.drawRoundedRect(rect, size * 0.16, size * 0.16)
    font = QFont("DejaVu Sans Mono")
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setBold(True)
    font.setPixelSize(int(size * 0.42))
    painter.setFont(font)
    painter.setPen(QColor("#16C60C"))
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, ">_")
    painter.end()
    return image


def main() -> int:
    """Write the icon file."""
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    if not draw_icon().save(str(OUTPUT)):
        sys.stderr.write(f"could not write {OUTPUT}\n")
        return 1
    sys.stdout.write(f"wrote {OUTPUT}\n")
    del app
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
