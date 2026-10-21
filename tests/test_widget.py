"""Tests for terminal.widget and terminal.view (SPEC §8.4, §8.5, §10.2)."""

from __future__ import annotations

from dataclasses import replace

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QInputMethodEvent, QWheelEvent
from PySide6.QtWidgets import QApplication

from pyssh import shortcuts, strings
from pyssh.models import AppSettings
from pyssh.terminal import widget as widget_module
from pyssh.terminal.colors import Theme
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
    row = shortcuts.shortcut_rows("new_session")[0]  # Ctrl+Shift+N, or Cmd+N on macOS
    new_session = QKeyEvent(QEvent.Type.ShortcutOverride, min(row.keys), row.mods, "")
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
    row = shortcuts.shortcut_rows("paste")[0]  # Ctrl+Shift+V, or Cmd+V on macOS
    qtbot.keyClick(term, Qt.Key(min(row.keys)), row.mods)
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
    zoom = shortcuts.zoom_wheel_modifier()  # Ctrl, or Cmd on macOS
    sizes = _record(term.font_size_changed)
    _wheel(term, 120, zoom)
    assert term.font_size == 12
    _wheel(term, -120, zoom)
    _wheel(term, -120, zoom)
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


# ----- shell prompt highlight (design B.3, B.5) --------------------------------------------
#
# Colors are observed through the widget's own run/style helper (``_runs``): it yields, for
# every screen row, the (fg, bg, bold, italics, underscore, strikethrough) that ``paintEvent``
# draws each cell with. That is exact and independent of fonts; a few tests also look at the
# pixels of ``grab()``.

_THEME = Theme()
_PLAIN = (_THEME.foreground, _THEME.background, False, False, False, False)
_USERHOST = (_THEME.ansi[10], _THEME.background, True, False, False, False)  # bright green, bold
_PATH = (_THEME.ansi[12], _THEME.background, True, False, False, False)  # bright blue, bold
_PROMPT = "root@Server-OBE-UMI:~# "  # userhost = columns 0-18, ':' = 19, path = 20, '#' = 21


def _prompt_term(qtbot, theme: Theme | None = None, **settings) -> TerminalWidget:
    widget = TerminalWidget(replace(AppSettings(), **settings), theme)
    qtbot.addWidget(widget)
    widget.resize(800, 400)
    widget.show()
    qtbot.waitExposed(widget)
    return widget


def _show(widget: TerminalWidget, text: str | bytes) -> None:
    widget.feed(text.encode() if isinstance(text, str) else text)
    widget.flush_pending()


def _row_styles(widget: TerminalWidget, row: int, selection=None) -> list[tuple]:
    """Style drawn for each column of screen row ``row`` (a wide character fills both columns)."""
    styles: list[tuple] = [()] * widget.emulator.cols
    for run in widget._runs(widget.emulator.history_len + row, selection):
        for col, _data, width in run.cells:
            for x in range(col, col + width):
                styles[x] = run.style
    return styles


@pytest.fixture
def prompt_term(qtbot) -> TerminalWidget:
    return _prompt_term(qtbot)


def test_highlight_prompt_is_on_by_default() -> None:
    assert AppSettings().highlight_prompt is True


def test_prompt_userhost_and_path_are_bright_green_and_blue_bold(prompt_term) -> None:
    _show(prompt_term, _PROMPT + "ls -la")
    styles = _row_styles(prompt_term, 0)
    assert styles[0:19] == [_USERHOST] * 19  # root@Server-OBE-UMI
    assert styles[19] == _PLAIN  # ':'
    assert styles[20] == _PATH  # '~'
    assert styles[21:] == [_PLAIN] * (len(styles) - 21)  # '# ls -la' and the empty rest


def test_prompt_colors_come_from_the_theme(qtbot) -> None:
    ansi = tuple(f"#{(index + 1) * 10:02X}{index:02X}00" for index in range(16))
    theme = Theme(ansi=ansi)
    widget = _prompt_term(qtbot, theme)
    _show(widget, _PROMPT)
    styles = _row_styles(widget, 0)
    assert styles[0] == (ansi[10], theme.background, True, False, False, False)
    assert styles[20] == (ansi[12], theme.background, True, False, False, False)
    assert ansi[10] != _THEME.ansi[10] and ansi[12] != _THEME.ansi[12]


@pytest.mark.parametrize("bold_is_bright", [True, False])
def test_prompt_colors_do_not_depend_on_bold_is_bright(qtbot, bold_is_bright: bool) -> None:
    widget = _prompt_term(qtbot, bold_is_bright=bold_is_bright)
    _show(widget, _PROMPT)
    styles = _row_styles(widget, 0)
    assert styles[0] == _USERHOST
    assert styles[20] == _PATH


