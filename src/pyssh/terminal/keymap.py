"""Translate Qt key events into terminal bytes (SPEC §8.3.3–§8.3.5). QtCore only (rule A6)."""

from __future__ import annotations

from PySide6.QtCore import Qt

from pyssh.config import IS_MAC
from pyssh.shortcuts import is_app_shortcut, normalize_mods

K = Qt.Key
M = Qt.KeyboardModifier

ESC = b"\x1b"

# Cursor-style keys: final byte of CSI/SS3 sequences.
_CURSOR_KEYS = {
    int(K.Key_Up): b"A",
    int(K.Key_Down): b"B",
    int(K.Key_Right): b"C",
    int(K.Key_Left): b"D",
    int(K.Key_Home): b"H",
    int(K.Key_End): b"F",
}
# "~" keys: CSI <n> ~
_TILDE_KEYS = {
    int(K.Key_Insert): 2,
    int(K.Key_Delete): 3,
    int(K.Key_PageUp): 5,
    int(K.Key_PageDown): 6,
    int(K.Key_F5): 15,
    int(K.Key_F6): 17,
    int(K.Key_F7): 18,
    int(K.Key_F8): 19,
    int(K.Key_F9): 20,
    int(K.Key_F10): 21,
    int(K.Key_F11): 23,
    int(K.Key_F12): 24,
}
_SS3_FUNCTION_KEYS = {
    int(K.Key_F1): b"P",
    int(K.Key_F2): b"Q",
    int(K.Key_F3): b"R",
    int(K.Key_F4): b"S",
}
_ENTER_KEYS = {int(K.Key_Return), int(K.Key_Enter)}

# Ctrl combinations that are not letters (SPEC §8.3.4), matched on the key code.
_CTRL_SYMBOLS = {
    int(K.Key_Space): 0x00,
    int(K.Key_At): 0x00,
    int(K.Key_2): 0x00,
    int(K.Key_BracketLeft): 0x1B,
    int(K.Key_3): 0x1B,
    int(K.Key_Backslash): 0x1C,
    int(K.Key_4): 0x1C,
    int(K.Key_BracketRight): 0x1D,
    int(K.Key_5): 0x1D,
    int(K.Key_AsciiCircum): 0x1E,
    int(K.Key_6): 0x1E,
    int(K.Key_Minus): 0x1F,
    int(K.Key_Underscore): 0x1F,
    int(K.Key_Slash): 0x1F,
    int(K.Key_7): 0x1F,
    int(K.Key_8): 0x7F,
    int(K.Key_Question): 0x7F,
}


def _printable(text: str) -> bool:
    return bool(text) and all(ch.isprintable() for ch in text)


def _xterm_modifier(mods: Qt.KeyboardModifier) -> int:
    m = 1
    if mods & M.ShiftModifier:
        m += 1
    if mods & M.AltModifier:
        m += 2
    if mods & M.ControlModifier:
        m += 4
    return m


def _special_key(key: int, mods: Qt.KeyboardModifier, *, app_cursor: bool) -> bytes | None:
    m = _xterm_modifier(mods)
    if key in _CURSOR_KEYS:
        final = _CURSOR_KEYS[key]
        if m > 1:
            return b"\x1b[1;%d" % m + final
        return (b"\x1bO" if app_cursor else b"\x1b[") + final
    if key in _TILDE_KEYS:
        n = _TILDE_KEYS[key]
        if m > 1:
            return b"\x1b[%d;%d~" % (n, m)
        return b"\x1b[%d~" % n
    if key in _SS3_FUNCTION_KEYS:
        final = _SS3_FUNCTION_KEYS[key]
        if m > 1:
            return b"\x1b[1;%d" % m + final
        return b"\x1bO" + final
    alt = bool(mods & M.AltModifier)
    if key in _ENTER_KEYS:
        return b"\x1b\r" if alt else b"\r"
    if key == int(K.Key_Backspace):
        base = b"\x08" if mods & M.ControlModifier else b"\x7f"
        return ESC + base if alt else base
    if key == int(K.Key_Backtab) or (key == int(K.Key_Tab) and mods & M.ShiftModifier):
        return b"\x1b[Z"
    if key == int(K.Key_Tab):
        return b"\t"
    if key == int(K.Key_Escape):
        return ESC
    return None


def _ctrl_byte(key: int) -> int | None:
    # Ctrl+Shift+- (Ctrl+_) on Windows/Linux is the zoom-out shortcut and never gets here,
    # because the shortcut check runs first (SPEC §8.3.2).
    if int(K.Key_A) <= key <= int(K.Key_Z):
        return key - int(K.Key_A) + 1
    return _CTRL_SYMBOLS.get(key)


def _option_base_char(key: int, mods: Qt.KeyboardModifier) -> str | None:
    """Character of the physical key (macOS Option-as-Meta), ignoring the Option layer."""
    if int(K.Key_A) <= key <= int(K.Key_Z):
        char = chr(key)
        return char if mods & M.ShiftModifier else char.lower()
    if 0x20 <= key < 0x7F:
        return chr(key)
    return None


def key_to_bytes(
    key: int,
    modifiers: Qt.KeyboardModifier,
    text: str,
    *,
    app_cursor: bool,
    mac: bool = IS_MAC,
    mac_option_as_meta: bool = False,
) -> bytes | None:
    """Bytes to send for a key press, or ``None`` when nothing goes to the server."""
    key = int(key)
    mods = normalize_mods(modifiers)
    ctrl = bool(mods & M.ControlModifier)
    alt = bool(mods & M.AltModifier)

    # 1–3: application shortcuts, Cmd/Super, Shift+PageUp/PageDown scrollback.
    if is_app_shortcut(key, mods, mac=mac):
        return None
    if mods & M.MetaModifier:
        return None
    if mods == M.ShiftModifier and key in (int(K.Key_PageUp), int(K.Key_PageDown)):
        return None
    # 4: special keys.
    special = _special_key(key, mods, app_cursor=app_cursor)
    if special is not None:
        return special
    # 5: AltGr (reported as Ctrl+Alt) producing a printable character.
    if ctrl and alt and _printable(text):
        return text.encode("utf-8")
    # 6: Ctrl combinations, from the key code.
    if ctrl:
        byte = _ctrl_byte(key)
        if byte is not None:
            data = bytes([byte])
            return ESC + data if alt else data
    # 7: Alt + printable character.
    if alt and _printable(text):
        if not mac:
            return ESC + text.encode("utf-8")
        if mac_option_as_meta:
            base = _option_base_char(key, mods)
            return ESC + (base if base is not None else text).encode("utf-8")
        return text.encode("utf-8")
    # 8: plain printable text.
    if _printable(text):
        return text.encode("utf-8")
    return None
