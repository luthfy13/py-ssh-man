"""Tests for terminal.widget and terminal.view (SPEC §8.4, §8.5, §10.2)."""

from __future__ import annotations

from dataclasses import replace

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QGuiApplication, QInputMethodEvent, QWheelEvent
from PySide6.QtWidgets import QApplication

from pyssh import strings
from pyssh.models import AppSettings
from pyssh.terminal import widget as widget_module
from pyssh.terminal.view import TerminalView
from pyssh.terminal.widget import (
    BACKPRESSURE_HIGH,
    PADDING,
    TerminalWidget,
    default_font_families,
    pick_font_family,
)

K = Qt.Key
M = Qt.KeyboardModifier


@pytest.fixture
def term(qtbot) -> TerminalWidget:
    widget = TerminalWidget(AppSettings())
    qtbot.addWidget(widget)
    widget.resize(800, 400)
    widget.show()  # Qt delivers resize events to hidden widgets only when they are shown
    qtbot.waitExposed(widget)
    return widget


def _record(signal) -> list:
    seen: list = []
    signal.connect(lambda *args: seen.append(args if len(args) != 1 else args[0]))
    return seen


def _expected_grid(widget: TerminalWidget) -> tuple[int, int]:
    cw, ch = widget.cell_size
    return (
        max(20, int((widget.width() - 2 * PADDING) // cw)),
        max(5, int((widget.height() - 2 * PADDING) // ch)),
    )


def test_font_family_choice() -> None:
    assert default_font_families(windows=True, mac=False)[0] == "Cascadia Mono"
    assert default_font_families(windows=False, mac=True)[0] == "Menlo"
    assert default_font_families(windows=False, mac=False)[0] == "DejaVu Sans Mono"
    linux = {"windows": False, "mac": False}
    assert pick_font_family("Foo", ["Foo", "DejaVu Sans Mono"], **linux) == "Foo"
    assert pick_font_family("Missing", ["Liberation Mono"], **linux) == "Liberation Mono"
    assert pick_font_family("", ["Consolas"], windows=True, mac=False) == "Consolas"
    assert pick_font_family("", ["Arial"], **linux) is None


def test_grid_follows_widget_size(term: TerminalWidget) -> None:
    assert term.grid_size() == _expected_grid(term)
    term.resize(1000, 600)
    assert term.grid_size() == _expected_grid(term)
    term.resize(10, 10)
    assert term.grid_size() == (20, 5)  # minimum grid


def test_feed_and_flush_fill_screen(term: TerminalWidget) -> None:
    term.feed(b"hello\r\n\x1b[31mworld")
    assert term.emulator.screen_lines_text()[0] == ""  # not processed yet
    term.flush_pending()
    assert term.emulator.screen_lines_text()[:2] == ["hello", "world"]


def test_pump_processes_asynchronously(term: TerminalWidget, qtbot) -> None:
    term.feed(b"async text")
    qtbot.waitUntil(lambda: term.emulator.screen_lines_text()[0] == "async text", timeout=2000)


def test_paint_renders_without_errors(term: TerminalWidget, qtbot) -> None:
    term.show()
    qtbot.waitExposed(term)
    term.feed(
        "\x1b[1;4;9;3mbold\x1b[0m \x1b[7mrev\x1b[0m \x1b[41;37mbg\x1b[0m 漢字 ┌─┐\r\n".encode()
    )
    term.flush_pending()
    term.set_selection((0, 0), (0, 4))
    term.setFocus()
    assert not term.grab().isNull()
    term.clearFocus()
    assert not term.grab().isNull()


def test_keys_send_bytes(term: TerminalWidget, qtbot) -> None:
    sent = _record(term.input_bytes)
    qtbot.keyClick(term, K.Key_Up)
    qtbot.keyClick(term, K.Key_C, M.ControlModifier)
    qtbot.keyClick(term, K.Key_A)
    assert sent == [b"\x1b[A", b"\x03", b"a"]


def test_app_cursor_keys_used(term: TerminalWidget, qtbot) -> None:
    sent = _record(term.input_bytes)
    term.feed(b"\x1b[?1h")
    term.flush_pending()
    qtbot.keyClick(term, K.Key_Up)
    assert sent == [b"\x1bOA"]


def test_tab_goes_to_terminal(term: TerminalWidget, qtbot) -> None:
    sent = _record(term.input_bytes)
    qtbot.keyClick(term, K.Key_Tab)
    assert sent == [b"\t"]
    assert term.focusNextPrevChild(True) is False


def test_shortcut_override(term: TerminalWidget) -> None:
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent

    ctrl_c = QKeyEvent(QEvent.Type.ShortcutOverride, K.Key_C, M.ControlModifier, "\x03")
    ctrl_c.ignore()
    QApplication.sendEvent(term, ctrl_c)
    assert ctrl_c.isAccepted()  # terminal keeps Ctrl+C
    new_session = QKeyEvent(
        QEvent.Type.ShortcutOverride, K.Key_N, M.ControlModifier | M.ShiftModifier, ""
    )
    new_session.accept()
    QApplication.sendEvent(term, new_session)
    assert not new_session.isAccepted()  # application shortcut


def test_paste_plain(term: TerminalWidget) -> None:
    sent = _record(term.input_bytes)
    QGuiApplication.clipboard().setText("a\r\nb\nc")
    term.paste_clipboard()
    assert sent == [b"a\rb\rc"]


def test_paste_bracketed(term: TerminalWidget) -> None:
    sent = _record(term.input_bytes)
    term.feed(b"\x1b[?2004h")
    term.flush_pending()
    QGuiApplication.clipboard().setText("x\x1b[201~y\n")
    term.paste_clipboard()
    assert sent == [b"\x1b[200~xy\r\x1b[201~"]


def test_paste_ignored_when_input_disabled_or_empty(term: TerminalWidget) -> None:
    sent = _record(term.input_bytes)
    QGuiApplication.clipboard().setText("")
    term.paste_clipboard()
    term.set_input_enabled(False)
    QGuiApplication.clipboard().setText("x")
    term.paste_clipboard()
    assert sent == []


def test_paste_shortcut(term: TerminalWidget, qtbot) -> None:
    sent = _record(term.input_bytes)
    QGuiApplication.clipboard().setText("clip")
    qtbot.keyClick(term, K.Key_V, M.ControlModifier | M.ShiftModifier)
    assert sent == [b"clip"]


def test_resize_debounce_emits_once(term: TerminalWidget, qtbot) -> None:
    qtbot.wait(200)  # let the initial resize settle
    sizes = _record(term.grid_size_changed)
    for width in (700, 720, 760, 900):
        term.resize(width, 500)
    qtbot.wait(300)
    assert sizes == [term.grid_size()]


def _wheel(widget: TerminalWidget, delta_y: int, mods, pixel_y: int = 0) -> None:
    event = QWheelEvent(
        QPointF(10, 10),
        QPointF(10, 10),
        QPoint(0, pixel_y),
        QPoint(0, delta_y),
        Qt.MouseButton.NoButton,
        mods,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(widget, event)


def test_ctrl_wheel_zooms(term: TerminalWidget) -> None:
    sizes = _record(term.font_size_changed)
    _wheel(term, 120, M.ControlModifier)
    assert term.font_size == 12
    _wheel(term, -120, M.ControlModifier)
    _wheel(term, -120, M.ControlModifier)
    assert term.font_size == 10
    assert sizes == [12, 11, 10]


def test_zoom_limits_and_reset(term: TerminalWidget) -> None:
    for _ in range(40):
        term.zoom_in()
    assert term.font_size == 32
    for _ in range(40):
        term.zoom_out()
    assert term.font_size == 6
    term.zoom_reset()
    assert term.font_size == 11


def test_wheel_scrolls_scrollback(term: TerminalWidget) -> None:
    term.feed(b"".join(b"%d\r\n" % i for i in range(200)))
    term.flush_pending()
    _wheel(term, 120, M.NoModifier)
    assert term.view_offset == 3
    _wheel(term, 40, M.NoModifier)  # high-resolution wheel: one line
    assert term.view_offset == 4
    _wheel(term, -240, M.NoModifier)
    assert term.view_offset == 0
    cell_h = term.cell_size[1]
    _wheel(term, 0, M.NoModifier, pixel_y=int(cell_h * 2) + 1)
    assert term.view_offset == 2


def test_shift_page_up_scrolls(term: TerminalWidget, qtbot) -> None:
    term.feed(b"".join(b"%d\r\n" % i for i in range(200)))
    term.flush_pending()
    rows = term.grid_size()[1]
    sent = _record(term.input_bytes)
    qtbot.keyClick(term, K.Key_PageUp, M.ShiftModifier)
    assert term.view_offset == rows
    qtbot.keyClick(term, K.Key_PageDown, M.ShiftModifier)
    assert term.view_offset == 0
    qtbot.keyClick(term, K.Key_PageUp, M.ShiftModifier)
    qtbot.keyClick(term, K.Key_X)  # typing returns to the bottom
    assert term.view_offset == 0
    assert sent == [b"x"]


def test_view_stays_put_while_output_arrives(term: TerminalWidget) -> None:
    term.feed(b"".join(b"%d\r\n" % i for i in range(100)))
    term.flush_pending()
    term.scroll_by(10)
    first = term.emulator.visible_range(term.view_offset).start
    first_text = term.emulator.line_text(first)
    term.feed(b"".join(b"new %d\r\n" % i for i in range(5)))
    term.flush_pending()
    assert term.view_offset == 15
    assert term.emulator.line_text(term.emulator.visible_range(term.view_offset).start) == (
        first_text
    )


def test_drag_selection_copies(term: TerminalWidget, qtbot) -> None:
    term.feed(b"hello world")
    term.flush_pending()
    cw, ch = term.cell_size
    y = int(PADDING + ch / 2)
    qtbot.mousePress(term, Qt.MouseButton.LeftButton, pos=QPoint(int(PADDING + 1), y))
    qtbot.mouseMove(term, QPoint(int(PADDING + 5 * cw + 1), y))
    qtbot.mouseRelease(term, Qt.MouseButton.LeftButton, pos=QPoint(int(PADDING + 5 * cw + 1), y))
    assert term.selected_text() == "hello"
    assert QGuiApplication.clipboard().text() == "hello"


def test_click_without_drag_clears_selection(term: TerminalWidget, qtbot) -> None:
    term.feed(b"hello")
    term.flush_pending()
    term.set_selection((term.emulator.history_len, 0), (term.emulator.history_len, 3))
    assert term.has_selection()
    qtbot.mouseClick(term, Qt.MouseButton.LeftButton, pos=QPoint(20, 10))
    assert not term.has_selection()


def test_double_click_selects_word(term: TerminalWidget, qtbot) -> None:
    term.feed(b"cd /var/log-x.1 (next)")
    term.flush_pending()
    cw, ch = term.cell_size
    point = QPoint(int(PADDING + 6 * cw + 2), int(PADDING + ch / 2))
    qtbot.mouseDClick(term, Qt.MouseButton.LeftButton, pos=point)
    assert term.selected_text() == "/var/log-x.1"
    point = QPoint(int(PADDING + 2 * cw + 2), int(PADDING + ch / 2))  # on a space
    qtbot.mouseDClick(term, Qt.MouseButton.LeftButton, pos=point)
    assert term.selected_text() == ""  # a single space, right-stripped


def test_new_output_clears_selection(term: TerminalWidget) -> None:
    term.feed(b"abc")
    term.flush_pending()
    term.set_selection((0, 0), (0, 2))
    term.feed(b"d")
    term.flush_pending()
    assert not term.has_selection()


def test_copy_without_selection(term: TerminalWidget) -> None:
    assert term.copy_selection() is False


def test_input_disabled_reconnect(term: TerminalWidget, qtbot) -> None:
    sent = _record(term.input_bytes)
    requests = _record(term.reconnect_requested)
    term.set_input_enabled(False)
    assert term.input_enabled is False
    qtbot.keyClick(term, K.Key_A)
    qtbot.keyClick(term, K.Key_R, M.ControlModifier)  # modifier: ignored
    qtbot.keyClick(term, K.Key_R)
    qtbot.keyClick(term, K.Key_Return)
    qtbot.keyClick(term, K.Key_Enter, M.KeypadModifier)
    assert len(requests) == 3
    assert sent == []


def test_input_method_commit(term: TerminalWidget) -> None:
    sent = _record(term.input_bytes)
    event = QInputMethodEvent()
    event.setCommitString("ñ")
    QApplication.sendEvent(term, event)
    assert sent == ["ñ".encode()]
    rect = term.inputMethodQuery(Qt.InputMethodQuery.ImCursorRectangle)
    assert rect.width() > 0


def test_backpressure_constants() -> None:
    # Lowered from SPEC §8.4.3 (4 MiB / 1 MiB) in Phase 8 for N-04; see docs/PROGRESS.md.
    assert BACKPRESSURE_HIGH == 256 * 1024
    assert widget_module.BACKPRESSURE_LOW == 64 * 1024


def test_backpressure_thresholds(term: TerminalWidget, monkeypatch: pytest.MonkeyPatch) -> None:
    # Same logic with small thresholds, so the test does not push 4 MiB through pyte.
    monkeypatch.setattr(widget_module, "BACKPRESSURE_HIGH", 4000)
    monkeypatch.setattr(widget_module, "BACKPRESSURE_LOW", 1000)
    states = _record(term.backpressure)
    term.feed(b"x" * 3000)
    assert states == []
    term.feed(b"y" * 1001)
    assert states == [True]
    assert term.backpressure_active
    term.feed(b"z" * 10)
    assert states == [True]  # no repeated signal
    term.flush_pending()
    assert states == [True, False]
    assert not term.backpressure_active


def test_write_local_is_not_sent(term: TerminalWidget) -> None:
    sent = _record(term.input_bytes)
    term.write_local("Menghubungkan…", "yellow")
    term.flush_pending()
    assert sent == []
    assert "Menghubungkan…" in term.emulator.screen_lines_text()
    line = term.emulator.history_len + term.emulator.screen_lines_text().index("Menghubungkan…")
    assert term.emulator.line_at(line)[0].fg == "brown"


def test_emulator_responses_go_to_backend(term: TerminalWidget) -> None:
    sent = _record(term.input_bytes)
    term.feed(b"\x1b[6n")
    term.flush_pending()
    assert sent == [b"\x1b[1;1R"]


def test_title_changed(term: TerminalWidget) -> None:
    titles = _record(term.title_changed)
    term.feed(b"\x1b]2;server:~\x07")
    term.flush_pending()
    assert titles == ["server:~"]


def test_clear_scrollback(term: TerminalWidget) -> None:
    term.feed(b"".join(b"%d\r\n" % i for i in range(100)))
    term.flush_pending()
    term.scroll_by(5)
    term.clear_scrollback()
    assert term.emulator.history_len == 0
    assert term.view_offset == 0


def test_context_menu(term: TerminalWidget) -> None:
    menu = term.context_menu()
    texts = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert texts == [
        strings.TERMINAL_COPY,
        strings.TERMINAL_PASTE,
        strings.TERMINAL_CLEAR_SCROLLBACK,
    ]
    assert not menu.actions()[0].isEnabled()  # nothing selected


def test_apply_settings(term: TerminalWidget) -> None:
    sizes = _record(term.font_size_changed)
    term.apply_settings(replace(AppSettings(), font_size=14, copy_on_select=False))
    assert term.font_size == 14
    assert sizes == [14]


def test_perf_monitor_logs(qtbot, monkeypatch: pytest.MonkeyPatch, caplog) -> None:
    import logging

    monkeypatch.setenv("PYSSH_DEBUG_PERF", "1")
    monkeypatch.setattr(widget_module, "PERF_REPORT_S", 0.15)
    widget = TerminalWidget(AppSettings())
    qtbot.addWidget(widget)
    widget.feed(b"x" * 1000)
    with caplog.at_level(logging.INFO, logger="pyssh.terminal.widget"):
        qtbot.waitUntil(lambda: "perf max_lag_ms=" in caplog.text, timeout=3000)


def test_view_scrollbar_sync(qtbot) -> None:
    view = TerminalView(AppSettings())
    qtbot.addWidget(view)
    view.resize(800, 400)
    view.show()
    qtbot.waitExposed(view)
    term = view.terminal
    term.feed(b"".join(b"%d\r\n" % i for i in range(100)))
    term.flush_pending()
    bar = view.scrollbar
    history = term.emulator.history_len
    assert (bar.maximum(), bar.value()) == (history, history)
    assert bar.pageStep() == term.grid_size()[1]
    bar.setValue(history - 7)
    assert term.view_offset == 7
    term.scroll_to_bottom()
    assert bar.value() == history


class _FakeClipboard:
    """Clipboard with X11-style primary selection (offscreen Qt has none)."""

    def __init__(self) -> None:
        from PySide6.QtGui import QClipboard

        self.data = {QClipboard.Mode.Clipboard: "", QClipboard.Mode.Selection: ""}

    def supportsSelection(self) -> bool:
        return True

    def setText(self, text: str, mode=None) -> None:
        from PySide6.QtGui import QClipboard

        self.data[mode or QClipboard.Mode.Clipboard] = text

    def text(self, mode=None) -> str:
        from PySide6.QtGui import QClipboard

        return self.data[mode or QClipboard.Mode.Clipboard]


def test_primary_selection(term: TerminalWidget, qtbot, monkeypatch) -> None:
    from PySide6.QtGui import QClipboard

    fake = _FakeClipboard()
    monkeypatch.setattr(QGuiApplication, "clipboard", staticmethod(lambda: fake))
    term.feed(b"select me")
    term.flush_pending()
    cw, ch = term.cell_size
    y = int(PADDING + ch / 2)
    qtbot.mousePress(term, Qt.MouseButton.LeftButton, pos=QPoint(int(PADDING + 1), y))
    qtbot.mouseMove(term, QPoint(int(PADDING + 6 * cw + 1), y))
    qtbot.mouseRelease(term, Qt.MouseButton.LeftButton, pos=QPoint(int(PADDING + 6 * cw + 1), y))
    assert fake.data[QClipboard.Mode.Selection] == "select"
    assert fake.data[QClipboard.Mode.Clipboard] == "select"
    sent = _record(term.input_bytes)
    fake.data[QClipboard.Mode.Selection] = "primary"
    qtbot.mouseClick(term, Qt.MouseButton.MiddleButton, pos=QPoint(20, 10))
    assert sent == [b"primary"]


def test_primary_selection_without_copy_on_select(qtbot, monkeypatch) -> None:
    from PySide6.QtGui import QClipboard

    fake = _FakeClipboard()
    monkeypatch.setattr(QGuiApplication, "clipboard", staticmethod(lambda: fake))
    widget = TerminalWidget(replace(AppSettings(), copy_on_select=False))
    qtbot.addWidget(widget)
    widget.resize(600, 300)
    widget.show()
    qtbot.waitExposed(widget)
    widget.feed(b"word here")
    widget.flush_pending()
    cw, ch = widget.cell_size
    qtbot.mouseDClick(
        widget, Qt.MouseButton.LeftButton, pos=QPoint(int(PADDING + cw + 1), int(PADDING + ch / 2))
    )
    assert fake.data[QClipboard.Mode.Selection] == "word"
    assert fake.data[QClipboard.Mode.Clipboard] == ""


def test_middle_click_without_selection_support_does_nothing(term: TerminalWidget, qtbot) -> None:
    sent = _record(term.input_bytes)
    qtbot.mouseClick(term, Qt.MouseButton.MiddleButton, pos=QPoint(20, 10))
    assert sent == []
