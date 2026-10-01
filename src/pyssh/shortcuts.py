"""Per-platform shortcut table, the single source of shortcuts (SPEC §8.3.1, §8.3.2).

On macOS ``app.py`` sets ``AA_MacDontSwapCtrlAndMeta``, so ``MetaModifier`` is Command and
``ControlModifier`` is the physical Control key on every platform.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from PySide6.QtCore import Qt

from pyssh.config import IS_MAC

K = Qt.Key
M = Qt.KeyboardModifier

CTRL_SHIFT = M.ControlModifier | M.ShiftModifier
META_SHIFT = M.MetaModifier | M.ShiftModifier


@dataclass(frozen=True)
class Shortcut:
    """One shortcut: exact modifiers plus the accepted key codes."""

    action: str
    mods: Qt.KeyboardModifier
    keys: frozenset[int]
    sequence: str
    handled_by: Literal["action", "widget"]


def _keys(*keys: Qt.Key) -> frozenset[int]:
    return frozenset(int(k) for k in keys)


# Base key and its Shift result, because Qt may report either (SPEC §8.3.2).
_EQUAL = _keys(K.Key_Equal, K.Key_Plus)
_MINUS = _keys(K.Key_Minus, K.Key_Underscore)
_ZERO = _keys(K.Key_0, K.Key_ParenRight)
_TAB = _keys(K.Key_Tab, K.Key_Backtab)
_BRACKET_RIGHT = _keys(K.Key_BracketRight, K.Key_BraceRight)
_BRACKET_LEFT = _keys(K.Key_BracketLeft, K.Key_BraceLeft)

_SCROLL = (
    Shortcut("scroll_page_up", M.ShiftModifier, _keys(K.Key_PageUp), "Shift+PgUp", "widget"),
    Shortcut("scroll_page_down", M.ShiftModifier, _keys(K.Key_PageDown), "Shift+PgDown", "widget"),
)

_DEFAULT = (
    Shortcut("new_session", CTRL_SHIFT, _keys(K.Key_N), "Ctrl+Shift+N", "action"),
    Shortcut("close_tab", CTRL_SHIFT, _keys(K.Key_W), "Ctrl+Shift+W", "action"),
    Shortcut("reconnect", CTRL_SHIFT, _keys(K.Key_R), "Ctrl+Shift+R", "action"),
    Shortcut("next_tab", M.ControlModifier, _keys(K.Key_Tab), "Ctrl+Tab", "action"),
    Shortcut("prev_tab", CTRL_SHIFT, _TAB, "Ctrl+Shift+Tab", "action"),
    Shortcut("zoom_in", CTRL_SHIFT, _EQUAL, "Ctrl+Shift+=", "action"),
    Shortcut("zoom_out", CTRL_SHIFT, _MINUS, "Ctrl+Shift+-", "action"),
    Shortcut("zoom_reset", CTRL_SHIFT, _ZERO, "Ctrl+Shift+0", "action"),
    Shortcut("toggle_panel", CTRL_SHIFT, _keys(K.Key_B), "Ctrl+Shift+B", "action"),
    Shortcut("copy", CTRL_SHIFT, _keys(K.Key_C), "Ctrl+Shift+C", "widget"),
    Shortcut("paste", CTRL_SHIFT, _keys(K.Key_V), "Ctrl+Shift+V", "widget"),
    *_SCROLL,
)

_MAC = (
    Shortcut("new_session", M.MetaModifier, _keys(K.Key_N), "Meta+N", "action"),
    Shortcut("close_tab", M.MetaModifier, _keys(K.Key_W), "Meta+W", "action"),
    Shortcut("reconnect", M.MetaModifier, _keys(K.Key_R), "Meta+R", "action"),
    Shortcut("next_tab", M.ControlModifier, _keys(K.Key_Tab), "Ctrl+Tab", "action"),
    Shortcut("next_tab", META_SHIFT, _BRACKET_RIGHT, "Meta+Shift+]", "action"),
    Shortcut("prev_tab", CTRL_SHIFT, _TAB, "Ctrl+Shift+Tab", "action"),
    Shortcut("prev_tab", META_SHIFT, _BRACKET_LEFT, "Meta+Shift+[", "action"),
    Shortcut("zoom_in", M.MetaModifier, _EQUAL, "Meta+=", "action"),
    Shortcut("zoom_out", M.MetaModifier, _MINUS, "Meta+-", "action"),
    Shortcut("zoom_reset", M.MetaModifier, _ZERO, "Meta+0", "action"),
    Shortcut("toggle_panel", M.MetaModifier, _keys(K.Key_B), "Meta+B", "action"),
    Shortcut("copy", M.MetaModifier, _keys(K.Key_C), "Meta+C", "widget"),
    Shortcut("paste", M.MetaModifier, _keys(K.Key_V), "Meta+V", "widget"),
    *_SCROLL,
)


def normalize_mods(mods: Qt.KeyboardModifier) -> Qt.KeyboardModifier:
    """Drop ``KeypadModifier`` (SPEC §8.3.2)."""
    return mods & ~M.KeypadModifier


def shortcuts_for(*, mac: bool = IS_MAC) -> tuple[Shortcut, ...]:
    """All shortcuts of the platform."""
    return _MAC if mac else _DEFAULT


def match(key: int, mods: Qt.KeyboardModifier, *, mac: bool = IS_MAC) -> Shortcut | None:
    """Return the shortcut whose modifiers equal ``mods`` and whose keys contain ``key``."""
    key = int(key)
    mods = normalize_mods(mods)
    for shortcut in shortcuts_for(mac=mac):
        if shortcut.mods == mods and key in shortcut.keys:
            return shortcut
    return None


def is_app_shortcut(key: int, mods: Qt.KeyboardModifier, *, mac: bool = IS_MAC) -> bool:
    """True when the key combination belongs to the application, not the terminal.

    Windows/Linux: only ``handled_by == "action"`` rows. macOS: those rows plus every other
    combination containing Cmd, except Cmd+C/Cmd+V (handled by the widget).
    """
    found = match(key, mods, mac=mac)
    if found is not None:
        return found.handled_by == "action"
    return mac and bool(normalize_mods(mods) & M.MetaModifier)


def zoom_wheel_modifier(*, mac: bool = IS_MAC) -> Qt.KeyboardModifier:
    """Modifier that turns the mouse wheel into zoom (Ctrl, or Cmd on macOS)."""
    return M.MetaModifier if mac else M.ControlModifier


def sequences_for(action: str, *, mac: bool = IS_MAC) -> list[str]:
    """Primary ``QKeySequence`` strings for an action, in table order."""
    return [s.sequence for s in shortcuts_for(mac=mac) if s.action == action]


def shortcut_rows(action: str, *, mac: bool = IS_MAC) -> list[Shortcut]:
    """All table rows of an action."""
    return [s for s in shortcuts_for(mac=mac) if s.action == action]
