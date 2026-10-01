"""Tests for ui.session_dialog (SPEC §6.6, §9.5)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox

from pyssh import strings
from pyssh.models import AuthType, SessionConfig
from pyssh.ui import session_dialog as dialog_module
from pyssh.ui.session_dialog import SessionDialog, normalize_host

MASTER = "master-pass-1"


@pytest.fixture
def dialog_factory(qtbot, services):
    def make(session: SessionConfig | None = None) -> SessionDialog:
        dialog = SessionDialog(services, session)
        qtbot.addWidget(dialog)
        return dialog

    return make


def _fill(dialog: SessionDialog, name="Web", host="10.0.0.5", user="admin", port=22) -> None:
    dialog.name_edit.setText(name)
    dialog.host_edit.setText(host)
    dialog.username_edit.setText(user)
    dialog.port_spin.setValue(port)


def test_normalize_host() -> None:
    assert normalize_host(" [::1] ") == "::1"
    assert normalize_host("example.org") == "example.org"


def test_save_disabled_until_valid(dialog_factory) -> None:
    dialog = dialog_factory()
    assert not dialog.save_button.isEnabled()
    assert dialog.error_label.text() == strings.ERR_NAME_REQUIRED
    dialog.name_edit.setText("Web")
    assert dialog.error_label.text() == strings.ERR_HOST_REQUIRED
    dialog.host_edit.setText("bad host")
    assert dialog.error_label.text() == strings.ERR_HOST_INVALID
    dialog.host_edit.setText("[fe80::1]")
    assert dialog.error_label.text() == strings.ERR_USERNAME_REQUIRED
    dialog.username_edit.setText("a b")
    assert dialog.error_label.text() == strings.ERR_USERNAME_SPACES
    dialog.username_edit.setText("admin")
    assert dialog.save_button.isEnabled()
    assert dialog.error_label.isHidden()


def test_port_range(dialog_factory) -> None:
    dialog = dialog_factory()
    assert (dialog.port_spin.minimum(), dialog.port_spin.maximum()) == (1, 65535)
    assert dialog.port_spin.value() == 22


def test_name_length_limited(dialog_factory) -> None:
    dialog = dialog_factory()
    assert dialog.name_edit.maxLength() == 64


def test_duplicate_name_rejected(dialog_factory, services) -> None:
    services.session_store.add(SessionConfig(name="Web", host="h", username="u"))
    dialog = dialog_factory()
    _fill(dialog, name="WEB")
    assert dialog.error_label.text() == strings.ERR_NAME_DUPLICATE.format(name="WEB")
    assert not dialog.save_button.isEnabled()


def test_edit_keeps_own_name(dialog_factory, services) -> None:
    session = SessionConfig(name="Web", host="h", username="u")
    services.session_store.add(session)
    dialog = dialog_factory(session)
    assert dialog.windowTitle() == strings.SESSION_EDIT_TITLE
    assert dialog.save_button.isEnabled()
    dialog.host_edit.setText("[::1]")
    dialog.save_button.click()
    saved = services.session_store.get(session.id)
    assert saved.host == "::1"
    assert saved.created_at == session.created_at


def test_key_mode_validation(dialog_factory, tmp_path: Path) -> None:
    dialog = dialog_factory()
    _fill(dialog)
    dialog.key_radio.setChecked(True)
    assert dialog.form.isRowVisible(dialog.passphrase_edit)
    assert not dialog.form.isRowVisible(dialog.password_edit)
    assert dialog.error_label.text() == strings.ERR_KEY_PATH_REQUIRED
    dialog.key_path_edit.setText(str(tmp_path / "missing"))
    assert dialog.error_label.text() == strings.ERR_KEY_FILE_MISSING
    key = tmp_path / "id_test"
    key.write_text("x")
    dialog.key_path_edit.setText(str(key))
    assert dialog.save_button.isEnabled()
    dialog.password_radio.setChecked(True)
    assert dialog.form.isRowVisible(dialog.password_edit)


def test_browse_sets_path(dialog_factory, monkeypatch) -> None:
    from PySide6.QtWidgets import QFileDialog

    seen = {}

    def fake(parent, title, start, filt):
        seen.update(title=title, start=start, filter=filt)
        return "/tmp/id_x", filt

    monkeypatch.setattr(QFileDialog, "getOpenFileName", fake)
    dialog = dialog_factory()
    dialog.browse_button.click()
    assert dialog.key_path_edit.text() == "/tmp/id_x"
    assert seen["filter"] == strings.BROWSE_FILTER


def test_new_session_without_secret(dialog_factory, services) -> None:
    dialog = dialog_factory()
    _fill(dialog, port=2222)
    dialog.save_button.click()
    saved = dialog.saved_session
    assert saved is not None
    expected = ("Web", "10.0.0.5", 2222, "admin")
    assert (saved.name, saved.host, saved.port, saved.username) == expected
    assert saved.remember_secret is False
    assert services.session_store.all() == [saved]


def test_secret_saved_immediately_when_vault_open(dialog_factory, services) -> None:
    services.vault.initialize(MASTER)
    dialog = dialog_factory()
    _fill(dialog)
    dialog.password_edit.setText("pw-from-dialog")
    dialog.remember_check.setChecked(True)
    dialog.save_button.click()
    sid = dialog.saved_session.id
    assert services.secret_store.get_secret(sid) == "pw-from-dialog"
    assert services.session_store.get(sid).remember_secret is True
    assert dialog.password_edit.text() == ""


def test_vault_refused_saves_without_secret(dialog_factory, services, monkeypatch) -> None:
    monkeypatch.setattr(dialog_module, "ensure_vault_unlocked", lambda parent, vault: False)
    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a: shown.append(a[2]))
    dialog = dialog_factory()
    _fill(dialog)
    dialog.password_edit.setText("pw")
    dialog.remember_check.setChecked(True)
    dialog.save_button.click()
    saved = dialog.saved_session
    assert saved.remember_secret is False
    assert services.secret_store.has_secret(saved.id) is False
    assert shown == [strings.SESSION_SAVED_WITHOUT_SECRET]


def test_vault_hint(dialog_factory, services) -> None:
    dialog = dialog_factory()
    assert dialog.vault_hint.text() == strings.VAULT_HINT_CREATE
    services.vault.initialize(MASTER)
    services.vault.lock()
    assert dialog_factory().vault_hint.text() == strings.VAULT_HINT_UNLOCK
    services.vault.unlock(MASTER)
    assert dialog_factory().vault_hint.isHidden()


def _stored_session(services, secret: str = "old-secret", **kwargs) -> SessionConfig:
    services.vault.initialize(MASTER)
    session = SessionConfig(name="Web", host="h", username="u", **kwargs)
    services.session_store.add(session)
    services.secret_store.set_secret(session.id, secret)
    return services.session_store.get(session.id)


def test_edit_with_stored_secret_shows_placeholder(dialog_factory, services) -> None:
    session = _stored_session(services)
    dialog = dialog_factory(session)
    assert dialog.password_edit.placeholderText() == strings.SECRET_STORED_PLACEHOLDER
    assert dialog.remember_check.isChecked()


def test_checked_and_empty_keeps_old_secret(dialog_factory, services) -> None:
    session = _stored_session(services)
    dialog = dialog_factory(session)
    dialog.host_edit.setText("new-host")
    dialog.save_button.click()
    assert services.secret_store.get_secret(session.id) == "old-secret"
    assert services.session_store.get(session.id).remember_secret is True


def test_checked_and_empty_without_secret_asks_later(dialog_factory, services) -> None:
    dialog = dialog_factory()
    _fill(dialog)
    dialog.remember_check.setChecked(True)
    dialog.save_button.click()
    saved = dialog.saved_session
    assert saved.remember_secret is True  # prompt at connect, save after success
    assert services.secret_store.has_secret(saved.id) is False


def test_unchecked_deletes_secret(dialog_factory, services) -> None:
    session = _stored_session(services)
    dialog = dialog_factory(session)
    dialog.remember_check.setChecked(False)
    dialog.save_button.click()
    assert services.secret_store.has_secret(session.id) is False
    assert services.session_store.get(session.id).remember_secret is False


def test_changing_method_deletes_old_secret(dialog_factory, services, tmp_path: Path) -> None:
    session = _stored_session(services)
    key = tmp_path / "id_x"
    key.write_text("x")
    dialog = dialog_factory(session)
    dialog.key_radio.setChecked(True)
    dialog.key_path_edit.setText(str(key))
    dialog.save_button.click()
    saved = services.session_store.get(session.id)
    assert saved.auth_type is AuthType.KEY
    assert saved.key_path == str(key)
    assert services.secret_store.has_secret(session.id) is False


def test_key_session_passphrase_saved(dialog_factory, services, tmp_path: Path) -> None:
    services.vault.initialize(MASTER)
    key = tmp_path / "id_x"
    key.write_text("x")
    dialog = dialog_factory()
    _fill(dialog)
    dialog.key_radio.setChecked(True)
    dialog.key_path_edit.setText(str(key))
    dialog.passphrase_edit.setText("phrase")
    dialog.password_edit.setText("ignored")
    dialog.remember_check.setChecked(True)
    dialog.save_button.click()
    assert services.secret_store.get_secret(dialog.saved_session.id) == "phrase"


def test_store_error_is_shown(dialog_factory, services, monkeypatch) -> None:
    dialog = dialog_factory()
    _fill(dialog)

    def boom(session):
        raise ValueError("Nama sesi sudah dipakai.")

    monkeypatch.setattr(services.session_store, "add", boom)
    dialog.save_button.click()
    assert dialog.saved_session is None
    assert dialog.error_label.text() == "Nama sesi sudah dipakai."
