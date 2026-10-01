"""Tests for shortcuts (SPEC §8.3.2)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt

from pyssh.shortcuts import (
    is_app_shortcut,
    match,
    sequences_for,
    shortcut_rows,
    shortcuts_for,
    zoom_wheel_modifier,
)

K = Qt.Key
M = Qt.KeyboardModifier
C, S, A, META = M.ControlModifier, M.ShiftModifier, M.AltModifier, M.MetaModifier

# (action, mods, key) for every key code variant of the table, Windows/Linux.
DEFAULT_ROWS = [
    ("new_session", C | S, K.Key_N),
    ("close_tab", C | S, K.Key_W),
    ("reconnect", C | S, K.Key_R),
    ("next_tab", C, K.Key_Tab),
    ("prev_tab", C | S, K.Key_Tab),
    ("prev_tab", C | S, K.Key_Backtab),
    ("zoom_in", C | S, K.Key_Equal),
    ("zoom_in", C | S, K.Key_Plus),
    ("zoom_out", C | S, K.Key_Minus),
    ("zoom_out", C | S, K.Key_Underscore),
    ("zoom_reset", C | S, K.Key_0),
    ("zoom_reset", C | S, K.Key_ParenRight),
    ("toggle_panel", C | S, K.Key_B),
    ("copy", C | S, K.Key_C),
    ("paste", C | S, K.Key_V),
    ("scroll_page_up", S, K.Key_PageUp),
    ("scroll_page_down", S, K.Key_PageDown),
]
MAC_ROWS = [
    ("new_session", META, K.Key_N),
    ("close_tab", META, K.Key_W),
    ("reconnect", META, K.Key_R),
    ("next_tab", C, K.Key_Tab),
    ("next_tab", META | S, K.Key_BracketRight),
    ("next_tab", META | S, K.Key_BraceRight),
    ("prev_tab", C | S, K.Key_Tab),
    ("prev_tab", C | S, K.Key_Backtab),
    ("prev_tab", META | S, K.Key_BracketLeft),
    ("prev_tab", META | S, K.Key_BraceLeft),
    ("zoom_in", META, K.Key_Equal),
    ("zoom_in", META, K.Key_Plus),
    ("zoom_out", META, K.Key_Minus),
    ("zoom_out", META, K.Key_Underscore),
    ("zoom_reset", META, K.Key_0),
    ("zoom_reset", META, K.Key_ParenRight),
    ("toggle_panel", META, K.Key_B),
    ("copy", META, K.Key_C),
    ("paste", META, K.Key_V),
    ("scroll_page_up", S, K.Key_PageUp),
    ("scroll_page_down", S, K.Key_PageDown),
]
WIDGET_ACTIONS = {"copy", "paste", "scroll_page_up", "scroll_page_down"}


@pytest.mark.parametrize(("action", "mods", "key"), DEFAULT_ROWS)
def test_default_table(action: str, mods, key) -> None:
    found = match(int(key), mods, mac=False)
    assert found is not None and found.action == action
    assert is_app_shortcut(int(key), mods, mac=False) is (action not in WIDGET_ACTIONS)


@pytest.mark.parametrize(("action", "mods", "key"), MAC_ROWS)
def test_mac_table(action: str, mods, key) -> None:
    found = match(int(key), mods, mac=True)
    assert found is not None and found.action == action
    assert is_app_shortcut(int(key), mods, mac=True) is (action not in WIDGET_ACTIONS)


def test_keypad_modifier_is_ignored() -> None:
    assert match(int(K.Key_Plus), C | S | M.KeypadModifier, mac=False).action == "zoom_in"


@pytest.mark.parametrize(
    ("key", "mods"),
    [
        (K.Key_C, C),
        (K.Key_D, C),
        (K.Key_W, C),
        (K.Key_R, C),
        (K.Key_2, C | S),
        (K.Key_At, C | S),
        (K.Key_6, C | S),
        (K.Key_AsciiCircum, C | S),
        (K.Key_N, C | S | A),
        (K.Key_N, META),  # Windows/Super key is not an app shortcut on Windows/Linux
    ],
)
def test_terminal_keys_are_not_app_shortcuts_on_default(key, mods) -> None:
    assert is_app_shortcut(int(key), mods, mac=False) is False


def test_other_cmd_combinations_are_app_shortcuts_on_mac() -> None:
    assert is_app_shortcut(int(K.Key_K), META, mac=True) is True
    assert is_app_shortcut(int(K.Key_Q), META | S, mac=True) is True
    assert is_app_shortcut(int(K.Key_C), META, mac=True) is False  # copy: widget
    assert is_app_shortcut(int(K.Key_V), META, mac=True) is False  # paste: widget
    assert is_app_shortcut(int(K.Key_C), C, mac=True) is False  # Ctrl+C goes to the server


def test_ctrl_shift_letters_not_in_table_go_to_terminal() -> None:
    assert match(int(K.Key_A), C | S, mac=False) is None
    assert is_app_shortcut(int(K.Key_A), C | S, mac=False) is False


def test_sequences_and_rows() -> None:
    assert sequences_for("next_tab", mac=True) == ["Ctrl+Tab", "Meta+Shift+]"]
    assert sequences_for("copy", mac=False) == ["Ctrl+Shift+C"]
    assert len(shortcut_rows("prev_tab", mac=True)) == 2
    actions = {s.action for s in shortcuts_for(mac=False)}
    assert actions == {s.action for s in shortcuts_for(mac=True)}


def test_zoom_wheel_modifier() -> None:
    assert zoom_wheel_modifier(mac=False) == C
    assert zoom_wheel_modifier(mac=True) == META
