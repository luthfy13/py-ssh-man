"""Tests for the scroll sequences SU/SD, REP and CBT of terminal.emulator (DESAIN-TERMINAL §A).

nano (ncurses) scrolls with ``CSI n S`` / ``CSI n T`` when several Down/Up keys arrive at once;
pyte 0.8.2 ignores both finals, which left stale lines on screen. SU, SD, REP (``CSI n b``) and
CBT (``CSI n Z``) are therefore handled by the emulator itself.

The unit tests below follow the specification only. The regression tests replay recordings of a
real nano 7.2 (``tests/data/*.bin``, made by ``tools/record_nano_scroll.py``).

Round 2 (§D): the handlers must accept any number of parameters (``CSI ? 1 ; 1 ; 0 S`` raised a
``TypeError`` that swallowed the rest of the chunk, including the replies to DA / DSR), and
``CSI > …`` sequences are discarded because pyte drops the ``>`` and would run them as the plain
sequence (``CSI > 4 ; 2 m`` underlined all later text). Those cases also run with the stream cut at
every position.
"""

from __future__ import annotations

import logging
import random
import re
from itertools import pairwise
from pathlib import Path

import pytest

from pyssh.terminal.emulator import TerminalEmulator

CSI = b"\x1b["
DATA = Path(__file__).parent / "data"


def _emu(
    cols: int = 20, rows: int = 5, scrollback: int = 100, on_response=None
) -> TerminalEmulator:
    return TerminalEmulator(cols, rows, scrollback, on_response=on_response)


def _numbered(
    rows: int = 5, cols: int = 20, scrollback: int = 100, on_response=None
) -> TerminalEmulator:
    """Emulator whose rows hold ``L0`` ... ``L<rows-1>``; the cursor ends on the last row."""
    emu = _emu(cols, rows, scrollback, on_response)
    emu.feed(b"\r\n".join(b"L%d" % n for n in range(rows)))
    assert emu.screen_lines_text() == [f"L{n}" for n in range(rows)]
    assert emu.history_len == 0
    return emu


def _history(emu: TerminalEmulator) -> list[str]:
    return [emu.line_text(i).rstrip() for i in range(emu.history_len)]


def _region(top: int, bottom: int) -> bytes:
    """DECSTBM for the 0-based rows ``top`` .. ``bottom`` (the cursor goes home)."""
    return CSI + b"%d;%dr" % (top + 1, bottom + 1)


def _goto(row: int, col: int) -> bytes:
    """CUP to the 0-based ``row`` / ``col``."""
    return CSI + b"%d;%dH" % (row + 1, col + 1)


# --- SU (CSI n S) ---------------------------------------------------------------------------


def test_su_default_scrolls_one_line() -> None:
    emu = _numbered()
    emu.feed(CSI + b"S")
    assert emu.screen_lines_text() == ["L1", "L2", "L3", "L4", ""]


def test_su_count() -> None:
    emu = _numbered()
    emu.feed(CSI + b"2S")
    assert emu.screen_lines_text() == ["L2", "L3", "L4", "", ""]


def test_su_zero_counts_as_one() -> None:
    emu = _numbered()
    emu.feed(CSI + b"0S")
    assert emu.screen_lines_text() == ["L1", "L2", "L3", "L4", ""]


def test_su_count_larger_than_region_clears_it() -> None:
    emu = _numbered()
    emu.feed(CSI + b"99S")
    assert emu.screen_lines_text() == [""] * 5
    assert _history(emu) == ["L0", "L1", "L2", "L3", "L4"]  # no more than the region height


def test_su_inside_partial_region_leaves_other_rows_alone() -> None:
    emu = _numbered()
    emu.feed(_region(1, 3) + _goto(2, 4) + CSI + b"S")
    assert emu.screen_lines_text() == ["L0", "L2", "L3", "", "L4"]
    emu.feed(CSI + b"2S")
    assert emu.screen_lines_text() == ["L0", "", "", "", "L4"]


def test_su_count_larger_than_partial_region_clears_only_the_region() -> None:
    emu = _numbered()
    emu.feed(_region(1, 3) + _goto(1, 0) + CSI + b"99S")
    assert emu.screen_lines_text() == ["L0", "", "", "", "L4"]


def test_su_keeps_the_cursor_where_it_is() -> None:
    emu = _numbered()
    emu.feed(_goto(2, 7) + CSI + b"2S")
    assert (emu.cursor.x, emu.cursor.y) == (7, 2)
    emu.feed(_region(1, 3) + _goto(3, 9) + CSI + b"S")  # on the region's bottom margin
    assert (emu.cursor.x, emu.cursor.y) == (9, 3)
    emu.feed(_goto(0, 5) + CSI + b"S")  # outside the region
    assert (emu.cursor.x, emu.cursor.y) == (5, 0)
    emu.feed(_goto(4, 6) + CSI + b"S")  # outside the region, below it
    assert (emu.cursor.x, emu.cursor.y) == (6, 4)


def test_su_outside_the_region_does_not_change_the_other_rows() -> None:
    emu = _numbered()
    emu.feed(_region(1, 3) + _goto(4, 0) + CSI + b"S")
    assert emu.screen_lines_text() == ["L0", "L2", "L3", "", "L4"]