@pytest.mark.parametrize(
    ("line", "userhost", "path"),
    [
        ("user@host:~$ ", (0, 9), (10, 11)),
        ("root@host:/etc# ", (0, 9), (10, 14)),
        ("[user@host ~/a/b]$ ", (1, 10), (11, 16)),
        ("[root@host ~]# ", (1, 10), (11, 12)),
        ("user@host ~ % ", (0, 9), (10, 11)),
        ("(venv) user@host:~$ ", (7, 16), (17, 18)),
        ("(base) [user@host ~]$ ", (8, 17), (18, 19)),
        ("(venv) user@host ~/src % ", (7, 16), (17, 22)),
    ],
)
def test_each_prompt_shape_is_colored_in_the_right_columns(
    prompt_term, line: str, userhost: tuple[int, int], path: tuple[int, int]
) -> None:
    _show(prompt_term, line + "echo hi")
    styles = _row_styles(prompt_term, 0)
    for x, style in enumerate(styles):
        if userhost[0] <= x < userhost[1]:
            assert style == _USERHOST, x
        elif path[0] <= x < path[1]:
            assert style == _PATH, x
        else:
            assert style == _PLAIN, x


def test_every_visible_row_is_checked(prompt_term) -> None:
    rows = prompt_term.emulator.rows
    _show(prompt_term, "\r\n".join(f"user@host:~/d{n}$ ls" for n in range(rows)))
    for row in range(rows):
        styles = _row_styles(prompt_term, row)
        assert styles[0] == _USERHOST, row
        assert styles[8] == _USERHOST, row
        assert styles[9] == _PLAIN, row
        assert styles[10] == _PATH, row
        assert styles[-1] == _PLAIN, row


def test_prompt_in_scrollback_is_colored_too(prompt_term) -> None:
    emulator = prompt_term.emulator
    _show(prompt_term, "\r\n".join(f"user@host:~$ echo {n}" for n in range(emulator.rows + 15)))
    assert emulator.history_len >= 10
    for line_index in (0, 5, emulator.history_len - 1):
        run = prompt_term._runs(line_index, None)[0]
        assert run.style == _USERHOST
        assert (run.start, run.end) == (0, 9)
    prompt_term.scroll_by(8)
    assert not prompt_term.grab().isNull()


def test_non_prompt_text_stays_plain(prompt_term) -> None:
    lines = [
        "hello world",
        "echo root@host:~# ",
        "write to a@b.com now",
        "root@host",
        "root@host:~",
        " root@host:~# ",
        "root@host:~#x",
    ]
    _show(prompt_term, "\r\n".join(lines))
    for row in range(len(lines)):
        assert _row_styles(prompt_term, row) == [_PLAIN] * prompt_term.emulator.cols, lines[row]


def test_style_cache_does_not_leak_between_prompt_and_other_cells(prompt_term) -> None:
    """Same characters and attributes, with and without the prompt override."""
    _show(prompt_term, "root@host\r\nroot@host:~# \r\nroot@host")
    for _ in range(2):  # the second round runs with warm style caches
        assert _row_styles(prompt_term, 0)[0] == _PLAIN
        assert _row_styles(prompt_term, 1)[0] == _USERHOST
        assert _row_styles(prompt_term, 1)[10] == _PATH
        assert _row_styles(prompt_term, 2)[0] == _PLAIN


def test_overwriting_the_prompt_removes_its_colors(prompt_term) -> None:
    _show(prompt_term, "root@host:~# ls")
    assert _row_styles(prompt_term, 0)[0] == _USERHOST
    _show(prompt_term, "\r\x1b[2Kplain text")
    assert _row_styles(prompt_term, 0) == [_PLAIN] * prompt_term.emulator.cols


def test_prompt_after_a_wide_character_path(prompt_term) -> None:
    _show(prompt_term, "user@host:~/漢字$ ls")  # '漢' = columns 12-13, '字' = 14-15, '$' = 16
    styles = _row_styles(prompt_term, 0)
    assert styles[0:9] == [_USERHOST] * 9
    assert styles[10:16] == [_PATH] * 6
    assert styles[16] == _PLAIN
    assert styles[17] == _PLAIN


def test_wide_characters_before_the_prompt_shift_the_columns(prompt_term) -> None:
    _show(prompt_term, "(漢字) user@host:~$ ")  # '(' + 4 columns + ')' + ' ' = 7 columns
    styles = _row_styles(prompt_term, 0)
    assert styles[0:7] == [_PLAIN] * 7
    assert styles[7:16] == [_USERHOST] * 9
    assert styles[16] == _PLAIN
    assert styles[17] == _PATH
    assert styles[18] == _PLAIN


def test_bold_without_colors_from_the_server_is_still_highlighted(prompt_term) -> None:
    _show(prompt_term, "\x1b[1muser@host\x1b[0m:\x1b[1m~\x1b[0m$ ")
    styles = _row_styles(prompt_term, 0)
    assert styles[0] == _USERHOST
    assert styles[10] == _PATH


