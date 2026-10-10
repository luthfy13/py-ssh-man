"""With English selected, the windows and dialogs show no Indonesian text."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QTabWidget,
    QWidget,
)

from pyssh import i18n
from pyssh.models import AuthType, SessionConfig
from pyssh.ui import main_window as main_window_module
from pyssh.ui.dialogs import HostKeyDialog, PasswordDialog
from pyssh.ui.main_window import MainWindow
from pyssh.ui.session_dialog import SessionDialog
from pyssh.ui.settings_dialog import SettingsDialog
from pyssh.ui.vault_dialogs import (
    ChangeMasterPasswordDialog,
    CreateMasterPasswordDialog,
    UnlockDialog,
)
from test_i18n import EN, ID, INDONESIAN_WORDS

INDONESIAN_ONLY = {value for name, value in ID.items() if EN[name] != value}
ALLOWED = {i18n.language_name("id")}  # the language list names each language in itself


def _widget_texts(root: QWidget) -> list[str]:
    texts: list[str] = []
    for widget in (root, *root.findChildren(QWidget)):
        texts += [widget.windowTitle(), widget.toolTip()]
        texts += [action.text() for action in widget.actions()]
        if isinstance(widget, QLabel | QAbstractButton):
            texts.append(widget.text())
        if isinstance(widget, QLineEdit):
            texts.append(widget.placeholderText())
        if isinstance(widget, QComboBox):
            texts += [widget.itemText(i) for i in range(widget.count())]
        if isinstance(widget, QListWidget):
            texts += [widget.item(i).text() for i in range(widget.count())]
        if isinstance(widget, QMenu):
            texts.append(widget.title())
        if isinstance(widget, QTabWidget):
            for i in range(widget.count()):
                texts += [widget.tabText(i), widget.tabToolTip(i)]
    return [text for text in texts if text and text not in ALLOWED]


def _assert_english(texts: list[str]) -> None:
    assert texts  # something was collected
    assert sorted(t for t in texts if t in INDONESIAN_ONLY) == []
    assert sorted(t for t in texts if INDONESIAN_WORDS.search(t)) == []


@pytest.fixture
def english(qapp):
    i18n.set_language("en")


@pytest.fixture
def fake_workers(services):
    from fakes import WorkerFactory

    services.worker_factory = WorkerFactory()
    return services.worker_factory


def test_main_window_in_english(
    english, qtbot, services, fake_workers, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main_window_module, "confirm", lambda *_a: True)
    monkeypatch.setattr(PasswordDialog, "ask", lambda self: ("pw", False))
    session = SessionConfig(name="web", host="h", username="u")
    services.session_store.add(session)
    window = MainWindow(services)
    qtbot.addWidget(window)
    window.show()
    welcome = window.welcome.text()
    window.session_panel.list.setCurrentRow(0)
    texts = _widget_texts(window)
    texts += [a.text() for a in window.session_panel.context_menu().actions()]

    window.open_demo_tab()
    demo = window.tabs.currentWidget()
    terminal = demo.terminal
    texts += [a.text() for a in terminal.context_menu().actions()]
    texts += terminal.emulator.screen_lines_text()

    failed = window.open_session(session)
    fake_workers.last.failed.emit("E_CONNECT", EN["E_CONNECT"].format(host="h", port=22))
    connecting = window.open_adhoc("u", "h2")
    texts += [*_widget_texts(window), window.statusBar().currentMessage()]
    texts += failed.terminal.emulator.screen_lines_text()
    texts += connecting.terminal.emulator.screen_lines_text()
    texts += [failed.status_text(), connecting.status_text()]

    _assert_english(texts)
    assert {"&File", "&Session", "&View", "&Help", "Settings…"} <= set(texts)
    assert welcome.startswith("Double-click a session")
    assert "Failed — u@h:22" in texts
    assert window.vault_label.text() == "Vault: not created"
    assert failed.banner.reconnect_button.text() == "Reconnect"


def test_dialogs_in_english(english, qtbot, services, fast_kdf) -> None:
    session = SessionConfig(name="k", host="h", username="u", auth_type=AuthType.KEY)
    dialogs: list[QWidget] = [
        SettingsDialog(services.settings_store, mac=True),
        SessionDialog(services),
        SessionDialog(services, session),
        CreateMasterPasswordDialog(services.vault),
        PasswordDialog(title=EN["PASSWORD_TITLE"], prompt="p", error=EN["PASSWORD_RETRY"]),
        HostKeyDialog("h", 22, "ssh-ed25519", "SHA256:abc"),
    ]
    services.vault.initialize("master-pass-1")
    services.vault.lock()
    dialogs += [
        UnlockDialog(services.vault, startup=True),
        ChangeMasterPasswordDialog(services.vault),
    ]
    texts: list[str] = []
    for dialog in dialogs:
        qtbot.addWidget(dialog)
        texts += _widget_texts(dialog)
    _assert_english(texts)
    assert {"Settings", "New Session", "Edit Session", "Unlock Vault", "Skip"} <= set(texts)


def test_check_finds_indonesian_ui(qtbot, services) -> None:
    """The same collection in Indonesian is flagged, so the checks above are meaningful."""
    window = MainWindow(services)
    qtbot.addWidget(window)
    texts = _widget_texts(window)
    assert any(t in INDONESIAN_ONLY for t in texts)
    assert any(INDONESIAN_WORDS.search(t) for t in texts)