def test_su_full_screen_on_main_screen_fills_scrollback() -> None:
    emu = _numbered()
    emu.feed(CSI + b"2S")
    assert _history(emu) == ["L0", "L1"]
    assert emu.scrolled_total == 2
    emu.feed(CSI + b"S")
    assert _history(emu) == ["L0", "L1", "L2"]
    assert emu.scrolled_total == 3


def test_su_matches_line_feeds_at_the_bottom_margin() -> None:
    by_su = _numbered()
    by_su.feed(CSI + b"3S")
    by_lf = _numbered()
    by_lf.feed(_goto(4, 0) + b"\n\n\n")
    assert by_su.screen_lines_text() == by_lf.screen_lines_text()
    assert _history(by_su) == _history(by_lf)
    assert by_su.scrolled_total == by_lf.scrolled_total == 3


def test_su_in_partial_region_does_not_fill_scrollback() -> None:
    emu = _numbered()
    emu.feed(_region(1, 3) + _goto(3, 0) + CSI + b"2S")
    assert emu.history_len == 0
    assert emu.scrolled_total == 0


def test_su_in_alt_screen_does_not_fill_scrollback() -> None:
    emu = _numbered()
    emu.feed(b"\r\nextra\r\nmore")  # main screen scrolls twice -> real history
    before = emu.history_len
    assert before == 2
    emu.feed(b"\x1b[?1049h")
    assert emu.in_alt_screen
    emu.feed(_goto(0, 0) + b"\r\n".join(b"A%d" % n for n in range(5)))
    emu.feed(CSI + b"2S")
    assert emu.screen_lines_text() == ["A2", "A3", "A4", "", ""]
    assert emu.history_len == before
    emu.feed(b"\x1b[?1049l")
    assert not emu.in_alt_screen
    assert emu.history_len == before


def test_su_private_variant_is_ignored() -> None:
    emu = _numbered()
    emu.feed(_goto(2, 3))
    before = (emu.screen_lines_text(), emu.cursor, emu.history_len)
    emu.feed(CSI + b"?2S")
    emu.feed(CSI + b"?S")
    assert (emu.screen_lines_text(), emu.cursor, emu.history_len) == before


def test_su_marks_the_region_dirty() -> None:
    emu = _numbered()
    emu.feed(_region(1, 3) + _goto(1, 0))
    emu.screen.dirty.clear()
    emu.feed(CSI + b"S")
    assert {1, 2, 3} <= set(emu.screen.dirty)


def test_su_split_over_several_feeds() -> None:
    emu = _numbered()
    for piece in (b"\x1b", b"[", b"2", b"S"):
        emu.feed(piece)
    assert emu.screen_lines_text() == ["L2", "L3", "L4", "", ""]


# --- SD (CSI n T) ---------------------------------------------------------------------------


def test_sd_default_scrolls_one_line() -> None:
    emu = _numbered()
    emu.feed(CSI + b"T")
    assert emu.screen_lines_text() == ["", "L0", "L1", "L2", "L3"]


def test_sd_count() -> None:
    emu = _numbered()
    emu.feed(CSI + b"2T")
    assert emu.screen_lines_text() == ["", "", "L0", "L1", "L2"]


def test_sd_zero_counts_as_one() -> None:
    emu = _numbered()
    emu.feed(CSI + b"0T")
    assert emu.screen_lines_text() == ["", "L0", "L1", "L2", "L3"]


def test_sd_count_larger_than_region_clears_it() -> None:
    emu = _numbered()
    emu.feed(CSI + b"99T")
    assert emu.screen_lines_text() == [""] * 5


def test_sd_inside_partial_region_leaves_other_rows_alone() -> None:
    emu = _numbered()
    emu.feed(_region(1, 3) + _goto(2, 4) + CSI + b"T")
    assert emu.screen_lines_text() == ["L0", "", "L1", "L2", "L4"]
    emu.feed(CSI + b"2T")
    assert emu.screen_lines_text() == ["L0", "", "", "", "L4"]


def test_sd_count_larger_than_partial_region_clears_only_the_region() -> None:
    emu = _numbered()
    emu.feed(_region(1, 3) + _goto(3, 0) + CSI + b"99T")
    assert emu.screen_lines_text() == ["L0", "", "", "", "L4"]


def test_sd_keeps_the_cursor_where_it_is() -> None:
    emu = _numbered()
    emu.feed(_goto(2, 7) + CSI + b"2T")
    assert (emu.cursor.x, emu.cursor.y) == (7, 2)
    emu.feed(_region(1, 3) + _goto(1, 9) + CSI + b"T")  # on the region's top margin
    assert (emu.cursor.x, emu.cursor.y) == (9, 1)
    emu.feed(_goto(0, 5) + CSI + b"T")  # outside the region
    assert (emu.cursor.x, emu.cursor.y) == (5, 0)
    emu.feed(_goto(4, 6) + CSI + b"T")  # outside the region, below it
    assert (emu.cursor.x, emu.cursor.y) == (6, 4)


def test_sd_matches_reverse_index_at_the_top_margin() -> None:
    by_sd = _numbered()
    by_sd.feed(CSI + b"2T")
    by_ri = _numbered()
    by_ri.feed(_goto(0, 0) + b"\x1bM\x1bM")
    assert by_sd.screen_lines_text() == by_ri.screen_lines_text()