_SERVER_COLOR_SGR = [
    "31",  # foreground
    "1;31",  # bold foreground
    "01;32",  # the Ubuntu default
    "44",  # background
    "37;41",
    "7",  # reverse
    "38;5;208",  # 256 colors
    "48;5;100",
    "38;2;10;20;30",  # true color
    "48;2;200;100;50",
]


@pytest.mark.parametrize("sgr", _SERVER_COLOR_SGR)
def test_cells_colored_by_the_server_are_not_changed(qtbot, sgr: str) -> None:
    data = f"\x1b[{sgr}muser@host\x1b[0m:\x1b[{sgr}m~/src\x1b[0m$ ls"
    on = _prompt_term(qtbot)
    off = _prompt_term(qtbot, highlight_prompt=False)
    _show(on, data)
    _show(off, data)
    styles = _row_styles(on, 0)
    assert styles == _row_styles(off, 0)
    assert styles[0] != _PLAIN  # the server's colors are still there
    assert styles[10] != _PLAIN
    assert styles[9] == _PLAIN  # the ':' had no server colors and is not in a span


def test_server_colors_are_kept_without_bright_bold(qtbot) -> None:
    data = "\x1b[01;32muser@host\x1b[00m:\x1b[01;34m~\x1b[00m$ "
    on = _prompt_term(qtbot, bold_is_bright=False)
    off = _prompt_term(qtbot, bold_is_bright=False, highlight_prompt=False)
    _show(on, data)
    _show(off, data)
    styles = _row_styles(on, 0)
    assert styles == _row_styles(off, 0)
    assert styles[0] == (_THEME.ansi[2], _THEME.background, True, False, False, False)
    assert styles[10] == (_THEME.ansi[4], _THEME.background, True, False, False, False)


def test_only_the_uncolored_cells_of_a_partly_colored_prompt_change(prompt_term) -> None:
    _show(prompt_term, "us\x1b[31mer\x1b[0m@host:~$ ")
    styles = _row_styles(prompt_term, 0)
    red = (_THEME.ansi[1], _THEME.background, False, False, False, False)
    assert styles[0:2] == [_USERHOST] * 2
    assert styles[2:4] == [red] * 2
    assert styles[4:9] == [_USERHOST] * 5
    assert styles[10] == _PATH


def test_colored_userhost_and_plain_path(prompt_term) -> None:
    _show(prompt_term, "\x1b[35muser@host\x1b[0m:~$ ")
    styles = _row_styles(prompt_term, 0)
    assert styles[0] == (_THEME.ansi[5], _THEME.background, False, False, False, False)
    assert styles[10] == _PATH


def test_selection_still_sets_the_background(prompt_term) -> None:
    _show(prompt_term, "root@host:~# ls")
    line = prompt_term.emulator.history_len
    prompt_term.set_selection((line, 0), (line, 12))
    styles = _row_styles(prompt_term, 0, prompt_term.selection_range())
    selected = _THEME.selection
    assert styles[0] == (_THEME.ansi[10], selected, True, False, False, False)
    assert styles[10] == (_THEME.ansi[12], selected, True, False, False, False)
    assert styles[11] == (_THEME.foreground, selected, False, False, False, False)  # ':' ... '#'
    assert styles[12] == _PLAIN  # outside the selection
    assert prompt_term.selected_text() == "root@host:~#"


def test_no_highlight_in_the_alternate_screen(prompt_term) -> None:
    _show(prompt_term, "root@host:~# vim\r\n")
    assert _row_styles(prompt_term, 0)[0] == _USERHOST
    _show(prompt_term, "\x1b[?1049h\x1b[H" + "root@host:~# looks like a prompt\r\n[a@b ~]$ x")
    assert prompt_term.emulator.in_alt_screen
    for row in (0, 1):
        assert _row_styles(prompt_term, row) == [_PLAIN] * prompt_term.emulator.cols
    _show(prompt_term, "\x1b[?1049l")
    assert not prompt_term.emulator.in_alt_screen
    assert _row_styles(prompt_term, 0)[0] == _USERHOST  # the main screen is highlighted again


def test_highlight_off_draws_prompts_plain(qtbot) -> None:
    widget = _prompt_term(qtbot, highlight_prompt=False)
    _show(widget, _PROMPT + "ls\r\n[user@host ~]$ x\r\nuser@host ~ % y")
    for row in range(3):
        assert _row_styles(widget, row) == [_PLAIN] * widget.emulator.cols


