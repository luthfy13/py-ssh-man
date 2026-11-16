"""Drag-selection auto-scroll of TerminalWidget (design: DESAIN-SELEKSI section 4)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt, QTimer
from PySide6.QtGui import QContextMenuEvent, QHideEvent, QMouseEvent
from PySide6.QtWidgets import QApplication, QLineEdit, QVBoxLayout, QWidget

from pyssh.models import AppSettings
from pyssh.terminal import widget as widget_module
from pyssh.terminal.widget import (
    AUTOSCROLL_INTERVAL_MS,
    AUTOSCROLL_MAX_LINES,
    PADDING,
    TerminalWidget,
)

TOTAL_LINES = 200
TIMEOUT = 10_000


@pytest.fixture
def term(qtbot) -> TerminalWidget:
    widget = TerminalWidget(AppSettings(copy_on_select=False))
    qtbot.addWidget(widget)
    widget.resize(700, 400)
    widget.show()
    qtbot.waitExposed(widget)
    text = "".join(f"line {i:03d}\r\n" for i in range(TOTAL_LINES))
    widget.feed(text.encode())
    widget.flush_pending()
    QApplication.processEvents()
    return widget


def _mouse(widget: TerminalWidget, kind: QEvent.Type, y: float, x: float = 20, *, held=True):
    pos = QPointF(x, y)
    left = Qt.MouseButton.LeftButton
    if kind == QEvent.Type.MouseMove:
        button = Qt.MouseButton.NoButton
        buttons = left if held else Qt.MouseButton.NoButton
    else:
        button = left
        buttons = left if kind == QEvent.Type.MouseButtonPress else Qt.MouseButton.NoButton
    event = QMouseEvent(kind, pos, pos, button, buttons, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(widget, event)


def _press(widget, y, x=20):
    _mouse(widget, QEvent.Type.MouseButtonPress, y, x)


def _move(widget, y, x=20, *, held=True):
    _mouse(widget, QEvent.Type.MouseMove, y, x, held=held)


def _release(widget, y, x=20):
    _mouse(widget, QEvent.Type.MouseButtonRelease, y, x)


def _row_y(widget: TerminalWidget, row: int) -> float:
    """Pointer y in the middle of visible row ``row``."""
    return PADDING + (row + 0.5) * widget.cell_size[1]


def _above(widget: TerminalWidget, cells: int) -> float:
    """Pointer y roughly ``cells`` rows above the top edge of the text area."""
    return PADDING - (cells + 0.5) * widget.cell_size[1]


def _below(widget: TerminalWidget, cells: int) -> float:
    """Pointer y roughly ``cells`` rows below the bottom edge of the text area."""
    rows = widget.grid_size()[1]
    return PADDING + rows * widget.cell_size[1] + (cells + 0.5) * widget.cell_size[1]


def _stop_timer(widget: TerminalWidget) -> None:
    widget._autoscroll_timer.stop()


def test_constants() -> None:
    assert AUTOSCROLL_INTERVAL_MS == 50
    assert AUTOSCROLL_MAX_LINES == 10
    assert widget_module.AUTOSCROLL_INTERVAL_MS == AUTOSCROLL_INTERVAL_MS


def test_drag_above_top_scrolls_into_history(term, qtbot) -> None:
    assert term.view_offset == 0
    history = term.emulator.history_len
    assert history > 50
    first_visible = term.emulator.visible_range(0)[0]
    _press(term, _row_y(term, 5))
    anchor_line = term.emulator.visible_range(0)[5]
    _move(term, _above(term, 3))
    qtbot.waitUntil(lambda: term.view_offset >= 20, timeout=TIMEOUT)
    _release(term, _above(term, 3))
    start, end = term.selection_range()
    assert start[0] < first_visible  # reaches lines that were not visible at press time
    assert end[0] == anchor_line
    lines = term.selected_text().splitlines()
    assert len(lines) > 20
    numbers = [int(line.split()[1]) for line in lines if line.startswith("line ")]
    assert numbers == list(range(numbers[0], numbers[0] + len(numbers)))  # consecutive


def test_drag_below_bottom_scrolls_toward_live(term, qtbot) -> None:
    term.scroll_by(60)
    start_offset = term.view_offset
    assert start_offset == 60
    bottom_line = term.emulator.visible_range(start_offset)[-1]
    _press(term, _row_y(term, 5))
    _move(term, _below(term, 3))
    qtbot.waitUntil(lambda: term.view_offset <= start_offset - 20, timeout=TIMEOUT)
    _release(term, _below(term, 3))
    assert term.view_offset < start_offset
    _, end = term.selection_range()
    assert end[0] > bottom_line  # selection extends below what was visible


def test_history_limit_is_reached_without_error(term, qtbot) -> None:
    history = term.emulator.history_len
    _press(term, _row_y(term, 5))
    _move(term, _above(term, 20))
    qtbot.waitUntil(lambda: term.view_offset == history, timeout=TIMEOUT)
    qtbot.wait(4 * AUTOSCROLL_INTERVAL_MS)
    assert term.view_offset == history
    _release(term, _above(term, 20))
    assert term.view_offset == history
    start, _ = term.selection_range()
    assert start[0] == 0


def test_bottom_limit_is_zero(term, qtbot) -> None:
    term.scroll_by(30)
    _press(term, _row_y(term, 5))
    _move(term, _below(term, 20))
    qtbot.waitUntil(lambda: term.view_offset == 0, timeout=TIMEOUT)
    qtbot.wait(4 * AUTOSCROLL_INTERVAL_MS)
    assert term.view_offset == 0
    _release(term, _below(term, 20))


def test_farther_pointer_scrolls_faster_per_tick(term) -> None:
    def lines_per_tick(cells_outside: int) -> int:
        term.scroll_to_bottom()
        term.clear_selection()
        _press(term, _row_y(term, 5))
        _move(term, _above(term, cells_outside))
        _stop_timer(term)  # deterministic: drive exactly one tick by hand
        before = term.view_offset
        term._autoscroll_timer.timeout.emit()
        delta = term.view_offset - before
        _release(term, _above(term, cells_outside))
        return delta

    near = lines_per_tick(0)
    far = lines_per_tick(5)
    assert near >= 1
    assert far > near
    assert far <= AUTOSCROLL_MAX_LINES


def test_speed_is_capped(term) -> None:
    _press(term, _row_y(term, 5))
    _move(term, _above(term, 100))
    _stop_timer(term)
    before = term.view_offset
    term._autoscroll_timer.timeout.emit()
    assert term.view_offset - before == AUTOSCROLL_MAX_LINES
    _release(term, _above(term, 100))


def test_reentering_text_area_stops_scrolling(term, qtbot) -> None:
    _press(term, _row_y(term, 5))
    _move(term, _above(term, 2))
    qtbot.waitUntil(lambda: term.view_offset > 0, timeout=TIMEOUT)
    _move(term, _row_y(term, 8))
    settled = term.view_offset
    qtbot.wait(6 * AUTOSCROLL_INTERVAL_MS)
    assert term.view_offset == settled
    _release(term, _row_y(term, 8))
    assert term.view_offset == settled


def test_release_stops_timer(term, qtbot) -> None:
    _press(term, _row_y(term, 5))
    _move(term, _above(term, 2))
    qtbot.waitUntil(lambda: term.view_offset > 0, timeout=TIMEOUT)
    _release(term, _above(term, 2))
    assert not term._autoscroll_timer.isActive()
    settled = term.view_offset
    qtbot.wait(6 * AUTOSCROLL_INTERVAL_MS)
    assert term.view_offset == settled


def test_clear_selection_stops_scrolling(term, qtbot) -> None:
    _press(term, _row_y(term, 5))
    _move(term, _above(term, 2))
    qtbot.waitUntil(lambda: term.view_offset > 0, timeout=TIMEOUT)
    term.clear_selection()
    settled = term.view_offset
    qtbot.wait(6 * AUTOSCROLL_INTERVAL_MS)
    assert term.view_offset == settled
    _release(term, _above(term, 2))


def test_anchor_stays_fixed(term, qtbot) -> None:
    _press(term, _row_y(term, 5))
    anchor_line = term.emulator.visible_range(0)[5]
    _move(term, _above(term, 3))
    qtbot.waitUntil(lambda: term.view_offset > 10, timeout=TIMEOUT)
    _release(term, _above(term, 3))
    start, end = term.selection_range()
    assert end[0] == anchor_line
    assert start[0] < anchor_line


def test_move_without_button_does_not_scroll(term, qtbot) -> None:
    _move(term, _above(term, 5), held=False)
    qtbot.wait(6 * AUTOSCROLL_INTERVAL_MS)
    assert term.view_offset == 0
    assert term.selection_range() is None
    _move(term, _below(term, 5), held=False)
    qtbot.wait(6 * AUTOSCROLL_INTERVAL_MS)
    assert term.view_offset == 0


def test_plain_drag_inside_text_area(term, qtbot) -> None:
    _press(term, _row_y(term, 2), x=20)
    _move(term, _row_y(term, 4), x=120)
    qtbot.wait(4 * AUTOSCROLL_INTERVAL_MS)
    _release(term, _row_y(term, 4), x=120)
    assert term.view_offset == 0
    lines = term.emulator.visible_range(0)
    start, end = term.selection_range()
    assert start[0] == lines[2]
    assert end[0] == lines[4]
    assert len(term.selected_text().splitlines()) == 3


def test_double_click_selects_word(term) -> None:
    pos = QPointF(25, _row_y(term, 3))
    left = Qt.MouseButton.LeftButton
    mods = Qt.KeyboardModifier.NoModifier
    QApplication.sendEvent(
        term, QMouseEvent(QEvent.Type.MouseButtonPress, pos, pos, left, left, mods)
    )
    QApplication.sendEvent(
        term, QMouseEvent(QEvent.Type.MouseButtonDblClick, pos, pos, left, left, mods)
    )
    QApplication.sendEvent(
        term,
        QMouseEvent(QEvent.Type.MouseButtonRelease, pos, pos, left, Qt.MouseButton.NoButton, mods),
    )
    assert term.selected_text() == "line"


def test_copy_on_select_still_copies_after_autoscroll(qtbot) -> None:
    widget = TerminalWidget(AppSettings(copy_on_select=True))
    qtbot.addWidget(widget)
    widget.resize(700, 400)
    widget.show()
    qtbot.waitExposed(widget)
    widget.feed("".join(f"line {i:03d}\r\n" for i in range(TOTAL_LINES)).encode())
    widget.flush_pending()
    _press(widget, _row_y(widget, 5))
    _move(widget, _above(widget, 3))
    qtbot.waitUntil(lambda: widget.view_offset > 10, timeout=TIMEOUT)
    _release(widget, _above(widget, 3))
    clip = QApplication.clipboard().text()
    assert clip == widget.selected_text()
    assert len(clip.splitlines()) > 10


# --- Round 2 (design section 6.2) ---------------------------------------------------------


def _start_outside_drag(term, qtbot, cells: int = 2) -> None:
    """Press inside, move outside and wait until auto-scroll has really scrolled."""
    _press(term, _row_y(term, 5))
    _move(term, _above(term, cells))
    qtbot.waitUntil(lambda: term.view_offset > 0, timeout=TIMEOUT)


def test_new_output_mid_drag_ends_autoscroll(term, qtbot) -> None:
    _start_outside_drag(term, qtbot)
    term.feed(b"fresh output\r\n")
    term.flush_pending()
    assert not term.has_selection()  # output wipes the selection
    _move(term, _above(term, 2))  # pointer outside again, button still held
    settled = term.view_offset
    assert not term._autoscroll_timer.isActive()
    qtbot.wait(8 * AUTOSCROLL_INTERVAL_MS)
    assert term.view_offset == settled
    assert not term._autoscroll_timer.isActive()
    _release(term, _above(term, 2))
    assert term.view_offset == settled


def test_clear_selection_mid_drag_then_outside_again_does_not_scroll(term, qtbot) -> None:
    _start_outside_drag(term, qtbot)
    term.clear_selection()
    _move(term, _above(term, 2))
    settled = term.view_offset
    assert not term._autoscroll_timer.isActive()
    qtbot.wait(8 * AUTOSCROLL_INTERVAL_MS)
    assert term.view_offset == settled
    assert not term._autoscroll_timer.isActive()
    _release(term, _above(term, 2))


def test_hide_ends_drag_and_autoscroll(term, qtbot) -> None:
    _start_outside_drag(term, qtbot)
    emits: list[int] = []
    term.scroll_state_changed.connect(lambda *args: emits.append(1))
    term.hide()
    assert not term._autoscroll_timer.isActive()
    assert term._dragging is False
    settled = term.view_offset
    emits.clear()
    qtbot.wait(8 * AUTOSCROLL_INTERVAL_MS)
    assert term.view_offset == settled
    assert emits == []


def test_context_menu_ends_drag_and_autoscroll(term, qtbot) -> None:
    _start_outside_drag(term, qtbot)
    seen: dict[str, object] = {}

    def close_popup() -> None:
        popup = QApplication.activePopupWidget()
        if popup is None:
            QTimer.singleShot(20, close_popup)  # popup not up yet; retry
            return
        seen["offset_open"] = term.view_offset
        popup.close()

    QTimer.singleShot(50, close_popup)
    event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(20, 20), QPoint(20, 20))
    term.contextMenuEvent(event)  # blocks until the popup is closed
    assert "offset_open" in seen
    assert term._dragging is False
    assert not term._autoscroll_timer.isActive()
    settled = term.view_offset
    qtbot.wait(8 * AUTOSCROLL_INTERVAL_MS)
    assert term.view_offset == settled
    assert not term._autoscroll_timer.isActive()


def test_no_scroll_state_emits_at_history_limit(term, qtbot) -> None:
    history = term.emulator.history_len
    _press(term, _row_y(term, 5))
    _move(term, _above(term, 20))
    qtbot.waitUntil(lambda: term.view_offset == history, timeout=TIMEOUT)
    qtbot.wait(2 * AUTOSCROLL_INTERVAL_MS)  # let any in-flight tick finish
    emits: list[int] = []
    term.scroll_state_changed.connect(lambda *args: emits.append(1))
    qtbot.wait(8 * AUTOSCROLL_INTERVAL_MS)
    assert emits == []
    assert term.view_offset == history
    _release(term, _above(term, 20))


def test_no_scroll_state_emits_at_live_bottom(term, qtbot) -> None:
    term.scroll_by(30)
    _press(term, _row_y(term, 5))
    _move(term, _below(term, 20))
    qtbot.waitUntil(lambda: term.view_offset == 0, timeout=TIMEOUT)
    qtbot.wait(2 * AUTOSCROLL_INTERVAL_MS)
    emits: list[int] = []
    term.scroll_state_changed.connect(lambda *args: emits.append(1))
    qtbot.wait(8 * AUTOSCROLL_INTERVAL_MS)
    assert emits == []
    _release(term, _below(term, 20))


def test_bottom_edge_boundary_is_inclusive(term, qtbot) -> None:
    term.scroll_by(30)
    rows = term.grid_size()[1]
    edge = PADDING + rows * term.cell_size[1]
    _press(term, _row_y(term, 5))
    _move(term, edge)  # exactly on the bottom edge counts as outside
    qtbot.waitUntil(lambda: term.view_offset < 30, timeout=TIMEOUT)
    _release(term, edge)


def test_pointer_just_inside_bottom_edge_does_not_scroll(term, qtbot) -> None:
    term.scroll_by(30)
    rows = term.grid_size()[1]
    edge = PADDING + rows * term.cell_size[1]
    _press(term, _row_y(term, 5))
    _move(term, edge - 1)
    assert not term._autoscroll_timer.isActive()
    qtbot.wait(6 * AUTOSCROLL_INTERVAL_MS)
    assert term.view_offset == 30
    _release(term, edge - 1)


def test_tick_guard_stops_when_selection_vanishes_without_move(term, qtbot) -> None:
    _start_outside_drag(term, qtbot)
    term.feed(b"fresh output\r\n")
    term.flush_pending()
    # Pointer stays still outside: no further mouse move arrives.
    settled = term.view_offset
    qtbot.wait(8 * AUTOSCROLL_INTERVAL_MS)
    assert term.view_offset == settled
    assert not term._autoscroll_timer.isActive()
    _release(term, _above(term, 2))


def test_tick_guard_itself_stops_timer_when_anchor_is_gone(term, qtbot) -> None:
    """Defense in depth: the tick must stop on its own if the anchor vanishes while it runs."""
    _start_outside_drag(term, qtbot)
    assert term._autoscroll_timer.isActive()
    term._sel_anchor = None  # bypasses clear_selection(), which would stop the timer itself
    settled = term.view_offset
    qtbot.waitUntil(lambda: not term._autoscroll_timer.isActive(), timeout=TIMEOUT)
    assert term.view_offset - settled <= AUTOSCROLL_MAX_LINES  # at most one tick slipped in
    after = term.view_offset
    qtbot.wait(8 * AUTOSCROLL_INTERVAL_MS)
    assert term.view_offset == after


def test_focus_out_to_sibling_ends_drag_and_autoscroll(qtbot) -> None:
    parent = QWidget()
    layout = QVBoxLayout(parent)
    term = TerminalWidget(AppSettings(copy_on_select=False))
    line_edit = QLineEdit()
    layout.addWidget(term)
    layout.addWidget(line_edit)
    qtbot.addWidget(parent)
    parent.resize(700, 500)
    parent.show()
    qtbot.waitExposed(parent)
    term.feed("".join(f"line {i:03d}\r\n" for i in range(TOTAL_LINES)).encode())
    term.flush_pending()
    QApplication.processEvents()
    _start_outside_drag(term, qtbot)
    assert term._dragging
    line_edit.setFocus()
    qtbot.waitUntil(lambda: line_edit.hasFocus(), timeout=TIMEOUT)
    assert term._dragging is False
    assert not term._autoscroll_timer.isActive()
    settled = term.view_offset
    qtbot.wait(8 * AUTOSCROLL_INTERVAL_MS)
    assert term.view_offset == settled
    assert not term._autoscroll_timer.isActive()


def test_hide_event_alone_ends_drag_and_autoscroll(term, qtbot) -> None:
    # The widget stays visible/focused: only the QHideEvent itself is delivered.
    _start_outside_drag(term, qtbot)
    assert term._dragging
    QApplication.sendEvent(term, QHideEvent())
    assert term._dragging is False
    assert not term._autoscroll_timer.isActive()
    settled = term.view_offset
    qtbot.wait(8 * AUTOSCROLL_INTERVAL_MS)
    assert term.view_offset == settled
    assert not term._autoscroll_timer.isActive()


# Note: contextMenuEvent is covered by test_context_menu_ends_drag_and_autoscroll above. A
# popup menu always takes focus (focusOutEvent -> _end_drag), so that test cannot isolate
# the explicit _end_drag() call in contextMenuEvent from the focus-out path (overlap).