def test_sd_never_touches_scrollback() -> None:
    emu = _numbered()
    emu.feed(b"\r\nextra\r\nmore")  # two lines of real history
    history = _history(emu)
    assert history == ["L0", "L1"]
    emu.feed(CSI + b"3T")
    assert _history(emu) == history
    assert emu.scrolled_total == 2


def test_sd_in_alt_screen_scrolls_the_alt_screen_only() -> None:
    emu = _numbered()
    emu.feed(b"\x1b[?1049h")
    emu.feed(_goto(0, 0) + b"\r\n".join(b"A%d" % n for n in range(5)))
    emu.feed(CSI + b"2T")
    assert emu.screen_lines_text() == ["", "", "A0", "A1", "A2"]
    assert emu.history_len == 0
    emu.feed(b"\x1b[?1049l")
    assert emu.screen_lines_text() == ["L0", "L1", "L2", "L3", "L4"]


def test_sd_private_variant_is_ignored() -> None:
    emu = _numbered()
    emu.feed(_goto(2, 3))
    before = (emu.screen_lines_text(), emu.cursor, emu.history_len)
    emu.feed(CSI + b"?3T")
    emu.feed(CSI + b"?T")
    assert (emu.screen_lines_text(), emu.cursor, emu.history_len) == before


def test_sd_marks_the_region_dirty() -> None:
    emu = _numbered()
    emu.feed(_region(1, 3) + _goto(1, 0))
    emu.screen.dirty.clear()
    emu.feed(CSI + b"T")
    assert {1, 2, 3} <= set(emu.screen.dirty)


def test_ncurses_style_batch_scroll_down_and_up() -> None:
    """What nano sends for a batch of keys: region, ``CSI n S``, redraw of the freed rows."""
    emu = _emu(cols=30, rows=10)
    for row in range(10):
        emu.feed(_goto(row, 0) + b"line %02d" % row)
    emu.feed(_region(1, 8) + b"\x1b[1;1H")
    emu.feed(CSI + b"3S")  # rows 1..8 move up by three
    emu.feed(_region(0, 9))
    for row, number in zip((6, 7, 8), (9, 10, 11), strict=True):
        emu.feed(_goto(row, 0) + b"line %02d" % number)
    assert emu.screen_lines_text()[1:9] == [f"line {n:02d}" for n in range(4, 12)]
    assert emu.screen_lines_text()[0] == "line 00"
    assert emu.screen_lines_text()[9] == "line 09"
    emu.feed(_region(1, 8) + CSI + b"3T")  # and back down
    emu.feed(_region(0, 9))
    for row, number in zip((1, 2, 3), (1, 2, 3), strict=True):
        emu.feed(_goto(row, 0) + b"line %02d" % number)
    assert emu.screen_lines_text()[1:9] == [f"line {n:02d}" for n in range(1, 9)]


# --- REP (CSI n b) --------------------------------------------------------------------------


def test_rep_repeats_the_last_character() -> None:
    emu = _emu()
    emu.feed(b"x\x1b[4b")
    assert emu.screen_lines_text()[0] == "xxxxx"
    assert emu.cursor.x == 5


def test_rep_default_count_is_one() -> None:
    emu = _emu()
    emu.feed(b"x\x1b[b")
    assert emu.screen_lines_text()[0] == "xx"


def test_rep_repeats_only_the_last_character() -> None:
    emu = _emu()
    emu.feed(b"ab\x1b[2b")
    assert emu.screen_lines_text()[0] == "abbb"


def test_rep_without_a_previous_character_does_nothing() -> None:
    emu = _emu()
    emu.feed(b"\x1b[4b")
    assert emu.screen_lines_text() == [""] * 5
    assert (emu.cursor.x, emu.cursor.y) == (0, 0)


def test_rep_remembers_the_character_across_cursor_movement() -> None:
    emu = _emu()
    emu.feed(b"x" + _goto(2, 9) + b"\x1b[2b")
    assert emu.screen_lines_text()[0] == "x"
    assert emu.screen_lines_text()[2] == " " * 9 + "xx"


def test_rep_repeats_a_non_ascii_character() -> None:
    emu = _emu()
    emu.feed("é\x1b[2b".encode())
    assert emu.screen_lines_text()[0] == "ééé"


def test_rep_count_is_limited_to_the_screen_size() -> None:
    emu = _emu(cols=20, rows=5)
    emu.feed(b"x\x1b[999999b")
    text = "".join(_history(emu)) + "".join(emu.screen_lines_text())
    assert set(text) == {"x"}
    assert len(text) == 1 + 20 * 5  # the drawn character plus at most columns * lines repeats


def test_rep_private_variant_is_ignored() -> None:
    emu = _emu()
    emu.feed(b"x\x1b[?4b")
    assert emu.screen_lines_text()[0] == "x"
    assert emu.cursor.x == 1


# --- CBT (CSI n Z) --------------------------------------------------------------------------


def _at_column(col: int) -> TerminalEmulator:
    emu = _emu(cols=80, rows=3)
    emu.feed(b"\x1b[%dG" % (col + 1))
    assert emu.cursor.x == col
    return emu


