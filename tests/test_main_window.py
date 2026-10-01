"""Tests for ui.main_window (SPEC §9.1)."""

from __future__ import annotations

import pytest

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
