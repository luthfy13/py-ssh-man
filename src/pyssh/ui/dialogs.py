"""Password, host key and confirmation dialogs (SPEC §9.7), plus small UI helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication


@contextmanager
def wait_cursor() -> Iterator[None]:
    """Show the wait cursor while a slow GUI-thread operation runs (rule A1 exception)."""
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        yield
    finally:
        QApplication.restoreOverrideCursor()
