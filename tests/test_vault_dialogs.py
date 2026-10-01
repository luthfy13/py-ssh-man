"""Tests for ui.vault_dialogs (SPEC §9.3)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QDialog

from pyssh import strings
from pyssh.core.vault import VaultState
from pyssh.ui import vault_dialogs
from pyssh.ui.vault_dialogs import (
    RESULT_RESET,
    ChangeMasterPasswordDialog,
    CreateMasterPasswordDialog,
    UnlockDialog,
    ensure_vault_unlocked,
    validate_new_password,
)

MASTER = "master-pass-1"


@pytest.mark.parametrize(
    ("password", "confirm", "expected"),
    [
        ("", "", strings.VAULT_ERR_TOO_SHORT.format(min=8)),
        ("1234567", "1234567", strings.VAULT_ERR_TOO_SHORT.format(min=8)),
        ("12345678", "12345679", strings.VAULT_ERR_MISMATCH),
        ("12345678", "12345678", None),
    ],
)
def test_validate_new_password(password: str, confirm: str, expected: str | None) -> None:
    assert validate_new_password(password, confirm) == expected


def test_create_dialog(qtbot, services) -> None:
    dialog = CreateMasterPasswordDialog(services.vault)
    qtbot.addWidget(dialog)
    assert not dialog.create_button.isEnabled()
    assert dialog.error_label.isHidden()
    dialog.password_edit.setText("short")
    assert not dialog.create_button.isEnabled()
    assert dialog.error_label.text() == strings.VAULT_ERR_TOO_SHORT.format(min=8)
    dialog.password_edit.setText(MASTER)
    dialog.confirm_edit.setText(MASTER + "x")
    assert dialog.error_label.text() == strings.VAULT_ERR_MISMATCH
    dialog.confirm_edit.setText(MASTER)
    assert dialog.create_button.isEnabled()
    assert dialog.error_label.isHidden()
    dialog.create_button.click()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert services.vault.state is VaultState.UNLOCKED
    assert dialog.password_edit.text() == ""


def test_unlock_dialog(qtbot, services) -> None:
    services.vault.initialize(MASTER)
    services.vault.lock()
    dialog = UnlockDialog(services.vault)
    qtbot.addWidget(dialog)
    assert dialog.reject_button.text() == strings.VAULT_BUTTON_CANCEL
    dialog.password_edit.setText("wrong-password")
    dialog.unlock_button.click()
    assert dialog.error_label.text() == strings.VAULT_ERR_WRONG
    assert not dialog.error_label.isHidden()
    assert services.vault.state is VaultState.LOCKED
    dialog.password_edit.setText(MASTER)
    dialog.unlock_button.click()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert services.vault.state is VaultState.UNLOCKED


def test_unlock_dialog_startup_has_skip(qtbot, services) -> None:
    dialog = UnlockDialog(services.vault, startup=True)
    qtbot.addWidget(dialog)
    assert dialog.reject_button.text() == strings.VAULT_BUTTON_SKIP
    assert dialog.unlock_button.isDefault()


def test_reset_from_unlock_dialog(qtbot, services, monkeypatch: pytest.MonkeyPatch) -> None:
    services.vault.initialize(MASTER)
    services.vault.lock()
    dialog = UnlockDialog(services.vault)
    qtbot.addWidget(dialog)
    monkeypatch.setattr(vault_dialogs, "confirm_reset", lambda parent: False)
    dialog.forgot_button.click()
    assert services.vault.state is VaultState.LOCKED
    monkeypatch.setattr(vault_dialogs, "confirm_reset", lambda parent: True)
    dialog.forgot_button.click()
    assert services.vault.state is VaultState.UNINITIALIZED
    assert dialog.result() == RESULT_RESET


def test_change_dialog(qtbot, services) -> None:
    services.vault.initialize(MASTER)
    dialog = ChangeMasterPasswordDialog(services.vault)
    qtbot.addWidget(dialog)
    assert not dialog.change_button.isEnabled()
    dialog.new_edit.setText("new-master-2")
    dialog.confirm_edit.setText("new-master-2")
    assert not dialog.change_button.isEnabled()  # old password still empty
    dialog.old_edit.setText("wrong-password")
    assert dialog.change_button.isEnabled()
    dialog.change_button.click()
    assert dialog.error_label.text() == strings.VAULT_ERR_WRONG_OLD
    assert dialog.old_edit.text() == ""
    dialog.old_edit.setText(MASTER)
    dialog.change_button.click()
    assert dialog.result() == QDialog.DialogCode.Accepted
    services.vault.lock()
    assert services.vault.unlock("new-master-2") is True


def test_change_dialog_validation(qtbot, services) -> None:
    dialog = ChangeMasterPasswordDialog(services.vault)
    qtbot.addWidget(dialog)
    dialog.old_edit.setText(MASTER)
    dialog.new_edit.setText("short")
    assert dialog.error_label.text() == strings.VAULT_ERR_TOO_SHORT.format(min=8)
    assert not dialog.change_button.isEnabled()


def _patch_exec(monkeypatch: pytest.MonkeyPatch, cls, action) -> list[str]:
    calls: list[str] = []

    def fake_exec(self):
        calls.append(cls.__name__)
        return action(self)

    monkeypatch.setattr(cls, "exec", fake_exec)
    return calls


def test_ensure_when_unlocked(services, monkeypatch: pytest.MonkeyPatch) -> None:
    services.vault.initialize(MASTER)
    calls = _patch_exec(monkeypatch, UnlockDialog, lambda self: 0)
    assert ensure_vault_unlocked(None, services.vault) is True
    assert calls == []


def test_ensure_when_locked(qapp, services, monkeypatch: pytest.MonkeyPatch) -> None:
    services.vault.initialize(MASTER)
    services.vault.lock()

    def unlock(dialog: UnlockDialog) -> int:
        dialog.password_edit.setText(MASTER)
        dialog.unlock_button.click()
        return dialog.result()

    calls = _patch_exec(monkeypatch, UnlockDialog, unlock)
    assert ensure_vault_unlocked(None, services.vault) is True
    assert calls == ["UnlockDialog"]


def test_ensure_when_locked_cancelled(qapp, services, monkeypatch: pytest.MonkeyPatch) -> None:
    services.vault.initialize(MASTER)
    services.vault.lock()
    _patch_exec(monkeypatch, UnlockDialog, lambda self: QDialog.DialogCode.Rejected.value)
    create_calls = _patch_exec(monkeypatch, CreateMasterPasswordDialog, lambda self: 0)
    assert ensure_vault_unlocked(None, services.vault) is False
    assert create_calls == []
    assert services.vault.state is VaultState.LOCKED


def test_ensure_when_locked_then_reset_creates(
    qapp, services, monkeypatch: pytest.MonkeyPatch
) -> None:
    services.vault.initialize(MASTER)
    services.vault.lock()

    def reset(dialog: UnlockDialog) -> int:
        services.vault.reset()
        return RESULT_RESET

    def create(dialog: CreateMasterPasswordDialog) -> int:
        dialog.password_edit.setText("brand-new-pass")
        dialog.confirm_edit.setText("brand-new-pass")
        dialog.create_button.click()
        return dialog.result()

    _patch_exec(monkeypatch, UnlockDialog, reset)
    calls = _patch_exec(monkeypatch, CreateMasterPasswordDialog, create)
    assert ensure_vault_unlocked(None, services.vault) is True
    assert calls == ["CreateMasterPasswordDialog"]


def test_ensure_when_uninitialized(qapp, services, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch_exec(monkeypatch, CreateMasterPasswordDialog, lambda self: 0)
    assert ensure_vault_unlocked(None, services.vault) is False
    assert calls == ["CreateMasterPasswordDialog"]

    def create(dialog: CreateMasterPasswordDialog) -> int:
        dialog.password_edit.setText(MASTER)
        dialog.confirm_edit.setText(MASTER)
        dialog.create_button.click()
        return dialog.result()

    _patch_exec(monkeypatch, CreateMasterPasswordDialog, create)
    assert ensure_vault_unlocked(None, services.vault) is True
    assert services.vault.state is VaultState.UNLOCKED


def test_confirm_reset_buttons(qapp, monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtWidgets import QMessageBox

    def click_reset(box: QMessageBox) -> int:
        for button in box.buttons():
            if button.text() == strings.VAULT_RESET_BUTTON:
                button.click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", click_reset)
    assert vault_dialogs.confirm_reset(None) is True
    monkeypatch.setattr(QMessageBox, "exec", lambda box: 0)
    assert vault_dialogs.confirm_reset(None) is False