@pytest.mark.parametrize(
    ("column", "sequence", "expected"),
    [
        (20, b"\x1b[Z", 16),
        (20, b"\x1b[1Z", 16),
        (20, b"\x1b[2Z", 8),
        (20, b"\x1b[3Z", 0),
        (20, b"\x1b[99Z", 0),
        (3, b"\x1b[Z", 0),
        (3, b"\x1b[2Z", 0),
        (16, b"\x1b[Z", 8),  # a stop under the cursor does not count
        (8, b"\x1b[Z", 0),
        (17, b"\x1b[Z", 16),
        (0, b"\x1b[Z", 0),
        (79, b"\x1b[Z", 72),
    ],
)
def test_cbt_moves_back_to_tab_stops(column: int, sequence: bytes, expected: int) -> None:
    emu = _at_column(column)
    emu.feed(sequence)
    assert emu.cursor.x == expected
    assert emu.cursor.y == 0


def test_cbt_uses_custom_tab_stops() -> None:
    emu = _emu(cols=80, rows=3)
    emu.feed(b"\x1b[3g")  # clear all tab stops
    emu.feed(b"\x1b[6G\x1bH\x1b[13G\x1bH")  # new stops at columns 5 and 12
    emu.feed(b"\x1b[16G\x1b[Z")
    assert emu.cursor.x == 12
    emu.feed(b"\x1b[Z")
    assert emu.cursor.x == 5
    emu.feed(b"\x1b[Z")
    assert emu.cursor.x == 0
    emu.feed(b"\x1b[16G\x1b[2Z")
    assert emu.cursor.x == 5


def test_cbt_does_not_change_the_text_or_the_row() -> None:
    emu = _emu(cols=80, rows=3)
    emu.feed(b"first\r\nsecond text\x1b[Z")  # the cursor was in column 11
    assert emu.screen_lines_text()[:2] == ["first", "second text"]
    assert (emu.cursor.x, emu.cursor.y) == (8, 1)


def test_cbt_private_variant_is_ignored() -> None:
    emu = _at_column(20)
    emu.feed(b"\x1b[?1Z")
    assert emu.cursor.x == 20


# --- no parser errors -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "sequence",
    [
        b"\x1b[S",
        b"\x1b[3S",
        b"\x1b[0S",
        b"\x1b[T",
        b"\x1b[3T",
        b"\x1b[?2S",
        b"\x1b[?3T",
        b"\x1b[?4b",
        b"\x1b[?1Z",
        b"\x1b[b",
        b"\x1b[5b",
        b"x\x1b[5b",
        b"\x1b[Z",
        b"\x1b[5Z",
        b"\x1b[999999999S",
        b"\x1b[999999999T",
        b"\x1b[999999999Z",
        b"x\x1b[999999999b",
    ],
)
def test_sequences_raise_no_parser_error(sequence: bytes, caplog: pytest.LogCaptureFixture) -> None:
    emu = _emu()
    with caplog.at_level(logging.WARNING):
        emu.feed(sequence)
        emu.feed(b"ok")  # the stream keeps working afterwards
    assert not [record for record in caplog.records if "parser error" in record.getMessage()]
    assert "ok" in "".join(emu.screen_lines_text())


# --- helpers for the round 2 tests: replies, full state, every way to cut a stream -----------


def _chunkings(data: bytes) -> list[list[bytes]]:
    """``data`` fed whole, byte by byte, and cut in two at every position."""
    cuts = [[data[:cut], data[cut:]] for cut in range(1, len(data))]
    return [[data], [data[i : i + 1] for i in range(len(data))], *cuts]


def _play(chunks: list[bytes], *, numbered: bool = False) -> tuple[TerminalEmulator, bytes]:
    """Feed ``chunks`` (one ``feed`` call each) to a new emulator; return it and its replies.

    With ``numbered`` the screen first shows ``L0`` ... ``L4`` (cursor after ``L4``, row 4); the
    replies of that setup are not counted.
    """
    replies: list[bytes] = []
    emu = _numbered(on_response=replies.append) if numbered else _emu(on_response=replies.append)
    replies.clear()
    for chunk in chunks:
        emu.feed(chunk)
    return emu, b"".join(replies)


def _state(emu: TerminalEmulator, replies: bytes = b"") -> tuple:
    """Everything observable about an emulator: every cell with its attributes, the cursor ..."""
    cells = [tuple(emu.line_at(i)[x] for x in range(emu.cols)) for i in range(emu.total_lines)]
    return (cells, emu.cursor, emu.history_len, emu.scrolled_total, emu.in_alt_screen, replies)


