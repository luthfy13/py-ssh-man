"""Tests for terminal.emulator (SPEC §8.1, §10.2)."""

from __future__ import annotations

import pytest

from pyssh.terminal.emulator import TerminalEmulator


def _emu(cols: int = 20, rows: int = 5, scrollback: int = 100, responses=None):
    return TerminalEmulator(cols, rows, scrollback, on_response=responses)


def test_basic_text() -> None:
    emu = _emu()
    emu.feed(b"hello\r\nworld")
    assert emu.screen_lines_text()[:2] == ["hello", "world"]
    assert emu.cursor.x == 5 and emu.cursor.y == 1 and emu.cursor.visible
    assert (emu.cols, emu.rows) == (20, 5)


def test_sgr_red() -> None:
    emu = _emu()
    emu.feed(b"\x1b[31mR\x1b[0mN")
    line = emu.line_at(0)
    assert line[0].fg == "red"
    assert line[1].fg == "default"


def test_256_and_truecolor() -> None:
    emu = _emu()
    emu.feed(b"\x1b[38;5;196mA\x1b[48;5;21mB\x1b[38;2;1;2;3mC")
    line = emu.line_at(0)
    assert line[0].fg == "ff0000"
    assert line[1].bg == "0000ff"
    assert line[2].fg == "010203"


def test_attributes() -> None:
    emu = _emu()
    emu.feed(b"\x1b[1;3;4;7;9mX")
    char = emu.line_at(0)[0]
    assert (char.bold, char.italics, char.underscore, char.reverse, char.strikethrough) == (
        True,
        True,
        True,
        True,
        True,
    )


def test_decckm() -> None:
    emu = _emu()
    assert emu.app_cursor_keys is False
    emu.feed(b"\x1b[?1h")
    assert emu.app_cursor_keys is True
    emu.feed(b"\x1b[?1l")
    assert emu.app_cursor_keys is False


def test_bracketed_paste_mode() -> None:
    emu = _emu()
    emu.feed(b"\x1b[?2004h")
    assert emu.bracketed_paste is True
    emu.feed(b"\x1b[?2004l")
    assert emu.bracketed_paste is False


def test_cursor_visibility() -> None:
    emu = _emu()
    emu.feed(b"\x1b[?25l")
    assert emu.cursor.visible is False
    emu.feed(b"\x1b[?25h")
    assert emu.cursor.visible is True


def test_dsr_response() -> None:
    responses: list[bytes] = []
    emu = _emu(responses=responses.append)
    emu.feed(b"\x1b[6n")
    assert responses == [b"\x1b[1;1R"]
    emu.feed(b"ab\x1b[6n")
    assert responses[-1] == b"\x1b[1;3R"


def test_device_attributes_response() -> None:
    responses: list[bytes] = []
    emu = _emu(responses=responses.append)
    emu.feed(b"\x1b[c")
    assert responses == [b"\x1b[?6c"]


def test_no_response_callback_is_fine() -> None:
    _emu().feed(b"\x1b[6n")


def test_title() -> None:
    emu = _emu()
    emu.feed(b"\x1b]0;judul sesi\x07")
    assert emu.title == "judul sesi"


def test_scrollback_full() -> None:
    emu = TerminalEmulator(20, 10, 50)
    emu.feed(b"".join(b"line %d\r\n" % i for i in range(100)))
    assert emu.history_len == 50
    assert emu.scrollback_limit == 50
    assert emu.total_lines == 60
    # 100 lines + trailing newline: the last 9 written lines plus an empty row are visible.
    assert emu.screen_lines_text()[-2] == "line 99"
    assert emu.line_text(0).rstrip() == "line 41"
    assert emu.line_text(49).rstrip() == "line 90"


def test_scrollback_order_small() -> None:
    emu = TerminalEmulator(10, 3, 100)
    emu.feed(b"a\r\nb\r\nc\r\nd\r\ne")
    assert emu.history_len == 2
    assert [emu.line_text(i).rstrip() for i in range(emu.total_lines)] == ["a", "b", "c", "d", "e"]


def test_partial_scroll_region_not_in_scrollback() -> None:
    emu = TerminalEmulator(10, 5, 100)
    emu.feed(b"\x1b[2;4r")  # scroll region rows 2..4
    emu.feed(b"\x1b[4;1H")  # bottom of region
    emu.feed(b"x\r\n" * 10)
    assert emu.history_len == 0
    emu.feed(b"\x1b[r\x1b[5;1H" + b"y\r\n" * 3)  # full region again
    assert emu.history_len == 3


def test_visible_range() -> None:
    emu = TerminalEmulator(10, 3, 100)
    emu.feed(b"1\r\n2\r\n3\r\n4\r\n5")
    assert emu.visible_range(0) == range(2, 5)
    assert emu.visible_range(2) == range(0, 3)


def test_line_at_bounds() -> None:
    emu = _emu()
    with pytest.raises(IndexError):
        emu.line_at(-1)
    with pytest.raises(IndexError):
        emu.line_at(emu.total_lines)


def test_resize() -> None:
    emu = _emu(20, 5)
    emu.feed(b"hello")
    emu.resize(30, 8)
    assert (emu.cols, emu.rows) == (30, 8)
    assert emu.screen_lines_text()[0] == "hello"
    emu.resize(3, 8)
    assert emu.screen_lines_text()[0] == "hel"


def test_wide_characters_use_two_cells() -> None:
    emu = _emu()
    emu.feed("漢字x".encode())
    line = emu.line_at(0)
    assert [line[i].data for i in range(5)] == ["漢", "", "字", "", "x"]
    assert emu.cursor.x == 5
    assert emu.screen_lines_text()[0] == "漢字x"


