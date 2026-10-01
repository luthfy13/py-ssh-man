"""Main application window (SPEC §9.1)."""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QWidget

from pyssh import config

INITIAL_WIDTH = 1200
INITIAL_HEIGHT = 750


class MainWindow(QMainWindow):
    """Top-level window; currently an empty shell (Phase 0)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the window with the application title and initial size."""
        super().__init__(parent)
        self.setWindowTitle(config.APP_NAME)
        self.resize(INITIAL_WIDTH, INITIAL_HEIGHT)
