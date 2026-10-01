"""Password, host key and confirmation dialogs (SPEC §9.7), plus small UI helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from pyssh import strings
from pyssh.core.ssh_worker import HostKeyDecision

ERROR_STYLE = "color: #C50F1F;"


@contextmanager
def wait_cursor() -> Iterator[None]:
    """Show the wait cursor while a slow GUI-thread operation runs (rule A1 exception)."""
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        yield
    finally:
        QApplication.restoreOverrideCursor()


class PasswordDialog(QDialog):
    """Ask for a password or passphrase, optionally with a "remember" checkbox."""

    def __init__(
        self,
        *,
        title: str,
        prompt: str,
        field_label: str = strings.PASSWORD_FIELD,
        remember_label: str = strings.PASSWORD_REMEMBER,
        error: str | None = None,
        show_remember: bool = True,
        remember_default: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        """Build the dialog; ``error`` is shown in red above the field."""
        super().__init__(parent)
        self.setWindowTitle(title)
        self.prompt_label = QLabel(prompt)
        self.prompt_label.setWordWrap(True)
        self.error_label = QLabel(error or "")
        self.error_label.setStyleSheet(ERROR_STYLE)
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(bool(error))
        self.secret_edit = QLineEdit()
        self.secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.remember_check = QCheckBox(remember_label)
        self.remember_check.setChecked(remember_default)
        self.remember_check.setVisible(show_remember)
        self._show_remember = show_remember

        form = QFormLayout()
        form.addRow(field_label, self.secret_edit)
        buttons = QDialogButtonBox()
        ok = buttons.addButton(strings.BUTTON_OK, QDialogButtonBox.ButtonRole.AcceptRole)
        ok.setDefault(True)
        buttons.addButton(strings.BUTTON_CANCEL, QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.prompt_label)
        layout.addWidget(self.error_label)
        layout.addLayout(form)
        layout.addWidget(self.remember_check)
        layout.addWidget(buttons)
        self.secret_edit.setFocus()

    def ask(self) -> tuple[str, bool] | None:
        """Run the dialog; ``(secret, remember)`` or ``None`` when cancelled."""
        if self.exec() != QDialog.DialogCode.Accepted:
            self.secret_edit.clear()
            return None
        secret = self.secret_edit.text()
        self.secret_edit.clear()
        return secret, self._show_remember and self.remember_check.isChecked()


class HostKeyDialog(QDialog):
    """Show an unknown host key fingerprint and ask whether to trust it."""

    def __init__(
        self, host: str, port: int, key_type: str, fingerprint: str, parent: QWidget | None = None
    ) -> None:
        """Build the dialog; "Terima & Simpan" is the default button."""
        super().__init__(parent)
        self.setWindowTitle(strings.HOSTKEY_TITLE)
        self._decision = HostKeyDecision.REJECT

        fingerprint_label = QLabel(fingerprint)
        fingerprint_label.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        fingerprint_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.fingerprint_label = fingerprint_label

        buttons = QDialogButtonBox()
        self.accept_save_button = buttons.addButton(
            strings.HOSTKEY_ACCEPT_SAVE, QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.accept_once_button = buttons.addButton(
            strings.HOSTKEY_ACCEPT_ONCE, QDialogButtonBox.ButtonRole.ActionRole
        )
        self.cancel_button = buttons.addButton(
            strings.BUTTON_CANCEL, QDialogButtonBox.ButtonRole.RejectRole
        )
        self.accept_save_button.setDefault(True)
        self.accept_save_button.clicked.connect(lambda: self._finish(HostKeyDecision.ACCEPT_SAVE))
        self.accept_once_button.clicked.connect(lambda: self._finish(HostKeyDecision.ACCEPT_ONCE))
        self.cancel_button.clicked.connect(lambda: self._finish(HostKeyDecision.REJECT))

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(strings.HOSTKEY_UNKNOWN.format(host=host, port=port)))
        layout.addWidget(QLabel(strings.HOSTKEY_TYPE.format(key_type=key_type)))
        layout.addWidget(QLabel(strings.HOSTKEY_FINGERPRINT))
        layout.addWidget(fingerprint_label)
        verify = QLabel(strings.HOSTKEY_VERIFY)
        verify.setWordWrap(True)
        layout.addWidget(verify)
        layout.addWidget(buttons)

    def _finish(self, decision: HostKeyDecision) -> None:
        self._decision = decision
        if decision is HostKeyDecision.REJECT:
            self.reject()
        else:
            self.accept()

    def ask(self) -> HostKeyDecision:
        """Run the dialog; closing it counts as REJECT."""
        self._decision = HostKeyDecision.REJECT
        self.exec()
        return self._decision


def confirm(parent: QWidget | None, title: str, text: str) -> bool:
    """Yes/No question; ``True`` for Yes."""
    answer = QMessageBox.question(
        parent,
        title,
        text,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return answer == QMessageBox.StandardButton.Yes
