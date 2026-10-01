"""Tests for terminal.keymap (SPEC §8.3.3–§8.3.5)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt

from pyssh.terminal.keymap import key_to_bytes

K = Qt.Key
M = Qt.KeyboardModifier
N = M.NoModifier
C, S, A, META = M.ControlModifier, M.ShiftModifier, M.AltModifier, M.MetaModifier

# (key, mods, text, app_cursor, expected) on Windows/Linux (mac=False).
CASES = [
    # Cursor keys: normal, DECCKM, modified.
    (K.Key_Up, N, "", False, b"\x1b[A"),
    (K.Key_Down, N, "", False, b"\x1b[B"),
    (K.Key_Right, N, "", False, b"\x1b[C"),
    (K.Key_Left, N, "", False, b"\x1b[D"),
    (K.Key_Up, N, "", True, b"\x1bOA"),
    (K.Key_Down, N, "", True, b"\x1bOB"),
    (K.Key_Right, N, "", True, b"\x1bOC"),
    (K.Key_Left, N, "", True, b"\x1bOD"),
    (K.Key_Up, S, "", False, b"\x1b[1;2A"),
    (K.Key_Up, A, "", False, b"\x1b[1;3A"),
    (K.Key_Right, C, "", False, b"\x1b[1;5C"),
    (K.Key_Left, C | S, "", True, b"\x1b[1;6D"),
    (K.Key_Down, C | A, "", False, b"\x1b[1;7B"),
    (K.Key_Up, C | A | S, "", False, b"\x1b[1;8A"),
    (K.Key_Home, N, "", False, b"\x1b[H"),
    (K.Key_End, N, "", False, b"\x1b[F"),
    (K.Key_Home, N, "", True, b"\x1bOH"),
    (K.Key_End, N, "", True, b"\x1bOF"),
    (K.Key_Home, S, "", False, b"\x1b[1;2H"),
    (K.Key_End, C, "", False, b"\x1b[1;5F"),
    # "~" keys.
    (K.Key_Insert, N, "", False, b"\x1b[2~"),
    (K.Key_Delete, N, "", False, b"\x1b[3~"),
    (K.Key_Delete, N, "", True, b"\x1b[3~"),
    (K.Key_PageUp, N, "", False, b"\x1b[5~"),
    (K.Key_PageDown, N, "", False, b"\x1b[6~"),
    (K.Key_Insert, S, "", False, b"\x1b[2;2~"),
    (K.Key_Delete, C, "", False, b"\x1b[3;5~"),
    (K.Key_PageUp, C, "", False, b"\x1b[5;5~"),
    (K.Key_PageDown, A, "", False, b"\x1b[6;3~"),
    (K.Key_PageUp, S, "", False, None),  # scrollback
    (K.Key_PageDown, S, "", False, None),
    # Function keys.
    (K.Key_F1, N, "", False, b"\x1bOP"),
    (K.Key_F2, N, "", False, b"\x1bOQ"),
    (K.Key_F3, N, "", False, b"\x1bOR"),
    (K.Key_F4, N, "", True, b"\x1bOS"),
    (K.Key_F5, N, "", False, b"\x1b[15~"),
    (K.Key_F6, N, "", False, b"\x1b[17~"),
    (K.Key_F7, N, "", False, b"\x1b[18~"),
    (K.Key_F8, N, "", False, b"\x1b[19~"),
    (K.Key_F9, N, "", False, b"\x1b[20~"),
    (K.Key_F10, N, "", False, b"\x1b[21~"),
    (K.Key_F11, N, "", False, b"\x1b[23~"),
    (K.Key_F12, N, "", False, b"\x1b[24~"),
    (K.Key_F1, S, "", False, b"\x1b[1;2P"),
    (K.Key_F4, C, "", False, b"\x1b[1;5S"),
    (K.Key_F5, S, "", False, b"\x1b[15;2~"),
    (K.Key_F12, C | S, "", False, b"\x1b[24;6~"),
    # Enter, Backspace, Tab, Escape.
    (K.Key_Return, N, "\r", False, b"\r"),
    (K.Key_Enter, M.KeypadModifier, "\r", False, b"\r"),
    (K.Key_Return, A, "\r", False, b"\x1b\r"),
    (K.Key_Backspace, N, "\x08", False, b"\x7f"),
    (K.Key_Backspace, C, "", False, b"\x08"),
    (K.Key_Backspace, A, "", False, b"\x1b\x7f"),
    (K.Key_Tab, N, "\t", False, b"\t"),
    (K.Key_Backtab, S, "", False, b"\x1b[Z"),
    (K.Key_Tab, S, "", False, b"\x1b[Z"),
    (K.Key_Escape, N, "\x1b", False, b"\x1b"),
    # Ctrl letters (Shift ignored unless the combination is an app shortcut).
    (K.Key_A, C, "\x01", False, b"\x01"),
    (K.Key_C, C, "\x03", False, b"\x03"),
    (K.Key_D, C, "\x04", False, b"\x04"),
    (K.Key_R, C, "\x12", False, b"\x12"),
    (K.Key_W, C, "\x17", False, b"\x17"),
    (K.Key_Z, C, "\x1a", False, b"\x1a"),
    (K.Key_A, C | S, "\x01", False, b"\x01"),
    (K.Key_N, C | S, "", False, None),  # new session shortcut
    # Ctrl+Shift+C/V are widget shortcuts: keyPressEvent handles them before key_to_bytes
    # (SPEC §8.4.5 step 2); key_to_bytes itself only drops app shortcuts (§8.3.5 step 1).
    (K.Key_C, C | S, "", False, b"\x03"),
    (K.Key_V, C | S, "", False, b"\x16"),
    # Ctrl symbols, base key and Shift result.
    (K.Key_Space, C, " ", False, b"\x00"),
    (K.Key_2, C, "", False, b"\x00"),
    (K.Key_At, C | S, "", False, b"\x00"),
    (K.Key_2, C | S, "", False, b"\x00"),
    (K.Key_BracketLeft, C, "", False, b"\x1b"),
    (K.Key_3, C, "", False, b"\x1b"),
    (K.Key_Backslash, C, "", False, b"\x1c"),
    (K.Key_4, C, "", False, b"\x1c"),
    (K.Key_BracketRight, C, "", False, b"\x1d"),
    (K.Key_5, C, "", False, b"\x1d"),
    (K.Key_AsciiCircum, C | S, "", False, b"\x1e"),
    (K.Key_6, C | S, "", False, b"\x1e"),
    (K.Key_6, C, "", False, b"\x1e"),
    (K.Key_Minus, C, "", False, b"\x1f"),
    (K.Key_Slash, C, "", False, b"\x1f"),
    (K.Key_7, C, "", False, b"\x1f"),
    (K.Key_Minus, C | S, "", False, None),  # zoom out on Windows/Linux
    (K.Key_Underscore, C | S, "", False, None),
    (K.Key_8, C, "", False, b"\x7f"),
    (K.Key_Question, C | S, "", False, b"\x7f"),
    # Ctrl+Alt+letter (not AltGr: no printable text).
    (K.Key_A, C | A, "", False, b"\x1b\x01"),
    (K.Key_X, C | A, "\x18", False, b"\x1b\x18"),
    # AltGr (Ctrl+Alt + printable text) sends the text.
    (K.Key_Q, C | A, "@", False, b"@"),
    (K.Key_E, C | A, "€", False, "€".encode()),
    (K.Key_7, C | A, "{", False, b"{"),
    # Alt + printable.
    (K.Key_X, A, "x", False, b"\x1bx"),
    (K.Key_X, A | S, "X", False, b"\x1bX"),
    (K.Key_Period, A, ".", False, b"\x1b."),
    # Plain text.
    (K.Key_A, N, "a", False, b"a"),
    (K.Key_A, S, "A", False, b"A"),
    (K.Key_Space, N, " ", False, b" "),
    (K.Key_unknown, N, "é", False, "é".encode()),
    (K.Key_unknown, N, "漢", False, "漢".encode()),
    # Nothing to send.
    (K.Key_Shift, S, "", False, None),
    (K.Key_Control, C, "", False, None),
    (K.Key_unknown, N, "", False, None),
    (K.Key_A, N, "\x7f", False, None),
    # Meta (Windows/Super) is never sent.
    (K.Key_A, META, "a", False, None),
    (K.Key_Up, META, "", False, None),
    # App shortcuts.
    (K.Key_Tab, C, "", False, None),
    (K.Key_Backtab, C | S, "", False, None),
    (K.Key_Equal, C | S, "", False, None),
]


@pytest.mark.parametrize(("key", "mods", "text", "app_cursor", "expected"), CASES)
def test_default_platform(key, mods, text: str, app_cursor: bool, expected) -> None:
    assert key_to_bytes(int(key), mods, text, app_cursor=app_cursor, mac=False) == expected


def test_case_count() -> None:
    assert len(CASES) + len(MAC_CASES) >= 60


# (key, mods, text, option_as_meta, expected) on macOS.
MAC_CASES = [
    (K.Key_C, C, "\x03", False, b"\x03"),  # Ctrl goes to the terminal
    (K.Key_Underscore, C | S, "", False, b"\x1f"),  # no zoom shortcut on Ctrl
    (K.Key_Minus, C | S, "", False, b"\x1f"),
    (K.Key_C, META, "c", False, None),  # Cmd+C: copy (widget)
    (K.Key_K, META, "k", False, None),  # any other Cmd combination
    (K.Key_Equal, META, "=", False, None),
    (K.Key_E, A, "´", False, "´".encode()),  # Option+e types the dead/accent character
    (K.Key_E, A, "´", True, b"\x1be"),  # Option as Meta: ESC + base key
    (K.Key_E, A | S, "´", True, b"\x1bE"),
    (K.Key_Period, A, "≥", True, b"\x1b."),
    (K.Key_Up, A, "", False, b"\x1b[1;3A"),
    (K.Key_Return, A, "\r", False, b"\x1b\r"),
    (K.Key_Tab, C, "", False, None),
    (K.Key_A, N, "a", False, b"a"),
]


@pytest.mark.parametrize(("key", "mods", "text", "option_meta", "expected"), MAC_CASES)
def test_mac(key, mods, text: str, option_meta: bool, expected) -> None:
    result = key_to_bytes(
        int(key), mods, text, app_cursor=False, mac=True, mac_option_as_meta=option_meta
    )
    assert result == expected


def test_option_as_meta_with_non_ascii_key_falls_back_to_text() -> None:
    result = key_to_bytes(
        int(K.Key_unknown), A, "ß", app_cursor=False, mac=True, mac_option_as_meta=True
    )
    assert result == "\x1bß".encode()


def test_option_as_meta_ignored_on_default_platform() -> None:
    result = key_to_bytes(
        int(K.Key_E), A, "e", app_cursor=False, mac=False, mac_option_as_meta=True
    )
    assert result == b"\x1be"
