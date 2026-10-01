"""Vault dialogs and ``ensure_vault_unlocked()`` (SPEC §9.3)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pyssh import strings
from pyssh.core.vault import MIN_MASTER_PASSWORD_LEN, Vault, VaultState
from pyssh.ui.dialogs import wait_cursor

RESULT_RESET = 2
ERROR_STYLE = "color: #C50F1F;"


def validate_new_password(password: str, confirm: str) -> str | None:
    """Return an error message for a new master password, or ``None`` when valid."""
    if len(password) < MIN_MASTER_PASSWORD_LEN:
        return strings.VAULT_ERR_TOO_SHORT.format(min=MIN_MASTER_PASSWORD_LEN)
    if password != confirm:
        return strings.VAULT_ERR_MISMATCH
    return None


def _password_edit() -> QLineEdit:
    edit = QLineEdit()
    edit.setEchoMode(QLineEdit.EchoMode.Password)
    return edit


def _error_label() -> QLabel:
    label = QLabel()
    label.setStyleSheet(ERROR_STYLE)
    label.setWordWrap(True)
    label.hide()
    return label


def _show_error(label: QLabel, message: str | None) -> None:
    label.setText(message or "")
    label.setVisible(bool(message))


def confirm_reset(parent: QWidget | None) -> bool:
    """Ask before deleting all stored secrets."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(strings.VAULT_RESET_TITLE)
    box.setText(strings.VAULT_RESET_CONFIRM)
    reset_button = box.addButton(strings.VAULT_RESET_BUTTON, QMessageBox.ButtonRole.DestructiveRole)
    cancel_button = box.addButton(strings.VAULT_BUTTON_CANCEL, QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(cancel_button)
    box.exec()
    return box.clickedButton() is reset_button


class CreateMasterPasswordDialog(QDialog):
    """Create the vault with a new master password."""

    def __init__(self, vault: Vault, parent: QWidget | None = None) -> None:
        """Build the form; the Create button stays disabled while the input is invalid."""
        super().__init__(parent)
        self._vault = vault
        self.setWindowTitle(strings.VAULT_CREATE_TITLE)
        self.password_edit = _password_edit()
        self.confirm_edit = _password_edit()
        self.error_label = _error_label()

        info = QLabel(strings.VAULT_CREATE_INFO)
        info.setWordWrap(True)
        warning = QLabel(strings.VAULT_CREATE_WARNING)
        warning.setWordWrap(True)
        warning.setStyleSheet("font-weight: bold;")

        form = QFormLayout()
        form.addRow(strings.VAULT_FIELD_PASSWORD, self.password_edit)
        form.addRow(strings.VAULT_FIELD_CONFIRM, self.confirm_edit)

        buttons = QDialogButtonBox()
        self.create_button = buttons.addButton(
            strings.VAULT_BUTTON_CREATE, QDialogButtonBox.ButtonRole.AcceptRole
        )
        buttons.addButton(strings.VAULT_BUTTON_CANCEL, QDialogButtonBox.ButtonRole.RejectRole)
        self.create_button.clicked.connect(self._create)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(info)
        layout.addWidget(warning)
        layout.addLayout(form)
        layout.addWidget(self.error_label)
        layout.addWidget(buttons)

        self.password_edit.textChanged.connect(self._update)
        self.confirm_edit.textChanged.connect(self._update)
        self._update()

    def _update(self) -> None:
        password, confirm = self.password_edit.text(), self.confirm_edit.text()
        message = validate_new_password(password, confirm)
        self.create_button.setEnabled(message is None)
        _show_error(self.error_label, message if (password or confirm) else None)

    def _create(self) -> None:
        if validate_new_password(self.password_edit.text(), self.confirm_edit.text()):
            return
        with wait_cursor():
            self._vault.initialize(self.password_edit.text())
        self.password_edit.clear()
        self.confirm_edit.clear()
        self.accept()


class UnlockDialog(QDialog):
    """Unlock the vault. Returns ``Accepted``, ``Rejected`` or ``RESULT_RESET``."""

    def __init__(
        self, vault: Vault, parent: QWidget | None = None, *, startup: bool = False
    ) -> None:
        """``startup=True`` labels the reject button "Lewati" instead of "Batal"."""
        super().__init__(parent)
        self._vault = vault
        self.setWindowTitle(strings.VAULT_UNLOCK_TITLE)
        self.password_edit = _password_edit()
        self.error_label = _error_label()

        buttons = QDialogButtonBox()
        self.unlock_button = buttons.addButton(
            strings.VAULT_BUTTON_UNLOCK, QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.reject_button = buttons.addButton(
            strings.VAULT_BUTTON_SKIP if startup else strings.VAULT_BUTTON_CANCEL,
            QDialogButtonBox.ButtonRole.RejectRole,
        )
        self.unlock_button.setDefault(True)
        self.unlock_button.clicked.connect(self._unlock)
        buttons.rejected.connect(self.reject)

        self.forgot_button = QPushButton(strings.VAULT_FORGOT_LINK)
        self.forgot_button.setFlat(True)
        self.forgot_button.setAutoDefault(False)
        self.forgot_button.clicked.connect(self._forgot)

        info = QLabel(strings.VAULT_UNLOCK_INFO)
        info.setWordWrap(True)
        form = QFormLayout()
        form.addRow(strings.VAULT_FIELD_PASSWORD, self.password_edit)

        layout = QVBoxLayout(self)
        layout.addWidget(info)
        layout.addLayout(form)
        layout.addWidget(self.error_label)
        layout.addWidget(self.forgot_button)
        layout.addWidget(buttons)

    def _unlock(self) -> None:
        with wait_cursor():
            ok = self._vault.unlock(self.password_edit.text())
        self.password_edit.clear()
        if ok:
            self.accept()
        else:
            _show_error(self.error_label, strings.VAULT_ERR_WRONG)
            self.password_edit.setFocus()

    def _forgot(self) -> None:
        if confirm_reset(self):
            self._vault.reset()
            self.done(RESULT_RESET)


class ChangeMasterPasswordDialog(QDialog):
    """Change the master password (re-wraps the DEK)."""

    def __init__(self, vault: Vault, parent: QWidget | None = None) -> None:
        """Build the form with old, new and confirmation fields."""
        super().__init__(parent)
        self._vault = vault
        self.setWindowTitle(strings.VAULT_CHANGE_TITLE)
        self.old_edit = _password_edit()
        self.new_edit = _password_edit()
        self.confirm_edit = _password_edit()
        self.error_label = _error_label()

        form = QFormLayout()
        form.addRow(strings.VAULT_FIELD_OLD, self.old_edit)
        form.addRow(strings.VAULT_FIELD_NEW, self.new_edit)
        form.addRow(strings.VAULT_FIELD_CONFIRM, self.confirm_edit)

        buttons = QDialogButtonBox()
        self.change_button = buttons.addButton(
            strings.VAULT_BUTTON_CHANGE, QDialogButtonBox.ButtonRole.AcceptRole
        )
        buttons.addButton(strings.VAULT_BUTTON_CANCEL, QDialogButtonBox.ButtonRole.RejectRole)
        self.change_button.clicked.connect(self._change)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.error_label)
        layout.addWidget(buttons)

        for edit in (self.old_edit, self.new_edit, self.confirm_edit):
            edit.textChanged.connect(self._update)
        self._update()

    def _update(self) -> None:
        new, confirm = self.new_edit.text(), self.confirm_edit.text()
        message = validate_new_password(new, confirm)
        self.change_button.setEnabled(message is None and bool(self.old_edit.text()))
        _show_error(self.error_label, message if (new or confirm) else None)

    def _change(self) -> None:
        if not self.change_button.isEnabled():
            return
        with wait_cursor():
            ok = self._vault.change_master_password(self.old_edit.text(), self.new_edit.text())
        if ok:
            for edit in (self.old_edit, self.new_edit, self.confirm_edit):
                edit.clear()
            self.accept()
        else:
            self.old_edit.clear()
            _show_error(self.error_label, strings.VAULT_ERR_WRONG_OLD)


def ensure_vault_unlocked(parent: QWidget | None, vault: Vault) -> bool:
    """Make sure the vault is UNLOCKED, asking the user when needed (SPEC §9.3).

    LOCKED → unlock dialog (no "Lewati"); if the user resets the vault from that dialog,
    the create dialog follows. UNINITIALIZED → create dialog.
    """
    if vault.state is VaultState.UNLOCKED:
        return True
    if vault.state is VaultState.LOCKED:
        result = UnlockDialog(vault, parent).exec()
        if vault.state is VaultState.UNLOCKED:
            return True
        if result != RESULT_RESET:
            return False
    CreateMasterPasswordDialog(vault, parent).exec()
    return vault.state is VaultState.UNLOCKED
