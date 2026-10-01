"""Tests for ui.main_window (SPEC §9.1)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt

from pyssh import strings
from pyssh.ui import main_window as main_window_module
from pyssh.ui.main_window import MainWindow
from pyssh.ui.vault_dialogs import (
    ChangeMasterPasswordDialog,
    CreateMasterPasswordDialog,
    UnlockDialog,
)

MASTER = "master-pass-1"


@pytest.fixture
def window(qtbot, services) -> MainWindow:
    w = MainWindow(services)
    qtbot.addWidget(w)
    return w


def _visible(window: MainWindow) -> set[str]:
    actions = {
        "create": window.action_vault_create,
        "unlock": window.action_vault_unlock,
        "lock": window.action_vault_lock,
        "change": window.action_vault_change,
        "reset": window.action_vault_reset,
    }
    return {name for name, action in actions.items() if action.isVisible()}


def test_vault_menu_follows_state(window: MainWindow, services) -> None:
    state_text = window.vault_label.text
    assert _visible(window) == {"create"}
    assert state_text() == strings.VAULT_STATUS.format(state=strings.VAULT_STATE_UNINITIALIZED)
    services.vault.initialize(MASTER)
    assert _visible(window) == {"lock", "change", "reset"}
    assert state_text() == strings.VAULT_STATUS.format(state=strings.VAULT_STATE_UNLOCKED)
    window.action_vault_lock.trigger()
    assert _visible(window) == {"unlock", "change", "reset"}
    assert state_text() == strings.VAULT_STATUS.format(state=strings.VAULT_STATE_LOCKED)


def test_vault_actions_open_dialogs(
    window: MainWindow, services, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[str] = []
    for cls in (CreateMasterPasswordDialog, UnlockDialog, ChangeMasterPasswordDialog):
        monkeypatch.setattr(cls, "exec", lambda self, n=cls.__name__: opened.append(n) or 0)
    window.action_vault_create.trigger()
    window.action_vault_unlock.trigger()
    window.action_vault_change.trigger()
    assert opened == [
        "CreateMasterPasswordDialog",
        "UnlockDialog",
        "ChangeMasterPasswordDialog",
    ]


def test_vault_reset_action(window: MainWindow, services, monkeypatch: pytest.MonkeyPatch) -> None:
    services.vault.initialize(MASTER)
    monkeypatch.setattr(main_window_module, "confirm_reset", lambda parent: False)
    window.action_vault_reset.trigger()
    assert _visible(window) == {"lock", "change", "reset"}
    monkeypatch.setattr(main_window_module, "confirm_reset", lambda parent: True)
    window.action_vault_reset.trigger()
    assert _visible(window) == {"create"}


def test_quit_action_closes(window: MainWindow, qtbot) -> None:
    window.show()
    qtbot.waitExposed(window)
    window.action_quit.trigger()
    assert not window.isVisible()


def test_demo_tab_and_grid_label(window: MainWindow, qtbot) -> None:
    window.show()
    qtbot.waitExposed(window)
    view = window.open_demo_tab()
    assert window.tabs.count() == 1
    assert window.tabs.tabText(0) == strings.DEMO_TAB_TITLE
    assert window.active_terminal() is view.terminal
    cols, rows = view.terminal.grid_size()
    qtbot.waitUntil(lambda: window.grid_label.text() == f"{cols}×{rows}", timeout=2000)


def test_tab_navigation_and_close(window: MainWindow, qtbot) -> None:
    window.show()
    qtbot.waitExposed(window)
    for _ in range(3):
        window.open_demo_tab()
    assert window.tabs.currentIndex() == 2
    window.action_next_tab.trigger()
    assert window.tabs.currentIndex() == 0
    window.action_prev_tab.trigger()
    assert window.tabs.currentIndex() == 2
    window.action_close_tab.trigger()
    assert window.tabs.count() == 2
    window.close_tab(99)  # unknown index: ignored
    window.close_current_tab()
    window.close_current_tab()
    assert window.tabs.count() == 0
    assert window.grid_label.text() == ""
    window.action_close_tab.trigger()
    window.action_next_tab.trigger()
    window.action_zoom_in.trigger()  # no terminal: no error


def test_zoom_actions_target_active_terminal(window: MainWindow, qtbot) -> None:
    window.show()
    view = window.open_demo_tab()
    window.action_zoom_in.trigger()
    assert view.terminal.font_size == 12
    window.action_zoom_out.trigger()
    window.action_zoom_out.trigger()
    assert view.terminal.font_size == 10
    window.action_zoom_reset.trigger()
    assert view.terminal.font_size == 11


def test_actions_use_shortcut_table() -> None:
    from PySide6.QtGui import QKeySequence

    from pyssh.ui.main_window import key_sequences

    zoom_in = key_sequences("zoom_in", mac=False)
    assert zoom_in[0] == QKeySequence("Ctrl+Shift+=")
    assert QKeySequence("Ctrl+Shift++") in zoom_in
    prev_tab = key_sequences("prev_tab", mac=False)
    assert QKeySequence("Ctrl+Shift+Tab") in prev_tab
    assert key_sequences("next_tab", mac=True)[0] == QKeySequence("Ctrl+Tab")
    assert QKeySequence("Meta+Shift+]") in key_sequences("next_tab", mac=True)


def test_ctrl_tab_switches_tabs_through_terminal(window: MainWindow, qtbot) -> None:
    window.show()
    qtbot.waitExposed(window)
    window.open_demo_tab()
    second = window.open_demo_tab()
    second.terminal.setFocus()
    qtbot.waitUntil(second.terminal.hasFocus, timeout=2000)
    qtbot.keyClick(second.terminal, Qt.Key.Key_Tab, Qt.KeyboardModifier.ControlModifier)
    assert window.tabs.currentIndex() == 0