def test_apply_settings_toggles_the_highlight_at_once(prompt_term) -> None:
    _show(prompt_term, _PROMPT)
    assert _row_styles(prompt_term, 0)[0] == _USERHOST
    prompt_term.apply_settings(replace(AppSettings(), highlight_prompt=False))
    assert _row_styles(prompt_term, 0) == [_PLAIN] * prompt_term.emulator.cols
    prompt_term.apply_settings(replace(AppSettings(), highlight_prompt=True))
    assert _row_styles(prompt_term, 0)[0] == _USERHOST
    assert _row_styles(prompt_term, 0)[20] == _PATH


def test_copied_text_and_terminal_data_are_unchanged(qtbot) -> None:
    text = _PROMPT + "ls -la"
    on = _prompt_term(qtbot)
    off = _prompt_term(qtbot, highlight_prompt=False)
    sent = _record(on.input_bytes)
    for widget in (on, off):
        _show(widget, text)
        line = widget.emulator.history_len
        widget.set_selection((line, 0), (line, 40))
        assert widget.selected_text() == text
        assert widget.copy_selection()
        assert QGuiApplication.clipboard().text() == text
        assert not widget.grab().isNull()
    assert on.emulator.screen_lines_text() == off.emulator.screen_lines_text()
    assert on.emulator.screen_lines_text()[0] == text
    cell = on.emulator.line_at(on.emulator.history_len)[0]
    assert (cell.fg, cell.bg, cell.bold) == ("default", "default", False)  # data not changed
    assert sent == []  # nothing is sent to the server


def _glyph_pixels(widget: TerminalWidget, image, row: int, start: int, end: int) -> list:
    """Colors of all pixels of ``row`` between columns ``start`` and ``end`` (exclusive)."""
    cw, ch = widget.cell_size
    ratio = image.devicePixelRatio()
    x0, x1 = int((PADDING + start * cw) * ratio), int((PADDING + end * cw) * ratio)
    y0, y1 = int((PADDING + row * ch) * ratio), int((PADDING + (row + 1) * ch) * ratio)
    return [image.pixelColor(x, y) for y in range(y0, y1) for x in range(x0, x1)]


def _tint(pixels: list, channel: str) -> int:
    """How much more ``channel`` ("g" or "b") the pixels have than the mean of the other two.

    Gray text, even with sub-pixel antialiasing fringes, adds up to about zero; text drawn in
    bright green (or blue) adds up to a large positive number.
    """
    total = 0
    for color in pixels:
        r, g, b = color.red(), color.green(), color.blue()
        total += g - (r + b) // 2 if channel == "g" else b - (r + g) // 2
    return total


def test_painted_pixels_show_the_prompt_colors(qtbot) -> None:
    widget = _prompt_term(qtbot, highlight_prompt=False)
    line = "root@Server-OBE-UMI:/usr/local/share# ls"  # userhost 0-18, path 20-35
    _show(widget, line)
    off = widget.grab().toImage()
    background = QColor(_THEME.background)
    if all(c == background for c in _glyph_pixels(widget, off, 0, 0, 36)):
        pytest.skip("this platform plugin draws no glyphs (no fonts)")
    userhost_off = _tint(_glyph_pixels(widget, off, 0, 0, 19), "g")
    path_off = _tint(_glyph_pixels(widget, off, 0, 20, 36), "b")
    assert abs(userhost_off) < 5_000
    assert abs(path_off) < 5_000

    widget.apply_settings(replace(AppSettings(), highlight_prompt=True))
    on = widget.grab().toImage()
    assert _tint(_glyph_pixels(widget, on, 0, 0, 19), "g") - userhost_off > 20_000
    assert _tint(_glyph_pixels(widget, on, 0, 20, 36), "b") - path_off > 15_000
    assert abs(_tint(_glyph_pixels(widget, on, 0, 36, 40), "g")) < 5_000  # '# ls' stays plain
    assert on != off
    # Only the prompt cells differ between the images: the rows below are identical.
    below = int((PADDING + widget.cell_size[1]) * on.devicePixelRatio()) + 1
    assert on.copy(0, below, on.width(), on.height() - below) == off.copy(
        0, below, off.width(), off.height() - below
    )

    widget.apply_settings(replace(AppSettings(), highlight_prompt=False))
    assert widget.grab().toImage() == off


@pytest.mark.parametrize(
    "data",
    [
        b"\x1b[?1049hroot@host:~# looks like a prompt",  # alternate screen
        b"plain output\r\n a@b.com\r\n [user@host ~]$ ls",  # no prompt at column 0
        b"\x1b[32muser@host\x1b[0m:\x1b[34m~\x1b[0m$ ls",  # colored by the server
    ],
    ids=["alt-screen", "no-prompt", "server-colors"],
)
def test_image_is_identical_with_and_without_the_feature(qtbot, data: bytes) -> None:
    on = _prompt_term(qtbot)
    off = _prompt_term(qtbot, highlight_prompt=False)
    _show(on, data)
    _show(off, data)
    assert on.grab().toImage() == off.grab().toImage()