def test_utf8_split_across_feeds() -> None:
    emu = _emu()
    emu.feed(b"\xe2\x82")
    emu.feed(b"\xac")
    assert emu.screen_lines_text()[0] == "€"


def test_text_between() -> None:
    emu = TerminalEmulator(10, 3, 100)
    emu.feed(b"abcdef\r\nghij  \r\nklm")
    assert emu.text_between((0, 1), (0, 4)) == "bcd"
    assert emu.text_between((0, 4), (2, 2)) == "ef\nghij\nkl"
    assert emu.text_between((2, 2), (0, 4)) == "ef\nghij\nkl"  # reversed order
    assert emu.text_between((1, 0), (1, 10)) == "ghij"  # right-stripped
    assert emu.text_between((0, 0), (0, 0)) == ""


def test_text_between_includes_scrollback() -> None:
    emu = TerminalEmulator(10, 2, 100)
    emu.feed(b"one\r\ntwo\r\nthree")
    assert emu.history_len == 1
    assert emu.text_between((0, 0), (2, 5)) == "one\ntwo\nthree"


def test_clear_scrollback() -> None:
    emu = TerminalEmulator(10, 2, 100)
    emu.feed(b"1\r\n2\r\n3\r\n4")
    assert emu.history_len > 0
    emu.clear_scrollback()
    assert emu.history_len == 0
    assert emu.screen_lines_text() == ["3", "4"]


def test_alternate_screen_restores_main_screen() -> None:
    """AC-8.3: ESC[?1049h + text + ESC[?1049l restores the previous screen."""
    emu = TerminalEmulator(20, 5, 100)
    emu.feed(b"prompt$ vim file\r\nline two")
    before_text = emu.screen_lines_text()
    before_cursor = emu.cursor
    emu.feed(b"\x1b[?1049h")
    assert emu.in_alt_screen
    assert emu.screen_lines_text() == [""] * 5
    emu.feed(b"\x1b[2J\x1b[H~\r\n~\r\nVIM TEXT")
    assert "VIM TEXT" in emu.screen_lines_text()
    emu.feed(b"\x1b[?1049l")
    assert not emu.in_alt_screen
    assert emu.screen_lines_text() == before_text
    assert emu.cursor == before_cursor


@pytest.mark.parametrize("mode", [b"47", b"1047", b"1049"])
def test_alternate_screen_modes(mode: bytes) -> None:
    emu = TerminalEmulator(20, 3, 100)
    emu.feed(b"main")
    # Like xterm, entering keeps the cursor position; applications home it themselves.
    emu.feed(b"\x1b[?" + mode + b"h")
    assert emu.cursor.x == 4
    emu.feed(b"\x1b[Halt")
    assert emu.screen_lines_text()[0] == "alt"
    emu.feed(b"\x1b[?" + mode + b"l")
    assert emu.screen_lines_text()[0] == "main"


def test_alternate_screen_does_not_fill_scrollback() -> None:
    emu = TerminalEmulator(20, 3, 100)
    emu.feed(b"a\r\nb\r\nc\r\nd")  # 1 line into scrollback
    history = emu.history_len
    emu.feed(b"\x1b[?1049h" + b"x\r\n" * 50)
    assert emu.history_len == history
    emu.feed(b"\x1b[?1049l")
    assert emu.history_len == history


def test_alternate_screen_enter_twice_and_leave_without_enter() -> None:
    emu = TerminalEmulator(20, 3, 100)
    emu.feed(b"keep")
    emu.feed(b"\x1b[?1049l")  # leaving without entering: no change
    assert emu.screen_lines_text()[0] == "keep"
    emu.feed(b"\x1b[?1049h\x1b[?1049h")  # entering twice keeps the first saved screen
    emu.feed(b"\x1b[?1049l")
    assert emu.screen_lines_text()[0] == "keep"


def test_alternate_screen_with_other_modes_in_same_sequence() -> None:
    emu = TerminalEmulator(20, 3, 100)
    emu.feed(b"\x1b[?1049;1h")  # alt screen + DECCKM together
    assert emu.in_alt_screen and emu.app_cursor_keys
    emu.feed(b"\x1b[?1049;1l")
    assert not emu.in_alt_screen and not emu.app_cursor_keys


def test_alternate_screen_survives_shrinking() -> None:
    emu = TerminalEmulator(20, 6, 100)
    emu.feed(b"1\r\n2\r\n3\r\n4\r\n5\r\n6")
    emu.feed(b"\x1b[?1049h")
    emu.resize(20, 3)
    emu.feed(b"\x1b[?1049l")
    assert len(emu.screen_lines_text()) == 3
    assert emu.cursor.y <= 2


@pytest.mark.parametrize("final", list("@ABCDEFGHLMPXadefgmnr'"))
def test_private_csi_variants_do_not_break_parsing(final: str) -> None:
    """pyte 0.8.2 raises TypeError for e.g. ESC[?1;2m; the rest of the data must survive."""
    emu = TerminalEmulator(20, 3, 100)
    emu.feed(b"ok\x1b[?1;2" + final.encode() + b"-after")
    assert emu.screen_lines_text()[0] == "ok-after"


def test_parser_errors_are_logged_not_raised(monkeypatch, caplog) -> None:
    import logging

    emu = TerminalEmulator(20, 3, 100)

    def boom(data: bytes) -> None:
        raise RuntimeError("secret-ish payload")

    monkeypatch.setattr(emu._stream, "feed", boom)
    with caplog.at_level(logging.WARNING):
        emu.feed(b"anything")
    assert "terminal parser error: RuntimeError" in caplog.text
    assert "payload" not in caplog.text
