"""``TerminalWidget``: rendering, input, selection and clipboard (SPEC §8.4)."""

from __future__ import annotations

import logging
import math
import os
import time
from collections.abc import Iterable
from dataclasses import dataclass, field

from PySide6.QtCore import QEvent, QPointF, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QContextMenuEvent,
    QFocusEvent,
    QFont,
    QFontDatabase,
    QFontMetricsF,
    QGuiApplication,
    QInputMethodEvent,
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QResizeEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import QMenu, QWidget

from pyssh import config, shortcuts, strings
from pyssh.models import AppSettings
from pyssh.terminal.colors import Theme, resolve_color
from pyssh.terminal.emulator import TerminalEmulator
from pyssh.terminal.keymap import key_to_bytes

log = logging.getLogger(__name__)

PADDING = 4
MIN_COLS = 20
MIN_ROWS = 5
FONT_MIN = 6
FONT_MAX = 32
PUMP_CHUNK = 16 * 1024
PUMP_BUDGET_S = 0.008
REPAINT_INTERVAL_MS = 16
RESIZE_DEBOUNCE_MS = 120
BACKPRESSURE_HIGH = 4 * 1024 * 1024
BACKPRESSURE_LOW = 1024 * 1024
WHEEL_NOTCH = 120
WHEEL_LINES_PER_NOTCH = 3
PERF_TICK_MS = 100
PERF_REPORT_S = 5.0
WORD_SEPARATORS = frozenset(" \t\"'()[]{}<>;,|")

FONT_FALLBACKS = {
    "windows": ["Cascadia Mono", "Consolas", "Courier New"],
    "mac": ["Menlo", "SF Mono", "Monaco"],
    "linux": ["DejaVu Sans Mono", "Noto Sans Mono", "Liberation Mono", "Ubuntu Mono"],
}

_LOCAL_COLORS = {"red": 31, "green": 32, "yellow": 33, "blue": 34, "magenta": 35, "cyan": 36}


def default_font_families(
    *, windows: bool = config.IS_WINDOWS, mac: bool = config.IS_MAC
) -> list[str]:
    """Platform font preference list (SPEC §8.4.2)."""
    if windows:
        return list(FONT_FALLBACKS["windows"])
    if mac:
        return list(FONT_FALLBACKS["mac"])
    return list(FONT_FALLBACKS["linux"])


def pick_font_family(
    preferred: str,
    available: Iterable[str],
    *,
    windows: bool = config.IS_WINDOWS,
    mac: bool = config.IS_MAC,
) -> str | None:
    """First available family: the configured one, then the platform list; else ``None``."""
    families = set(available)
    candidates = ([preferred] if preferred else []) + default_font_families(
        windows=windows, mac=mac
    )
    for name in candidates:
        if name in families:
            return name
    return None


def make_font(preferred: str, size: int) -> QFont:
    """Monospace font for the terminal; system fixed font as the last fallback."""
    family = pick_font_family(preferred, QFontDatabase.families())
    if family is not None:
        font = QFont(family)
    else:
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setPointSize(size)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setFixedPitch(True)
    font.setKerning(False)
    return font


@dataclass
class _Run:
    """Consecutive cells with an identical style."""

    start: int
    end: int
    style: tuple
    cells: list[tuple[int, str, int]] = field(default_factory=list)  # (col, text, width)


