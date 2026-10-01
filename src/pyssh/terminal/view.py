"""``TerminalView``: terminal widget combined with a scrollbar (SPEC §8.5)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QScrollBar, QWidget

from pyssh.models import AppSettings
from pyssh.terminal.colors import Theme
from pyssh.terminal.widget import TerminalWidget


class TerminalView(QWidget):
    """``TerminalWidget`` with a vertical scrollbar for the scrollback."""

    def __init__(
        self, settings: AppSettings, theme: Theme | None = None, parent: QWidget | None = None
    ) -> None:
        """Lay out the terminal (stretching) and the scrollbar."""
        super().__init__(parent)
        self.terminal = TerminalWidget(settings, theme, self)
        self.scrollbar = QScrollBar(Qt.Orientation.Vertical, self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.terminal, 1)
        layout.addWidget(self.scrollbar)
        self.setFocusProxy(self.terminal)
        self.terminal.scroll_state_changed.connect(self._on_scroll_state)
        self.scrollbar.valueChanged.connect(self.terminal.set_scroll_value)
        self._on_scroll_state(0, 0, self.terminal.grid_size()[1])

    def _on_scroll_state(self, value: int, maximum: int, page_step: int) -> None:
        bar = self.scrollbar
        bar.blockSignals(True)
        try:
            bar.setRange(0, maximum)
            bar.setPageStep(page_step)
            bar.setValue(value)
        finally:
            bar.blockSignals(False)
