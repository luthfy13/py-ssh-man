"""Status dot icons drawn with QPainter (SPEC §9.6.1)."""

from __future__ import annotations

from functools import cache

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

YELLOW = "#E5B800"
GREEN = "#16C60C"
RED = "#E74856"
GRAY = "#8A8A8A"
SIZE = 16


@cache
def dot_icon(color: str, size: int = SIZE) -> QIcon:
    """A filled circle on a transparent background."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    margin = size * 0.2
    painter.drawEllipse(QRectF(margin, margin, size - 2 * margin, size - 2 * margin))
    painter.end()
    return QIcon(pixmap)