class TerminalWidget(QWidget):
    """Draws a ``TerminalEmulator`` and turns user input into bytes for the backend."""

    input_bytes = Signal(bytes)
    grid_size_changed = Signal(int, int)
    backpressure = Signal(bool)
    title_changed = Signal(str)
    scroll_state_changed = Signal(int, int, int)
    reconnect_requested = Signal()
    font_size_changed = Signal(int)

    def __init__(
        self, settings: AppSettings, theme: Theme | None = None, parent: QWidget | None = None
    ) -> None:
        """Create the widget and its emulator (80×24 until the first layout)."""
        super().__init__(parent)
        self._settings = settings
        self._theme = theme or Theme()
        self._font_size = settings.font_size
        self._emulator = TerminalEmulator(
            80, 24, settings.scrollback_lines, on_response=self._on_emulator_response
        )
        self._pending = bytearray()
        self._pump_scheduled = False
        self._paused = False
        self._view_offset = 0
        self._scrolled_seen = 0
        self._input_enabled = True
        self._sel_anchor: tuple[int, int] | None = None
        self._sel_end: tuple[int, int] | None = None
        self._dragging = False
        self._wheel_acc = 0.0
        self._pixel_acc = 0.0
        self._title = ""
        self._colors: dict[str, QColor] = {}
        self._fonts: dict[tuple[bool, bool], QFont] = {}
        self._cell_w = 1.0
        self._cell_h = 1.0
        self._ascent = 1.0

        self._repaint_timer = QTimer(self)
        self._repaint_timer.setSingleShot(True)
        self._repaint_timer.setInterval(REPAINT_INTERVAL_MS)
        self._repaint_timer.timeout.connect(self.update)
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(RESIZE_DEBOUNCE_MS)
        self._resize_timer.timeout.connect(self._emit_grid_size)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setCursor(Qt.CursorShape.IBeamCursor)
        self._apply_font()

        self._perf_enabled = os.environ.get("PYSSH_DEBUG_PERF") == "1"
        self._perf_bytes = 0
        if self._perf_enabled:
            self._start_perf_monitor()

    # ----- public API -------------------------------------------------------------------

    @property
    def emulator(self) -> TerminalEmulator:
        """The emulator (GUI thread only)."""
        return self._emulator

    @property
    def view_offset(self) -> int:
        """Lines scrolled up from the bottom (0 = live view)."""
        return self._view_offset

    @property
    def input_enabled(self) -> bool:
        """Whether key presses are sent to the backend."""
        return self._input_enabled

    @property
    def font_size(self) -> int:
        """Current (possibly zoomed) font size in points."""
        return self._font_size

    @property
    def cell_size(self) -> tuple[float, float]:
        """Cell width and height in pixels."""
        return self._cell_w, self._cell_h

    @property
    def backpressure_active(self) -> bool:
        """True while the backend was asked to pause."""
        return self._paused

    def feed(self, data: bytes) -> None:
        """Queue output bytes; they are processed in time-boxed chunks (SPEC §8.4.3)."""
        if not data:
            return
        self._pending += data
        self._check_backpressure()
        if not self._pump_scheduled:
            self._pump_scheduled = True
            QTimer.singleShot(0, self, self._pump)

    def flush_pending(self) -> None:
        """Process all queued bytes now (used by tests)."""
        self._process(budget=None)
        self.update()

    def write_local(self, text: str, color: str | None = None) -> None:
        """Show a local status message; it is never sent to the server."""
        code = _LOCAL_COLORS.get(color or "")
        start = f"\x1b[{code}m" if code else ""
        self.feed(("\r\n" + start + text + "\x1b[0m\r\n").encode("utf-8"))

    def grid_size(self) -> tuple[int, int]:
        """Current ``(cols, rows)``."""
        return self._emulator.cols, self._emulator.rows

    def set_input_enabled(self, enabled: bool) -> None:
        """Enable or disable sending keys (disabled: R/Enter request a reconnect)."""
        self._input_enabled = enabled

    def set_scroll_value(self, value: int) -> None:
        """Scrollbar position: ``maximum`` (= history length) is the bottom."""
        offset = self._emulator.history_len - value
        self._set_view_offset(offset)

    def scroll_by(self, lines: int) -> None:
        """Scroll ``lines`` up (positive) or down (negative)."""
        self._set_view_offset(self._view_offset + lines)

    def scroll_to_bottom(self) -> None:
        """Return to the live view."""
        self._set_view_offset(0)

    def has_selection(self) -> bool:
        """True when a non-empty selection exists."""
        return self.selection_range() is not None

    def selection_range(self) -> tuple[tuple[int, int], tuple[int, int]] | None:
        """Ordered ``(start, end)`` of the selection, or ``None`` when empty."""
        if self._sel_anchor is None or self._sel_end is None or self._sel_anchor == self._sel_end:
            return None
        return min(self._sel_anchor, self._sel_end), max(self._sel_anchor, self._sel_end)

    def selected_text(self) -> str:
        """Text of the selection ("" when empty)."""
        selection = self.selection_range()
        if selection is None:
            return ""
        return self._emulator.text_between(*selection)

    def set_selection(self, start: tuple[int, int], end: tuple[int, int]) -> None:
        """Select from ``start`` to ``end`` as ``(line_index, col)`` boundaries."""
        self._sel_anchor, self._sel_end = start, end
        self.update()

    def clear_selection(self) -> None:
        """Remove the selection."""
        if self._sel_anchor is not None or self._sel_end is not None:
            self._sel_anchor = self._sel_end = None
            self.update()

    def copy_selection(self) -> bool:
        """Copy the selection to the clipboard; ``False`` when there is nothing to copy."""
        text = self.selected_text()
        if not text:
            return False
        QGuiApplication.clipboard().setText(text)
        return True

    def paste_clipboard(self) -> None:
        """Send clipboard text, using bracketed paste when the application enabled it."""
        if not self._input_enabled:
            return
        text = QGuiApplication.clipboard().text()
        if not text:
            return
        text = text.replace("\r\n", "\r").replace("\n", "\r")
        if self._emulator.bracketed_paste:
            text = "\x1b[200~" + text.replace("\x1b[201~", "") + "\x1b[201~"
        self.scroll_to_bottom()
        self.input_bytes.emit(text.encode("utf-8"))

    def clear_scrollback(self) -> None:
        """Forget the scrollback history."""
        self._emulator.clear_scrollback()
        self._scrolled_seen = self._emulator.scrolled_total
        self._view_offset = 0
        self.clear_selection()
        self._emit_scroll_state()
        self.update()

    def zoom_in(self) -> None:
        """Increase the font size by one point (max 32)."""
        self._set_font_size(self._font_size + 1)

    def zoom_out(self) -> None:
        """Decrease the font size by one point (min 6)."""
        self._set_font_size(self._font_size - 1)

    def zoom_reset(self) -> None:
        """Return to the configured font size."""
        self._set_font_size(self._settings.font_size)

    def apply_settings(self, settings: AppSettings) -> None:
        """Apply new settings; font changes apply now, scrollback only to new tabs."""
        self._settings = settings
        self._colors.clear()
        old_size = self._font_size
        self._font_size = _clamp(settings.font_size, FONT_MIN, FONT_MAX)
        self._apply_font()
        if self._font_size != old_size:
            self.font_size_changed.emit(self._font_size)
        self.update()

    def context_menu(self) -> QMenu:
        """Build the right-click menu (exposed for tests)."""
        menu = QMenu(self)
        copy_action = menu.addAction(strings.TERMINAL_COPY, self.copy_selection)
        copy_action.setEnabled(self.has_selection())
        paste_action = menu.addAction(strings.TERMINAL_PASTE, self.paste_clipboard)
        paste_action.setEnabled(self._input_enabled)
        for action, name in ((copy_action, "copy"), (paste_action, "paste")):
            sequences = shortcuts.sequences_for(name)
            if sequences:
                action.setShortcut(QKeySequence(sequences[0]))
        menu.addSeparator()
        menu.addAction(strings.TERMINAL_CLEAR_SCROLLBACK, self.clear_scrollback)
        return menu

    def sizeHint(self) -> QSize:
        """Room for 80×24 cells."""
        return QSize(
            math.ceil(80 * self._cell_w + 2 * PADDING), math.ceil(24 * self._cell_h + 2 * PADDING)
        )

    # ----- data pump --------------------------------------------------------------------

    def _on_emulator_response(self, data: bytes) -> None:
        self.input_bytes.emit(data)

    def _pump(self) -> None:
        self._pump_scheduled = False
        self._process(budget=PUMP_BUDGET_S)
        if self._pending and not self._pump_scheduled:
            self._pump_scheduled = True
            QTimer.singleShot(0, self, self._pump)

    def _process(self, budget: float | None) -> None:
        if not self._pending:
            return
        started = time.perf_counter()
        processed = 0
        while self._pending:
            chunk = bytes(self._pending[:PUMP_CHUNK])
            del self._pending[:PUMP_CHUNK]
            self._emulator.feed(chunk)
            processed += len(chunk)
            if budget is not None and time.perf_counter() - started >= budget:
                break
        self._after_feed(processed)

    def _after_feed(self, processed: int) -> None:
        self._perf_bytes += processed
        scrolled = self._emulator.scrolled_total
        added = scrolled - self._scrolled_seen
        self._scrolled_seen = scrolled
        if self._view_offset > 0 and added > 0:
            # Keep the scrolled-up view on the same content (SPEC §8.4.3, SHOULD).
            self._view_offset = min(self._view_offset + added, self._emulator.history_len)
        if processed:
            self._sel_anchor = self._sel_end = None
        if not self._repaint_timer.isActive():
            self._repaint_timer.start()
        self._emit_scroll_state()
        title = self._emulator.title
        if title != self._title:
            self._title = title
            self.title_changed.emit(title)
        self._check_backpressure()

    def _check_backpressure(self) -> None:
        pending = len(self._pending)
        if not self._paused and pending > BACKPRESSURE_HIGH:
            self._paused = True
            self.backpressure.emit(True)
        elif self._paused and pending < BACKPRESSURE_LOW:
            self._paused = False
            self.backpressure.emit(False)

    # ----- geometry, fonts, scrolling ---------------------------------------------------

    def _apply_font(self) -> None:
        base = make_font(self._settings.font_family, self._font_size)
        self._fonts = {}
        for bold in (False, True):
            for italic in (False, True):
                font = QFont(base)
                font.setBold(bold)
                font.setItalic(italic)
                self._fonts[(bold, italic)] = font
        metrics = QFontMetricsF(base)
        self._cell_w = max(metrics.horizontalAdvance("M"), 1.0)
        self._cell_h = max(metrics.lineSpacing(), 1.0)
        self._ascent = metrics.ascent()
        self.setFont(base)
        self._update_grid()
        self.update()

    def _set_font_size(self, size: int) -> None:
        size = _clamp(size, FONT_MIN, FONT_MAX)
        if size == self._font_size:
            return
        self._font_size = size
        self._apply_font()
        self.font_size_changed.emit(size)

    def _compute_grid(self) -> tuple[int, int]:
        cols = max(MIN_COLS, int((self.width() - 2 * PADDING) // self._cell_w))
        rows = max(MIN_ROWS, int((self.height() - 2 * PADDING) // self._cell_h))
        return cols, rows

    def _update_grid(self) -> None:
        cols, rows = self._compute_grid()
        if (cols, rows) == self.grid_size():
            return
        self._emulator.resize(cols, rows)
        self._view_offset = min(self._view_offset, self._emulator.history_len)
        self._emit_scroll_state()
        self.update()
        self._resize_timer.start()

    def _emit_grid_size(self) -> None:
        self.grid_size_changed.emit(*self.grid_size())

    def _set_view_offset(self, offset: int) -> None:
        offset = _clamp(offset, 0, self._emulator.history_len)
        if offset != self._view_offset:
            self._view_offset = offset
            self.update()
        self._emit_scroll_state()

    def _emit_scroll_state(self) -> None:
        maximum = self._emulator.history_len
        self.scroll_state_changed.emit(maximum - self._view_offset, maximum, self._emulator.rows)

    def _boundary_at(self, pos: QPointF) -> tuple[int, int]:
        """Selection boundary (line_index, col 0..cols) nearest to a point."""
        row = _clamp(int((pos.y() - PADDING) // self._cell_h), 0, self._emulator.rows - 1)
        col = _clamp(round((pos.x() - PADDING) / self._cell_w), 0, self._emulator.cols)
        return self._emulator.visible_range(self._view_offset)[row], col

    def _cell_at(self, pos: QPointF) -> tuple[int, int]:
        """Cell (line_index, col 0..cols-1) under a point."""
        row = _clamp(int((pos.y() - PADDING) // self._cell_h), 0, self._emulator.rows - 1)
        col = _clamp(int((pos.x() - PADDING) // self._cell_w), 0, self._emulator.cols - 1)
        return self._emulator.visible_range(self._view_offset)[row], col

    def _word_bounds(self, line_index: int, col: int) -> tuple[int, int]:
        line = self._emulator.line_at(line_index)
        cols = self._emulator.cols
        while col > 0 and line[col].data == "":  # stub of a wide character
            col -= 1

        def is_word(x: int) -> bool:
            data = line[x].data
            return data == "" or data not in WORD_SEPARATORS

        if not is_word(col):
            return col, col + 1
        start, end = col, col + 1
        while start > 0 and is_word(start - 1):
            start -= 1
        while end < cols and is_word(end):
            end += 1
        return start, end

    # ----- Qt events --------------------------------------------------------------------

    def event(self, event: QEvent) -> bool:
        """Keep Ctrl+letter etc. away from menu shortcuts unless they are app shortcuts."""
        if event.type() == QEvent.Type.ShortcutOverride:
            assert isinstance(event, QKeyEvent)
            if shortcuts.is_app_shortcut(event.key(), event.modifiers()):
                event.ignore()
            else:
                event.accept()
            return True
        return super().event(event)

    def focusNextPrevChild(self, next: bool) -> bool:
        """Tab and Shift+Tab belong to the terminal."""
        return False

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Translate a key press (SPEC §8.4.5)."""
        key, mods = event.key(), event.modifiers()
        if not self._input_enabled:
            reconnect_keys = (int(Qt.Key.Key_R), int(Qt.Key.Key_Return), int(Qt.Key.Key_Enter))
            no_mods = shortcuts.normalize_mods(mods) == Qt.KeyboardModifier.NoModifier
            if no_mods and key in reconnect_keys:
                self.reconnect_requested.emit()
            event.accept()
            return
        found = shortcuts.match(key, mods)
        if found is not None and found.handled_by == "widget":
            if found.action == "copy":
                self.copy_selection()
            elif found.action == "paste":
                self.paste_clipboard()
            elif found.action == "scroll_page_up":
                self.scroll_by(self._emulator.rows)
            elif found.action == "scroll_page_down":
                self.scroll_by(-self._emulator.rows)
            event.accept()
            return
        data = key_to_bytes(
            key,
            mods,
            event.text(),
            app_cursor=self._emulator.app_cursor_keys,
            mac_option_as_meta=self._settings.mac_option_as_meta,
        )
        if data is None:
            super().keyPressEvent(event)
            return
        self.scroll_to_bottom()
        self.clear_selection()
        self.input_bytes.emit(data)
        event.accept()

    def inputMethodEvent(self, event: QInputMethodEvent) -> None:
        """Send text committed by an input method."""
        text = event.commitString()
        if text and self._input_enabled:
            self.scroll_to_bottom()
            self.input_bytes.emit(text.encode("utf-8"))
        event.accept()

    def inputMethodQuery(self, query: Qt.InputMethodQuery):
        """Tell input methods where the cursor is."""
        if query == Qt.InputMethodQuery.ImCursorRectangle:
            return self._cursor_rect().toRect()
        return super().inputMethodQuery(query)

    def focusInEvent(self, event: QFocusEvent) -> None:
        """Redraw the cursor as a filled block."""
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event: QFocusEvent) -> None:
        """Redraw the cursor as an outline."""
        super().focusOutEvent(event)
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Start a selection."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            boundary = self._boundary_at(event.position())
            self._sel_anchor = self._sel_end = boundary
            self._dragging = True
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Extend the selection while dragging."""
        if self._dragging:
            self._sel_end = self._boundary_at(event.position())
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Finish the selection; copy it when ``copy_on_select`` is on."""
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            if self.has_selection():
                if self._settings.copy_on_select:
                    self.copy_selection()
            else:
                self.clear_selection()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Select the word under the pointer."""
        if event.button() == Qt.MouseButton.LeftButton:
            line_index, col = self._cell_at(event.position())
            start, end = self._word_bounds(line_index, col)
            self._dragging = False
            self.set_selection((line_index, start), (line_index, end))
            if self._settings.copy_on_select:
                self.copy_selection()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """Show copy/paste/clear-scrollback."""
        self.context_menu().exec(event.globalPos())

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Scroll 3 lines per notch; with Ctrl (Cmd on macOS) change the font size."""
        mods = shortcuts.normalize_mods(event.modifiers())
        if mods & shortcuts.zoom_wheel_modifier():
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            elif delta < 0:
                self.zoom_out()
            event.accept()
            return
        pixel = event.pixelDelta()
        if not pixel.isNull():
            self._pixel_acc += pixel.y()
            lines = int(self._pixel_acc / self._cell_h)
            self._pixel_acc -= lines * self._cell_h
        else:
            step = WHEEL_NOTCH / WHEEL_LINES_PER_NOTCH
            self._wheel_acc += event.angleDelta().y()
            lines = int(self._wheel_acc / step)
            self._wheel_acc -= lines * step
        if lines:
            self.scroll_by(lines)
        event.accept()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Recompute the grid; the new size is announced after 120 ms."""
        super().resizeEvent(event)
        self._update_grid()

    # ----- painting ---------------------------------------------------------------------

    def _color(self, value: str) -> QColor:
        color = self._colors.get(value)
        if color is None:
            color = QColor(value)
            self._colors[value] = color
        return color

    def _style(self, char, selected: bool) -> tuple:
        theme = self._theme
        bright = self._settings.bold_is_bright
        fg = resolve_color(char.fg, is_fg=True, bold=char.bold, theme=theme, bold_is_bright=bright)
        bg = resolve_color(char.bg, is_fg=False, bold=char.bold, theme=theme, bold_is_bright=bright)
        if char.reverse:
            fg, bg = bg, fg
        if selected:
            bg = theme.selection
        return fg, bg, char.bold, char.italics, char.underscore, char.strikethrough

    def _runs(self, line_index: int, selection) -> list[_Run]:
        line = self._emulator.line_at(line_index)
        cols = self._emulator.cols
        runs: list[_Run] = []
        x = 0
        while x < cols:
            char = line[x]
            if char.data == "":
                x += 1
                continue
            width = 2 if x + 1 < cols and line[x + 1].data == "" else 1
            selected = selection is not None and selection[0] <= (line_index, x) < selection[1]
            style = self._style(char, selected)
            if runs and runs[-1].style == style and runs[-1].end == x:
                run = runs[-1]
            else:
                run = _Run(start=x, end=x, style=style)
                runs.append(run)
            run.cells.append((x, char.data, width))
            run.end = x + width
            x += width
        return runs

    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw background, text runs, decorations and the cursor (SPEC §8.4.4)."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._color(self._theme.background))
        selection = self.selection_range()
        for row, line_index in enumerate(self._emulator.visible_range(self._view_offset)):
            if 0 <= line_index < self._emulator.total_lines:
                y = PADDING + row * self._cell_h
                for run in self._runs(line_index, selection):
                    self._paint_run(painter, run, y)
        self._paint_cursor(painter)
        painter.end()

    def _paint_run(self, painter: QPainter, run: _Run, y: float) -> None:
        fg, bg, bold, italics, underscore, strike = run.style
        cw, ch = self._cell_w, self._cell_h
        x0 = PADDING + run.start * cw
        x1 = PADDING + run.end * cw
        if bg != self._theme.background:
            left = math.floor(x0)
            painter.fillRect(
                QRect(left, math.floor(y), math.ceil(x1) - left, math.ceil(ch)), self._color(bg)
            )
        text = "".join(data for _col, data, _w in run.cells)
        if not text.strip() and not underscore and not strike:
            return
        fg_color = self._color(fg)
        painter.setPen(fg_color)
        painter.setFont(self._fonts[(bold, italics)])
        baseline = y + self._ascent
        if text.isascii() and all(width == 1 for _c, _d, width in run.cells):
            painter.drawText(QPointF(x0, baseline), text)
        else:
            for col, data, _width in run.cells:
                if data.strip():
                    painter.drawText(QPointF(PADDING + col * cw, baseline), data)
        if underscore or strike:
            painter.setPen(QPen(fg_color, 1))
            if underscore:
                uy = min(baseline + 1, y + ch - 1)
                painter.drawLine(QPointF(x0, uy), QPointF(x1, uy))
            if strike:
                sy = y + ch / 2
                painter.drawLine(QPointF(x0, sy), QPointF(x1, sy))

    def _cursor_rect(self) -> QRectF:
        cursor = self._emulator.cursor
        cols = self._emulator.cols
        x = min(cursor.x, cols - 1)
        line = self._emulator.screen.buffer[cursor.y]
        width = 2 if x + 1 < cols and line[x + 1].data == "" else 1
        return QRectF(
            PADDING + x * self._cell_w,
            PADDING + cursor.y * self._cell_h,
            width * self._cell_w,
            self._cell_h,
        )

    def _paint_cursor(self, painter: QPainter) -> None:
        cursor = self._emulator.cursor
        if self._view_offset != 0 or not cursor.visible:
            return
        rect = self._cursor_rect()
        color = self._color(self._theme.cursor)
        if self.hasFocus():
            painter.fillRect(rect, color)
            x = min(cursor.x, self._emulator.cols - 1)
            char = self._emulator.screen.buffer[cursor.y][x]
            if char.data.strip():
                painter.setPen(self._color(self._theme.background))
                painter.setFont(self._fonts[(char.bold, char.italics)])
                painter.drawText(QPointF(rect.x(), rect.y() + self._ascent), char.data)
        else:
            painter.setPen(QPen(color, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect.adjusted(0.5, 0.5, -0.5, -0.5))

    # ----- performance instrumentation (PYSSH_DEBUG_PERF=1) ---------------------------

    def _start_perf_monitor(self) -> None:
        self._perf_timer = QTimer(self)
        self._perf_timer.setInterval(PERF_TICK_MS)
        self._perf_last_tick = time.perf_counter()
        self._perf_window_start = self._perf_last_tick
        self._perf_max_lag = 0.0
        self._perf_timer.timeout.connect(self._perf_tick)
        self._perf_timer.start()

    def _perf_tick(self) -> None:
        now = time.perf_counter()
        lag_ms = (now - self._perf_last_tick) * 1000 - PERF_TICK_MS
        self._perf_last_tick = now
        self._perf_max_lag = max(self._perf_max_lag, lag_ms)
        elapsed = now - self._perf_window_start
        if elapsed >= PERF_REPORT_S:
            mb_per_s = self._perf_bytes / elapsed / 1_000_000
            log.info(
                "perf max_lag_ms=%.0f bytes_processed=%d mb_per_s=%.3f",
                self._perf_max_lag,
                self._perf_bytes,
                mb_per_s,
            )
            self._perf_window_start = now
            self._perf_max_lag = 0.0
            self._perf_bytes = 0


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))
