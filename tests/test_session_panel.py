"""Tests for ui.session_panel (SPEC §9.4)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from pyssh import strings
from pyssh.models import SessionConfig
from pyssh.ui import session_panel as panel_module
from pyssh.ui.session_dialog import SessionDialog
from pyssh.ui.session_panel import SessionPanel, matches


@pytest.fixture
def panel(qtbot, services) -> SessionPanel:
    widget = SessionPanel(services)
    qtbot.addWidget(widget)
    return widget


def _add(services, name: str, host: str = "h", user: str = "u", port: int = 22):
    session = SessionConfig(name=name, host=host, username=user, port=port)
    services.session_store.add(session)
    return session


def test_matches() -> None:
    s = SessionConfig(name="Web Server", host="10.0.0.5", username="admin")
    assert matches(s, "")
    assert matches(s, "web")
    assert matches(s, "0.0.5")
    assert matches(s, "ADM")
    assert not matches(s, "db")


def test_empty_state(panel: SessionPanel) -> None:
    assert panel.stack.currentWidget() is panel.empty_label
    assert panel.empty_label.text() == strings.PANEL_EMPTY
    assert not panel.edit_button.isEnabled()
    assert not panel.delete_button.isEnabled()


def test_order_and_two_line_items(panel: SessionPanel, services) -> None:
    _add(services, "charlie")
    _add(services, "Bravo", host="db.local", user="root", port=2200)
    _add(services, "alpha")
    panel.refresh()
    assert panel.visible_names() == ["alpha", "Bravo", "charlie"]
    assert panel.list.item(1).text() == "Bravo\nroot@db.local:2200"
    assert panel.list.item(1).toolTip() == "root@db.local:2200"
    assert panel.stack.currentWidget() is panel.list


def test_filter(panel: SessionPanel, services) -> None:
    _add(services, "Web", host="10.0.0.5", user="admin")
    _add(services, "DB", host="db.local", user="root")
    panel.refresh()
    panel.filter_edit.setText("root")
    assert panel.visible_names() == ["DB"]
    panel.filter_edit.setText("10.0")
    assert panel.visible_names() == ["Web"]
    panel.filter_edit.setText("WE")
    assert panel.visible_names() == ["Web"]
    panel.filter_edit.setText("")
    assert panel.visible_names() == ["DB", "Web"]


def test_buttons_follow_selection(panel: SessionPanel, services) -> None:
    session = _add(services, "Web")
    panel.refresh()
    panel.select(session.id)
    assert panel.edit_button.isEnabled() and panel.delete_button.isEnabled()
    assert panel.selected_session() == session


def test_open_by_double_click_and_enter(panel: SessionPanel, services, qtbot) -> None:
    session = _add(services, "Web")
    panel.refresh()
    opened: list[SessionConfig] = []
    panel.open_requested.connect(opened.append)
    panel.select(session.id)
    panel.list.itemDoubleClicked.emit(panel.list.currentItem())
    qtbot.keyClick(panel.list, Qt.Key.Key_Return)
    assert [s.id for s in opened] == [session.id, session.id]


def test_delete_removes_secret(panel: SessionPanel, services, monkeypatch, qtbot) -> None:
    services.vault.initialize("master-pass-1")
    session = _add(services, "Web")
    services.secret_store.set_secret(session.id, "pw")
    panel.refresh()
    panel.select(session.id)
    monkeypatch.setattr(panel_module, "confirm", lambda *a: False)
    qtbot.keyClick(panel.list, Qt.Key.Key_Delete)
    assert services.session_store.get(session.id) is not None
    monkeypatch.setattr(panel_module, "confirm", lambda *a: True)
    changed: list[bool] = []
    panel.sessions_changed.connect(lambda: changed.append(True))
    panel.delete_button.click()
    assert services.session_store.all() == []
    assert services.secret_store.has_secret(session.id) is False
    assert changed == [True]
    assert panel.stack.currentWidget() is panel.empty_label


def test_backspace_deletes_only_on_mac(qtbot) -> None:
    default_list = panel_module._SessionList(mac=False)
    qtbot.addWidget(default_list)
    ignored: list[bool] = []
    default_list.remove.connect(lambda: ignored.append(True))
    qtbot.keyClick(default_list, Qt.Key.Key_Backspace)
    assert ignored == []
    mac_list = panel_module._SessionList(mac=True)
    qtbot.addWidget(mac_list)
    removed: list[bool] = []
    mac_list.remove.connect(lambda: removed.append(True))
    qtbot.keyClick(mac_list, Qt.Key.Key_Backspace)
    assert removed == [True]


def test_duplicate(panel: SessionPanel, services) -> None:
    session = _add(services, "Web")
    panel.refresh()
    panel.select(session.id)
    panel.duplicate_selected()
    assert panel.visible_names() == ["Web", "Web (salinan)"]
    assert panel.selected_session().name == "Web (salinan)"


def test_new_and_edit_open_dialog(panel: SessionPanel, services, monkeypatch, qtbot) -> None:
    calls: list[str | None] = []

    def fake_exec(dialog: SessionDialog) -> int:
        calls.append(dialog._original.name if dialog._original else None)
        dialog.name_edit.setText("Created" if dialog._original is None else "Renamed")
        dialog.host_edit.setText("h")
        dialog.username_edit.setText("u")
        dialog.save_button.click()
        return 1

    monkeypatch.setattr(SessionDialog, "exec", fake_exec)
    panel.new_button.click()
    assert panel.visible_names() == ["Created"]
    qtbot.keyClick(panel.list, Qt.Key.Key_F2)
    assert calls == [None, "Created"]
    assert panel.visible_names() == ["Renamed"]


def test_context_menu_items(panel: SessionPanel) -> None:
    texts = [a.text() for a in panel.context_menu().actions() if not a.isSeparator()]
    assert texts == [
        strings.MENU_OPEN,
        strings.MENU_EDIT,
        strings.MENU_DUPLICATE,
        strings.MENU_DELETE,
        strings.MENU_FORGET_HOST_KEY,
    ]


def test_forget_host_key(panel: SessionPanel, services, monkeypatch) -> None:
    import io

    import paramiko
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519

    session = _add(services, "Web", host="srv", port=2222)
    pem = ed25519.Ed25519PrivateKey.generate().private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.OpenSSH,
        serialization.NoEncryption(),
    )
    key = paramiko.Ed25519Key.from_private_key(io.StringIO(pem.decode()))
    host_keys = paramiko.HostKeys()
    host_keys.add("[srv]:2222", key.get_name(), key)
    host_keys.save(str(services.paths.known_hosts_file))
    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a: shown.append(a[2]))
    panel.refresh()
    panel.select(session.id)
    forget = [a for a in panel.context_menu().actions() if a.text() == strings.MENU_FORGET_HOST_KEY]
    forget[0].trigger()
    assert shown == [strings.FORGET_DONE.format(target="srv:2222")]
    assert paramiko.HostKeys(str(services.paths.known_hosts_file)).lookup("[srv]:2222") is None
    panel.forget_host_key()
    assert shown[-1] == strings.FORGET_NONE.format(target="srv:2222")


def test_actions_without_selection_do_nothing(panel: SessionPanel) -> None:
    panel.open_selected()
    panel.edit_selected()
    panel.duplicate_selected()
    panel.delete_selected()
    panel.forget_host_key()
