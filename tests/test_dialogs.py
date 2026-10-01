"""Tests for ui.dialogs: PasswordDialog and HostKeyDialog (SPEC §9.7)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QDialog, QMessageBox

from pyssh.core.ssh_worker import HostKeyDecision
from pyssh.ui.dialogs import HostKeyDialog, PasswordDialog, confirm


def _password_dialog(qtbot, **kwargs) -> PasswordDialog:
    dialog = PasswordDialog(title="Password", prompt="Password untuk a@b:22", **kwargs)
    qtbot.addWidget(dialog)
    return dialog


def test_password_dialog_returns_secret_and_remember(qtbot, monkeypatch) -> None:
    dialog = _password_dialog(qtbot, remember_default=True)

    def accept(self) -> int:
        self.secret_edit.setText("pw-123")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(PasswordDialog, "exec", accept)
    assert dialog.ask() == ("pw-123", True)
    assert dialog.secret_edit.text() == ""  # cleared after use


def test_password_dialog_hidden_remember_is_false(qtbot, monkeypatch) -> None:
    dialog = _password_dialog(qtbot, show_remember=False, remember_default=True)
    monkeypatch.setattr(PasswordDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    assert dialog.ask() == ("", False)
    assert dialog.remember_check.isHidden()


def test_password_dialog_cancel(qtbot, monkeypatch) -> None:
    dialog = _password_dialog(qtbot, error="Password salah, coba lagi.")
    assert dialog.error_label.text() == "Password salah, coba lagi."
    assert not dialog.error_label.isHidden()
    monkeypatch.setattr(PasswordDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    assert dialog.ask() is None


def test_password_dialog_no_error_label(qtbot) -> None:
    assert _password_dialog(qtbot).error_label.isHidden()


@pytest.mark.parametrize(
    ("button", "decision"),
    [
        ("accept_save_button", HostKeyDecision.ACCEPT_SAVE),
        ("accept_once_button", HostKeyDecision.ACCEPT_ONCE),
        ("cancel_button", HostKeyDecision.REJECT),
    ],
)
def test_host_key_dialog_buttons(qtbot, monkeypatch, button: str, decision) -> None:
    dialog = HostKeyDialog("srv", 2222, "ssh-ed25519", "SHA256:abc")
    qtbot.addWidget(dialog)
    assert dialog.accept_save_button.isDefault()
    assert dialog.fingerprint_label.text() == "SHA256:abc"
    monkeypatch.setattr(HostKeyDialog, "exec", lambda self: getattr(self, button).click() or 0)
    assert dialog.ask() is decision


def test_host_key_dialog_closed_is_reject(qtbot, monkeypatch) -> None:
    dialog = HostKeyDialog("srv", 22, "ssh-rsa", "SHA256:x")
    qtbot.addWidget(dialog)
    monkeypatch.setattr(HostKeyDialog, "exec", lambda self: 0)
    assert dialog.ask() is HostKeyDecision.REJECT


def test_confirm(monkeypatch) -> None:
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Yes)
    assert confirm(None, "t", "x") is True
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.No)
    assert confirm(None, "t", "x") is False
