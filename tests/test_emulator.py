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
