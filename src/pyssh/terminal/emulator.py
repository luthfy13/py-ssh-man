"""``TerminalEmulator``: pyte wrapper with scrollback (SPEC §8.1). No Qt imports (rule A6)."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass

import pyte
from pyte.screens import Char, Margins

# pyte stores private modes shifted by 5 bits (verified in pyte 0.8.2 Screen.set_mode).
DECCKM = 1 << 5
DECTCEM = 25 << 5
BRACKETED_PASTE = 2004 << 5
ALT_SCREEN = (47 << 5, 1047 << 5, 1049 << 5)


def _noop(_data: bytes) -> None:
    return None


class _ScrollbackScreen(pyte.Screen):
    """``pyte.Screen`` that keeps lines scrolled off the top in a bounded deque."""

    def __init__(
        self, cols: int, rows: int, scrollback: int, on_response: Callable[[bytes], None]
    ) -> None:
        super().__init__(cols, rows)
        self.scrollback: deque = deque(maxlen=scrollback)
        self._on_response = on_response
        self.in_alt_screen = False
        self.scrolled_total = 0  # lines ever added to scrollback (survives deque eviction)

    def index(self) -> None:
        top, bottom = self.margins or Margins(0, self.lines - 1)
        full_region = top == 0 and bottom == self.lines - 1
        if self.cursor.y == bottom and full_region and not self.in_alt_screen:
            # pyte drops the top line object from ``buffer`` (rebinds rows), so keeping a
            # reference here is safe.
            self.scrollback.append(self.buffer[top])
            self.scrolled_total += 1
        super().index()

    def write_process_input(self, data: str) -> None:
        # Answers to DSR/DA (e.g. ESC[6n → ESC[y;xR) must go back to the server.
        self._on_response(data.encode("utf-8"))


@dataclass(frozen=True)
class CursorState:
    """Cursor position on the screen (0-based) and visibility."""

    x: int
    y: int
    visible: bool


class TerminalEmulator:
    """Screen state of one terminal; used from the GUI thread only (rule A2)."""

    def __init__(
        self,
        cols: int,
        rows: int,
        scrollback: int,
        on_response: Callable[[bytes], None] | None = None,
    ) -> None:
        """Create a ``cols``×``rows`` screen keeping at most ``scrollback`` history lines."""
        self._screen = _ScrollbackScreen(cols, rows, scrollback, on_response or _noop)
        self._stream = pyte.ByteStream(self._screen)

    @property
    def screen(self) -> pyte.Screen:
        """The underlying pyte screen (for rendering helpers and tests)."""
        return self._screen

    @property
    def cols(self) -> int:
        """Number of columns."""
        return self._screen.columns

    @property
    def rows(self) -> int:
        """Number of rows."""
        return self._screen.lines

    @property
    def history_len(self) -> int:
        """Number of scrollback lines."""
        return len(self._screen.scrollback)

    @property
    def total_lines(self) -> int:
        """Scrollback lines plus screen rows."""
        return self.history_len + self.rows

    @property
    def scrolled_total(self) -> int:
        """Number of lines ever moved into scrollback (keeps counting when it is full)."""
        return self._screen.scrolled_total

    @property
    def scrollback_limit(self) -> int:
        """Maximum number of scrollback lines."""
        return self._screen.scrollback.maxlen or 0

    @property
    def cursor(self) -> CursorState:
        """Cursor position and visibility."""
        cursor = self._screen.cursor
        return CursorState(cursor.x, cursor.y, not cursor.hidden)

    @property
    def app_cursor_keys(self) -> bool:
        """DECCKM (application cursor keys) is set."""
        return DECCKM in self._screen.mode

    @property
    def bracketed_paste(self) -> bool:
        """Bracketed paste mode is set."""
        return BRACKETED_PASTE in self._screen.mode

    @property
    def title(self) -> str:
        """Window title set with OSC 0/2."""
        return self._screen.title

    def feed(self, data: bytes) -> None:
        """Process bytes; UTF-8 characters split across calls are handled by pyte."""
        self._stream.feed(data)

    def resize(self, cols: int, rows: int) -> None:
        """Resize the screen (pyte drops top rows when shrinking)."""
        self._screen.resize(lines=rows, columns=cols)

    def line_at(self, index: int) -> Mapping[int, Char]:
        """Line ``index`` of scrollback + screen (``0 ≤ index < total_lines``)."""
        history = self.history_len
        if not 0 <= index < history + self.rows:
            raise IndexError(index)
        if index < history:
            return self._screen.scrollback[index]
        return self._screen.buffer[index - history]

    def visible_range(self, view_offset: int) -> range:
        """Line indexes shown when scrolled ``view_offset`` lines up (0 = bottom)."""
        start = self.history_len - view_offset
        return range(start, start + self.rows)

    def line_text(self, index: int, start: int = 0, end: int | None = None) -> str:
        """Text of cells ``[start, end)`` of a line; wide-character stubs are skipped."""
        line = self.line_at(index)
        stop = self.cols if end is None else min(end, self.cols)
        return "".join(line[x].data for x in range(max(start, 0), stop))

    def text_between(self, start: tuple[int, int], end: tuple[int, int]) -> str:
        """Text from ``start`` (inclusive) to ``end`` (exclusive), as ``(line, col)`` pairs.

        Each line is right-stripped; lines are joined with ``"\\n"``.
        """
        if end < start:
            start, end = end, start
        (first_line, first_col), (last_line, last_col) = start, end
        parts = []
        for index in range(first_line, last_line + 1):
            col_from = first_col if index == first_line else 0
            col_to = last_col if index == last_line else self.cols
            parts.append(self.line_text(index, col_from, col_to).rstrip())
        return "\n".join(parts)

    def clear_scrollback(self) -> None:
        """Forget all scrollback lines."""
        self._screen.scrollback.clear()

    def screen_lines_text(self) -> list[str]:
        """Text of each screen row, right-stripped (for tests)."""
        history = self.history_len
        return [self.line_text(history + y).rstrip() for y in range(self.rows)]
