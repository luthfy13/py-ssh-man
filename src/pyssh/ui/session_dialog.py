"""Dialog for creating and editing sessions (SPEC §6.6, §9.5)."""

from __future__ import annotations

import os
import uuid
from dataclasses import replace
from pathlib import Path

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pyssh import strings
from pyssh.core.vault import VaultState
from pyssh.models import NAME_MAX_LEN, PORT_MAX, PORT_MIN, AuthType, SessionConfig, now_iso
from pyssh.services import AppServices
from pyssh.ui.vault_dialogs import ensure_vault_unlocked

ERROR_STYLE = "color: #C50F1F;"
HINT_STYLE = "color: gray;"


def normalize_host(text: str) -> str:
    """Trim and remove IPv6 brackets (``[::1]`` → ``::1``)."""
    host = text.strip()
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    return host


def key_file_exists(path: str) -> bool:
    """True when the (``~``-expanded) path is an existing file."""
    return os.path.isfile(os.path.expanduser(path))


class SessionDialog(QDialog):
    """Create (``session=None``) or edit a session; ``saved_session`` holds the result."""

    def __init__(
        self,
        services: AppServices,
        session: SessionConfig | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Build the form, pre-filled when editing."""
        super().__init__(parent)
        self._services = services
        self._original = session
        self.saved_session: SessionConfig | None = None
        self.setWindowTitle(strings.SESSION_EDIT_TITLE if session else strings.SESSION_NEW_TITLE)

        self.name_edit = QLineEdit()
        self.name_edit.setMaxLength(NAME_MAX_LEN)
        self.host_edit = QLineEdit()
        self.port_spin = QSpinBox()
        self.port_spin.setRange(PORT_MIN, PORT_MAX)
        self.port_spin.setValue(22)
        self.username_edit = QLineEdit()
        self.password_radio = QRadioButton(strings.AUTH_PASSWORD)
        self.key_radio = QRadioButton(strings.AUTH_KEY)
        self._auth_group = QButtonGroup(self)
        self._auth_group.addButton(self.password_radio)
        self._auth_group.addButton(self.key_radio)
        self.password_radio.setChecked(True)
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_path_edit = QLineEdit()
        self.browse_button = QPushButton(strings.BROWSE)
        self.passphrase_edit = QLineEdit()
        self.passphrase_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.remember_check = QCheckBox(strings.REMEMBER_SECRET)
        self.vault_hint = QLabel()
        self.vault_hint.setStyleSheet(HINT_STYLE)
        self.error_label = QLabel()
        self.error_label.setStyleSheet(ERROR_STYLE)
        self.error_label.setWordWrap(True)

        auth_row = QHBoxLayout()
        auth_row.addWidget(self.password_radio)
        auth_row.addWidget(self.key_radio)
        auth_row.addStretch(1)
        key_row = QHBoxLayout()
        key_row.addWidget(self.key_path_edit, 1)
        key_row.addWidget(self.browse_button)
        self._key_row_widget = QWidget()
        self._key_row_widget.setLayout(key_row)
        key_row.setContentsMargins(0, 0, 0, 0)

        self.form = QFormLayout()
        self.form.addRow(strings.FIELD_NAME, self.name_edit)
        self.form.addRow(strings.FIELD_HOST, self.host_edit)
        self.form.addRow(strings.FIELD_PORT, self.port_spin)
        self.form.addRow(strings.FIELD_USERNAME, self.username_edit)
        self.form.addRow(strings.FIELD_AUTH, auth_row)
        self.form.addRow(strings.FIELD_PASSWORD, self.password_edit)
        self.form.addRow(strings.FIELD_KEY_PATH, self._key_row_widget)
        self.form.addRow(strings.FIELD_PASSPHRASE, self.passphrase_edit)
        self.form.addRow("", self.remember_check)
        self.form.addRow("", self.vault_hint)

        buttons = QDialogButtonBox()
        self.save_button = buttons.addButton(
            strings.BUTTON_SAVE, QDialogButtonBox.ButtonRole.AcceptRole
        )
        buttons.addButton(strings.BUTTON_CANCEL, QDialogButtonBox.ButtonRole.RejectRole)
        self.save_button.clicked.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(self.form)
        layout.addWidget(self.error_label)
        layout.addWidget(buttons)

        if session is not None:
            self._load(session)
        for edit in (self.name_edit, self.host_edit, self.username_edit, self.key_path_edit):
            edit.textChanged.connect(self._validate)
        self.port_spin.valueChanged.connect(self._validate)
        self.password_radio.toggled.connect(self._update_mode)
        self.browse_button.clicked.connect(self._browse)
        self._update_mode()

    # ----- form state -------------------------------------------------------------------

    @property
    def auth_type(self) -> AuthType:
        """Selected authentication method."""
        return AuthType.KEY if self.key_radio.isChecked() else AuthType.PASSWORD

    def _load(self, session: SessionConfig) -> None:
        self.name_edit.setText(session.name)
        self.host_edit.setText(session.host)
        self.port_spin.setValue(session.port)
        self.username_edit.setText(session.username)
        self.key_radio.setChecked(session.auth_type is AuthType.KEY)
        self.password_radio.setChecked(session.auth_type is AuthType.PASSWORD)
        self.key_path_edit.setText(session.key_path or "")
        self.remember_check.setChecked(session.remember_secret)
        if self._services.secret_store.has_secret(session.id):
            self._secret_edit(session.auth_type).setPlaceholderText(
                strings.SECRET_STORED_PLACEHOLDER
            )

    def _secret_edit(self, auth_type: AuthType) -> QLineEdit:
        return self.passphrase_edit if auth_type is AuthType.KEY else self.password_edit

    def _set_row_visible(self, field: QWidget, visible: bool) -> None:
        self.form.setRowVisible(field, visible)

    def _update_mode(self) -> None:
        key_mode = self.auth_type is AuthType.KEY
        self._set_row_visible(self.password_edit, not key_mode)
        self._set_row_visible(self._key_row_widget, key_mode)
        self._set_row_visible(self.passphrase_edit, key_mode)
        state = self._services.vault.state
        hint = {
            VaultState.UNINITIALIZED: strings.VAULT_HINT_CREATE,
            VaultState.LOCKED: strings.VAULT_HINT_UNLOCK,
        }.get(state, "")
        self.vault_hint.setText(hint)
        self.vault_hint.setVisible(bool(hint))
        self._validate()

    def _browse(self) -> None:
        ssh_dir = Path.home() / ".ssh"
        start = str(ssh_dir if ssh_dir.is_dir() else Path.home())
        path, _filter = QFileDialog.getOpenFileName(
            self, strings.BROWSE_TITLE, start, strings.BROWSE_FILTER
        )
        if path:
            self.key_path_edit.setText(path)

    # ----- validation -------------------------------------------------------------------

    def validation_error(self) -> str | None:
        """Message for the first invalid field, or ``None``."""
        name = self.name_edit.text().strip()
        if not name:
            return strings.ERR_NAME_REQUIRED
        if len(name) > NAME_MAX_LEN:
            return strings.ERR_NAME_TOO_LONG.format(max=NAME_MAX_LEN)
        if self._name_taken(name):
            return strings.ERR_NAME_DUPLICATE.format(name=name)
        host = normalize_host(self.host_edit.text())
        if not host:
            return strings.ERR_HOST_REQUIRED
        if any(ch.isspace() for ch in host) or "[" in host or "]" in host:
            return strings.ERR_HOST_INVALID
        username = self.username_edit.text().strip()
        if not username:
            return strings.ERR_USERNAME_REQUIRED
        if any(ch.isspace() for ch in username):
            return strings.ERR_USERNAME_SPACES
        if self.auth_type is AuthType.KEY:
            key_path = self.key_path_edit.text().strip()
            if not key_path:
                return strings.ERR_KEY_PATH_REQUIRED
            if not key_file_exists(key_path):
                return strings.ERR_KEY_FILE_MISSING
        return None

    def _name_taken(self, name: str) -> bool:
        key = name.casefold()
        own_id = self._original.id if self._original else None
        return any(
            s.name.casefold() == key and s.id != own_id for s in self._services.session_store.all()
        )

    def _validate(self) -> None:
        message = self.validation_error()
        self.save_button.setEnabled(message is None)
        self.error_label.setText(message or "")
        self.error_label.setVisible(message is not None)

    # ----- saving -----------------------------------------------------------------------

    def _build(self, remember: bool) -> SessionConfig:
        key_mode = self.auth_type is AuthType.KEY
        values = {
            "name": self.name_edit.text().strip(),
            "host": normalize_host(self.host_edit.text()),
            "port": self.port_spin.value(),
            "username": self.username_edit.text().strip(),
            "auth_type": self.auth_type,
            "key_path": self.key_path_edit.text().strip() if key_mode else None,
            "remember_secret": remember,
        }
        if self._original is None:
            return SessionConfig(**values, id=uuid.uuid4().hex, created_at=now_iso())
        return replace(self._original, **values)

    def _save(self) -> None:
        if self.validation_error() is not None:
            return
        store = self._services.session_store
        secrets = self._services.secret_store
        checked = self.remember_check.isChecked()
        secret = self._secret_edit(self.auth_type).text()
        method_changed = (
            self._original is not None and self._original.auth_type is not self.auth_type
        )
        # Saved first; the remember flag becomes 1 only once a secret is really stored,
        # or when the user wants to be asked at connect time (SPEC §9.5).
        session = self._build(remember=checked and not secret)
        try:
            if self._original is None:
                store.add(session)
            else:
                store.update(session)
        except (ValueError, KeyError) as exc:
            self.error_label.setText(str(exc))
            self.error_label.show()
            return
        if method_changed or not checked:
            secrets.delete_secret(session.id)
        if checked and secret:
            if ensure_vault_unlocked(self, self._services.vault):
                secrets.set_secret(session.id, secret)
            else:
                QMessageBox.information(
                    self, strings.SESSION_EDIT_TITLE, strings.SESSION_SAVED_WITHOUT_SECRET
                )
        self.password_edit.clear()
        self.passphrase_edit.clear()
        self.saved_session = store.get(session.id)
        self.accept()