def _parser_errors(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [m for m in (r.getMessage() for r in caplog.records) if "parser error" in m]


def _underlined(emu: TerminalEmulator) -> list[bool]:
    line = emu.line_at(emu.history_len)
    return [line[x].underscore for x in range(emu.cols)]


# --- D.1: several parameters and private variants must not lose the rest of the chunk -------

# pyte calls ``handler(*params)`` or, after ``CSI ?``, ``handler(*params, private=True)`` with
# every parameter positional. A handler written as ``(count=None, private=False)`` turned the
# second parameter into ``private`` and raised ``TypeError`` for more, so the text after the
# sequence and the reply to the DA / DSR that followed it were lost.

# (sequence, row 0 after ``<sequence>AFTER``). Only the first parameter counts (like xterm).
EXTRA_PARAMETER_CASES = [
    (b"\x1b[?1;1;0S", "AFTER"),  # XTSMGRAPHICS: sent by notcurses, lsix, chafa ...
    (b"\x1b[?2;1;0S", "AFTER"),
    (b"\x1b[?1;2S", "AFTER"),
    (b"\x1b[1;2;3;4;5T", "AFTER"),  # SD by one line on an empty screen
    (b"x\x1b[1;2;3b", "xxAFTER"),  # REP: one repeat
    (b"\x1b[1;2;3Z", "AFTER"),  # CBT at column 0
]


@pytest.mark.parametrize(("sequence", "row"), EXTRA_PARAMETER_CASES)
def test_extra_parameters_keep_the_text_and_the_reply(
    sequence: bytes, row: str, caplog: pytest.LogCaptureFixture
) -> None:
    data = sequence + b"AFTER\x1b[c"
    with caplog.at_level(logging.WARNING):
        for chunks in _chunkings(data):
            emu, replies = _play(chunks)
            assert emu.screen_lines_text()[0] == row, chunks
            assert replies == b"\x1b[?6c", chunks
    assert not _parser_errors(caplog)


def test_xtsmgraphics_before_a_status_request_keeps_the_replies(
    caplog: pytest.LogCaptureFixture,
) -> None:
    data = b"\x1b[?2;1;0S\x1b[?1;1;0S\x1b[6n\x1b[c"
    with caplog.at_level(logging.WARNING):
        for chunks in _chunkings(data):
            emu, replies = _play(chunks)
            assert replies == b"\x1b[1;1R\x1b[?6c", chunks
            assert emu.screen_lines_text() == [""] * 5
    assert not _parser_errors(caplog)


@pytest.mark.parametrize(
    "sequence",
    [
        b"\x1b[?1;1;0S",
        b"\x1b[?2;1;0S",
        b"\x1b[?1;2S",
        b"\x1b[?1;2;3;4T",
        b"\x1b[?1;2b",
        b"\x1b[?1;2;3b",
        b"\x1b[?1;2Z",
        b"\x1b[?1;2;3Z",
    ],
)
def test_private_variants_with_several_parameters_are_ignored(
    sequence: bytes, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        for chunks in _chunkings(sequence):
            emu, _ = _play([b"x" + _goto(2, 3)], numbered=True)
            before = _state(emu)
            for chunk in chunks:
                emu.feed(chunk)
            assert _state(emu) == before, chunks
    assert not _parser_errors(caplog)


@pytest.mark.parametrize(
    ("sequence", "expected"),
    [
        (b"\x1b[2;5S", ["L2", "L3", "L4", "", ""]),
        (b"\x1b[0;5S", ["L1", "L2", "L3", "L4", ""]),  # first parameter 0 counts as 1
        (b"\x1b[;5S", ["L1", "L2", "L3", "L4", ""]),  # first parameter omitted
        (b"\x1b[3;1T", ["", "", "", "L0", "L1"]),
        (b"\x1b[0;9T", ["", "L0", "L1", "L2", "L3"]),
        (b"\x1b[;9T", ["", "L0", "L1", "L2", "L3"]),
    ],
)
def test_su_and_sd_use_only_the_first_parameter(sequence: bytes, expected: list[str]) -> None:
    for chunks in _chunkings(sequence):
        emu, _ = _play([_goto(1, 7), *chunks], numbered=True)
        assert emu.screen_lines_text() == expected, chunks
        assert (emu.cursor.x, emu.cursor.y) == (7, 1), chunks  # the cursor stays where it was


def test_su_with_extra_parameters_still_fills_the_scrollback() -> None:
    emu = _numbered()
    emu.feed(CSI + b"2;5S")
    assert _history(emu) == ["L0", "L1"]
    assert emu.scrolled_total == 2


def test_rep_and_cbt_use_only_the_first_parameter() -> None:
    emu = _emu(cols=80, rows=3)
    emu.feed(b"x\x1b[3;1b")
    assert emu.screen_lines_text()[0] == "xxxx"
    emu.feed(b"\x1b[21G\x1b[2;9Z")
    assert emu.cursor.x == 8


# --- D.2: CSI > sequences are discarded ------------------------------------------------------

# pyte 0.8.2 drops the ``>`` and runs the rest as the plain sequence: ``CSI > Pm T`` (xterm
# XTRMTITLE) became SD and ``CSI > 4 ; 2 m`` (vim 9 modifyOtherKeys) became SGR 4;2, which
# underlined everything after it. Only the secondary DA (final ``c``) is still answered.

# Discarded whatever the final byte is. The tests give each of them a screen on which the plain
# sequence would be visible (scroll, underline, cursor movement, erase).
GT_DISCARDED = [
    b"\x1b[>0T",
    b"\x1b[>3T",
    b"\x1b[>T",
    b"\x1b[>4;2m",
    b"\x1b[>4;m",
    b"\x1b[>m",
    b"\x1b[>4:2m",
    b"\x1b[>1u",
    b"\x1b[>5u",
    b"\x1b[>0q",
    b"\x1b[>2S",
    b"\x1b[>2J",
    b"\x1b[>3A",
    b"\x1b[>1;1H",
    b"\x1b[>2K",
    b"\x1b[>4;1;2;3;4;5;6;7;8;9m",
]


@pytest.mark.parametrize("sequence", GT_DISCARDED)
def test_gt_sequence_is_discarded_at_every_cut(
    sequence: bytes, caplog: pytest.LogCaptureFixture
) -> None:
    emu, replies = _play([b"ab" + b"cd"], numbered=True)
    assert emu.screen_lines_text() == ["L0", "L1", "L2", "L3", "L4abcd"]
    expected = _state(emu, replies)
    with caplog.at_level(logging.WARNING):
        for chunks in _chunkings(b"ab" + sequence + b"cd"):
            emu, replies = _play(chunks, numbered=True)
            assert _state(emu, replies) == expected, chunks
    assert not _parser_errors(caplog)


@pytest.mark.parametrize("sequence", [b"\x1b[>0T", b"\x1b[>3T", b"\x1b[>T"])
def test_gt_xtrmtitle_does_not_scroll(sequence: bytes) -> None:
    emu = _numbered()
    emu.feed(_goto(2, 3))
    before = _state(emu)
    emu.feed(sequence)
    assert _state(emu) == before
    assert emu.screen_lines_text() == ["L0", "L1", "L2", "L3", "L4"]
    assert (emu.cursor.x, emu.cursor.y) == (3, 2)


def test_gt_modify_other_keys_does_not_underline_the_text() -> None:
    emu = _emu()
    emu.feed(b"\x1b[>4;2mabc")
    assert emu.screen_lines_text()[0] == "abc"
    assert not any(_underlined(emu))
    emu.feed(b"def\r\nghi")
    assert not any(_underlined(emu))
    assert not any(emu.line_at(1)[x].underscore for x in range(emu.cols))


@pytest.mark.parametrize("sequence", [b"\x1b[>1u", b"\x1b[>4;m"])
def test_gt_keyboard_mode_sequences_leave_no_effect(
    sequence: bytes, caplog: pytest.LogCaptureFixture
) -> None:
    plain, _ = _play([b"abc"])
    with caplog.at_level(logging.WARNING):
        emu, replies = _play([sequence + b"abc"])
    assert replies == b""
    assert _state(emu) == _state(plain)
    assert not any(_underlined(emu))
    assert not _parser_errors(caplog)


@pytest.mark.parametrize("sequence", [b"\x1b[>c", b"\x1b[>0c"])
def test_gt_secondary_device_attributes_are_still_answered(sequence: bytes) -> None:
    for chunks in _chunkings(b"ab" + sequence + b"cd"):
        emu, replies = _play(chunks)
        assert replies == b"\x1b[?6c", chunks  # the same reply as for CSI c
        assert emu.screen_lines_text()[0] == "abcd", chunks


def test_gt_discarded_and_answered_sequences_together() -> None:
    data = b"\x1b[>4;2mab\x1b[>c\x1b[>0T\x1b[>0c\x1b[>1ucd\x1b[6n"
    for chunks in _chunkings(data):
        emu, replies = _play(chunks)
        assert replies == b"\x1b[?6c\x1b[?6c\x1b[1;5R", chunks
        assert emu.screen_lines_text()[0] == "abcd", chunks
        assert not any(_underlined(emu)), chunks


def test_plain_text_ending_with_esc_continues_in_the_next_chunk() -> None:
    emu = _emu()
    emu.feed(b"hi\x1b")
    assert emu.screen_lines_text()[0] == "hi"  # the text before the unfinished ESC is drawn now
    emu.feed(b"[31mred")
    assert emu.screen_lines_text()[0] == "hired"
    line = emu.line_at(0)
    assert [line[x].fg for x in range(5)] == ["default", "default", "red", "red", "red"]


@pytest.mark.parametrize("tail", [b"\x1b", b"\x1b[", b"\x1b[>", b"\x1b[>4", b"\x1b[>4;"])
def test_text_before_an_unfinished_sequence_is_drawn_at_once(tail: bytes) -> None:
    emu = _emu()
    emu.feed(b"hi" + tail)
    assert emu.screen_lines_text()[0] == "hi"
    assert emu.cursor.x == 2


def test_unfinished_gt_sequence_is_completed_by_the_next_chunk() -> None:
    emu = _emu()
    for piece in (b"a\x1b", b"[", b">", b"4", b";", b"2", b"m", b"bc"):
        emu.feed(piece)
    assert emu.screen_lines_text()[0] == "abc"
    assert not any(_underlined(emu))


# The filter holds back an unfinished ``ESC [ >`` plus at most this many parameter bytes (the
# ``{0,64}`` of ``_GT_SEQUENCE`` / ``_GT_PREFIX``); a longer run goes to pyte instead of being held.
GT_PARAM_CAP = 64
GT_PREFIX_LEN = len(b"\x1b[>")


def _gt_params(length: int) -> bytes:
    """``length`` parameter bytes (digits and ``;``) that end in a digit, so ``m`` makes SGR 4."""
    if length % 2:
        return b"4" + b";4" * ((length - 1) // 2)
    return b"44" + b";4" * ((length - 2) // 2)


def test_runaway_gt_sequence_is_not_held_beyond_the_parameter_cap() -> None:
    params = _gt_params(81)
    pieces = [params[i : i + 7] for i in range(0, len(params), 7)]
    emu = _emu()
    emu.feed(b"\x1b[>")
    assert emu._pending == b"\x1b[>"
    seen = 0
    released = False
    for piece in pieces:
        emu.feed(piece)
        seen += len(piece)
        held = len(emu._pending)
        assert held <= GT_PREFIX_LEN + GT_PARAM_CAP, (seen, held)  # the carry stays small
        if seen <= GT_PARAM_CAP:
            assert emu._pending == b"\x1b[>" + params[:seen], seen  # still a possible prefix
        else:
            assert emu._pending == b"", seen  # over the cap: passed on, not held
            released = True
    assert released
    assert emu.screen_lines_text()[0] == ""  # pyte is inside the CSI, nothing drawn yet
    emu.feed(b"m" + b"abc")
    assert emu._pending == b""
    assert emu.screen_lines_text()[0] == "abc"
    # not discarded: pyte dropped the ``>`` and ran the whole runaway sequence as SGR 4
    assert _underlined(emu)[:3] == [True, True, True]


@pytest.mark.parametrize(
    ("length", "discarded"),
    [(1, True), (63, True), (GT_PARAM_CAP, True), (GT_PARAM_CAP + 1, False), (66, False)],
)
def test_gt_sequence_is_discarded_only_up_to_the_cap(length: int, discarded: bool) -> None:
    data = b"\x1b[>" + _gt_params(length) + b"mabc"
    for chunks in _chunkings(data):
        emu, replies = _play(chunks)
        assert replies == b"", chunks
        assert emu.screen_lines_text()[0] == "abc", chunks
        assert _underlined(emu)[:3] == [not discarded] * 3, chunks
        assert emu._pending == b"", chunks


def test_esc_alone_in_a_chunk_is_not_lost() -> None:
    emu = _numbered()
    emu.feed(_goto(0, 0))
    emu.feed(b"\x1b")
    emu.feed(b"M")  # ESC M = reverse index at the top margin: the screen scrolls down
    assert emu.screen_lines_text() == ["", "L0", "L1", "L2", "L3"]


# Escape sequences of all kinds (none of them a discarded ``CSI >``) must pass unchanged. The
# stream also holds multi-byte UTF-8 characters, which must survive being cut in the middle.
MIXED = (
    b"\x1b[31mred\x1b[0m \x1b[2;3Hxy\x1b[?25l\x1b[?25h\x1b]0;a title\x07\x1b(B\x1b7\x1b[3Cz\x1b8"
    b"\xc3\xa9\xe6\x97\xa5\xe6\x9c\xac\x1b[1;2;3Z\x1b[?1;1;0Szz\x1b[2S\x1b[T\x1b[3b\x1b[6n"
    b"\x1b[>c\x1b[=c\x1b[<u\x1b[?1049h\x1b[1;1H\x1b[?1049l\x1b[1;5r\x1b[2S\x1b[r\x1bM\x1b[4h"
)
MIXED_WITH_GT = MIXED[:20] + b"\x1b[>4;2m" + MIXED[20:60] + b"\x1b[>0T\x1b[>1u" + MIXED[60:]


def test_stream_with_escape_sequences_is_independent_of_chunking(
    caplog: pytest.LogCaptureFixture,
) -> None:
    for data in (MIXED, MIXED_WITH_GT):
        emu, replies = _play([data], numbered=True)
        whole = _state(emu, replies)
        # the cursor position report, then the answer to the secondary DA ``CSI > c``
        assert re.fullmatch(rb"\x1b\[\d+;\d+R\x1b\[\?6c", replies), replies
        with caplog.at_level(logging.WARNING):
            for chunks in _chunkings(data):
                emu, replies = _play(chunks, numbered=True)
                assert _state(emu, replies) == whole, chunks
    assert not _parser_errors(caplog)


def test_gt_sequences_are_the_only_thing_removed() -> None:
    reference, ref_replies = _play([MIXED], numbered=True)
    emu, replies = _play([MIXED_WITH_GT], numbered=True)
    assert _state(emu, replies) == _state(reference, ref_replies)


# Random streams made of text, partial escape sequences and complete ones (discarded and plain).
# Only finals whose pyte handler takes any number of parameters are used, so that the streams
# never raise inside pyte itself.
FUZZ_TOKENS = [
    b"x",
    b"yz",
    "é".encode(),
    "日".encode(),
    b"\r\n",
    b"\x1b",
    b"\x1b[",
    b"\x1b[>",
    b"[",
    b">",
    b"4",
    b"2",
    b";",
    b":",
    b"m",
    b"T",
    b"S",
    b"Z",
    b"b",
    b"u",
    b"\x1b[>4;2m",
    b"\x1b[>0T",
    b"\x1b[>c",
    b"\x1b[31m",
    b"\x1b[2;5S",
    b"\x1b[?1;1;0S",
    b"\x1b[2J",
    b"\x1b[6n",
]


def test_random_streams_are_independent_of_chunking(caplog: pytest.LogCaptureFixture) -> None:
    rng = random.Random(20261021)
    with caplog.at_level(logging.WARNING):
        for _ in range(400):
            data = b"".join(rng.choice(FUZZ_TOKENS) for _ in range(rng.randint(1, 30)))
            cuts = sorted(rng.randint(0, len(data)) for _ in range(rng.randint(1, 4)))
            bounds = [0, *cuts, len(data)]
            pieces = [data[a:b] for a, b in pairwise(bounds)]
            whole = _state(*_play([data], numbered=True))
            assert _state(*_play(pieces, numbered=True)) == whole, (data, pieces)
            assert (
                _state(*_play([data[i : i + 1] for i in range(len(data))], numbered=True)) == whole
            )
    assert not _parser_errors(caplog)


# --- regression: recordings of a real nano 7.2 ----------------------------------------------

# name -> (key presses, first line shown, cursor row) of the final nano screen. The edited file
# has 300 lines "baris NNN isi teks contoh"; nano shows 20 of them on screen rows 1..20. After P
# Down presses the cursor sits on line P + 1, on the last row (20), so the screen shows lines
# P - 18 .. P + 1. The Up recording starts at line 109 (six PgDn, 18 lines each) and ends after
# 60 Up presses on line 49, on the first row (1).
RECORDINGS = {
    "nano_down_single": (80, 62, 20),  # 80 single presses (LF scrolling, always worked)
    "nano_down_batch2": (50, 32, 20),  # 25 writes of 2 presses
    "nano_down_batch3": (75, 57, 20),  # 25 writes of 3
    "nano_down_batch5": (125, 107, 20),  # 25 writes of 5
    "nano_up_batch3": (60, 49, 1),  # 6 x PgDn, then 20 writes of 3 Up
}
BATCH_RECORDINGS = ["nano_down_batch2", "nano_down_batch3", "nano_down_batch5"]


def _replay(name: str, chunk: int | None = None) -> TerminalEmulator:
    data = (DATA / f"{name}.bin").read_bytes()
    emu = TerminalEmulator(80, 24, 1000)
    if chunk is None:
        emu.feed(data)
    else:
        for start in range(0, len(data), chunk):
            emu.feed(data[start : start + chunk])
    return emu


def _body_numbers(emu: TerminalEmulator) -> list[int | None]:
    """The ``NNN`` of ``baris NNN ...`` for screen rows 2..21 (``None`` if a row differs)."""
    numbers: list[int | None] = []
    for text in emu.screen_lines_text()[1:21]:
        match = re.match(r"baris (\d{3}) isi teks contoh$", text)
        numbers.append(int(match.group(1)) if match else None)
    return numbers


@pytest.mark.parametrize("name", list(RECORDINGS))
def test_nano_scroll_shows_consecutive_lines(name: str) -> None:
    numbers = _body_numbers(_replay(name))
    assert None not in numbers, numbers
    assert all(b - a == 1 for a, b in pairwise(numbers)), numbers


@pytest.mark.parametrize("name", list(RECORDINGS))
def test_nano_scroll_ends_on_the_expected_lines(name: str) -> None:
    _, first, cursor_row = RECORDINGS[name]
    emu = _replay(name)
    assert _body_numbers(emu) == list(range(first, first + 20))
    assert (emu.cursor.x, emu.cursor.y) == (0, cursor_row)


@pytest.mark.parametrize("name", list(RECORDINGS))
def test_nano_scroll_keeps_the_frame_intact(name: str) -> None:
    emu = _replay(name)
    lines = emu.screen_lines_text()
    assert lines[21] == ""  # status bar
    assert "^G Help" in lines[22]
    assert "^X Exit" in lines[23]
    assert emu.in_alt_screen
    assert emu.history_len == 0  # scrolling inside nano's alternate screen leaves no scrollback


@pytest.mark.parametrize("name", list(RECORDINGS))
@pytest.mark.parametrize("chunk", [1, 7, 61])
def test_nano_scroll_is_independent_of_chunking(name: str, chunk: int) -> None:
    whole, pieces = _replay(name), _replay(name, chunk)
    assert pieces.screen_lines_text() == whole.screen_lines_text()
    assert pieces.cursor == whole.cursor
    assert pieces.history_len == whole.history_len


@pytest.mark.parametrize("name", list(RECORDINGS))
def test_recordings_carry_no_path_of_the_recording_machine(name: str) -> None:
    """nano shows the file name in its title bar: it must be the bare ``sample.txt``."""
    data = (DATA / f"{name}.bin").read_bytes()
    assert not re.search(rb"/(?:tmp|home|root|Users|var|usr|mnt)/", data)
    title = _replay(name).screen_lines_text()[0]
    assert title.split()[-1] == "sample.txt", title
    assert "/" not in title
    assert "..." not in title  # nano shortens a long path with "..."


@pytest.mark.parametrize("name", BATCH_RECORDINGS)
def test_batch_recordings_contain_su(name: str) -> None:
    """The recordings must really exercise ``CSI n S`` (otherwise they prove nothing)."""
    data = (DATA / f"{name}.bin").read_bytes()
    assert re.search(rb"\x1b\[\d+S", data)


def test_up_recording_contains_sd() -> None:
    assert re.search(rb"\x1b\[\d+T", (DATA / "nano_up_batch3.bin").read_bytes())


def test_single_press_recording_scrolls_with_line_feeds() -> None:
    data = (DATA / "nano_down_single.bin").read_bytes()
    assert not re.search(rb"\x1b\[\d*[ST]", data)
    assert data.count(b"\n") >= 20
