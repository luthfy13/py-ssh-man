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
def confirms(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Answer every confirmation with Yes (modal boxes would block) and record the texts."""
    asked: list[str] = []

    def fake_confirm(parent, title: str, text: str) -> bool:
        asked.append(text)
        return True

    monkeypatch.setattr(main_window_module, "confirm", fake_confirm)
    return asked


@pytest.fixture
def window(qtbot, services, confirms) -> MainWindow:
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


@pytest.fixture
def fake_workers(services):
    from fakes import WorkerFactory

    services.worker_factory = WorkerFactory()
    return services.worker_factory


@pytest.fixture
def password_answer(monkeypatch: pytest.MonkeyPatch):
    from pyssh.ui.dialogs import PasswordDialog

    monkeypatch.setattr(PasswordDialog, "ask", lambda self: ("pw", False))


def test_open_adhoc_tab(window: MainWindow, fake_workers, password_answer, qtbot) -> None:
    from pyssh.ui.terminal_tab import TabState

    window.show()
    tab = window.open_adhoc("admin", "10.0.0.5", 2222)
    assert window.tabs.tabText(0) == "admin@10.0.0.5"
    assert window.active_tab() is tab
    assert tab.adhoc
    assert window.state_label.text() == "Menghubungkan… — admin@10.0.0.5:2222"
    fake_workers.last.connected.emit()
    assert tab.state is TabState.CONNECTED
    assert window.state_label.text() == "Terhubung — admin@10.0.0.5:2222"


def test_open_session_and_reconnect(
    window: MainWindow, services, fake_workers, password_answer, qtbot
) -> None:
    from pyssh.models import SessionConfig
    from pyssh.ui.terminal_tab import TabState

    window.show()
    session = SessionConfig(name="Web", host="h", username="u")
    services.session_store.add(session)
    tab = window.open_session(session)
    assert window.tabs.tabText(0) == "Web"
    assert not tab.adhoc
    fake_workers.last.failed.emit("E_CONNECT", "gagal")
    assert tab.state is TabState.FAILED
    window.action_reconnect.trigger()
    assert len(fake_workers.workers) == 2
    assert tab.state is TabState.CONNECTING


def test_close_tab_stops_session(window: MainWindow, fake_workers, password_answer) -> None:
    from pyssh.ui.terminal_tab import TabState

    tab = window.open_adhoc("u", "h")
    worker = fake_workers.last
    window.close_tab(0)
    assert worker.stopped
    assert tab.state is TabState.CLOSED
    assert window.tabs.count() == 0
    window.reconnect_current()  # no tab: no error


def test_banner_close_and_info_message(
    window: MainWindow, fake_workers, password_answer, monkeypatch
) -> None:
    from pyssh.ui import terminal_tab as tab_module

    monkeypatch.setattr(tab_module, "ensure_vault_unlocked", lambda parent, vault: False)
    from pyssh.ui.dialogs import PasswordDialog

    monkeypatch.setattr(PasswordDialog, "ask", lambda self: ("pw", True))
    from pyssh.models import SessionConfig

    session = SessionConfig(name="S", host="h", username="u")
    window.services.session_store.add(session)
    tab = window.open_session(session)
    fake_workers.last.connected.emit()
    assert window.statusBar().currentMessage() == strings.SECRET_NOT_SAVED_VAULT
    tab.close_requested.emit()
    assert window.tabs.count() == 0


def test_welcome_page_and_tabs(window: MainWindow, fake_workers, password_answer) -> None:
    assert window.content.currentWidget() is window.welcome
    assert "Ctrl+Shift+N" in window.welcome.text()
    window.open_adhoc("u", "h")
    assert window.content.currentWidget() is window.tabs
    window.close_tab(0)
    assert window.content.currentWidget() is window.welcome


def test_panel_open_request_opens_tab(
    window: MainWindow, services, fake_workers, password_answer
) -> None:
    from pyssh.models import SessionConfig

    session = SessionConfig(name="Web", host="h", username="u")
    services.session_store.add(session)
    window.session_panel.refresh()
    window.session_panel.select(session.id)
    window.session_panel.open_selected()
    assert window.tabs.tabText(0) == "Web"
    assert window.active_tab().session.id == session.id


def test_new_session_action_and_panel_toggle(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch, qtbot
) -> None:
    window.show()
    qtbot.waitExposed(window)
    calls: list[bool] = []
    monkeypatch.setattr(window.session_panel, "new_session", lambda: calls.append(True))
    window.action_new_session.trigger()
    assert calls == [True]
    assert window.session_panel.isVisible()
    window.action_toggle_panel.trigger()
    assert not window.session_panel.isVisible()
    assert not window.action_toggle_panel.isChecked()
    window.action_toggle_panel.trigger()
    assert window.session_panel.isVisible()


def test_geometry_saved_and_restored(services, qtbot, confirms) -> None:
    first = MainWindow(services)
    qtbot.addWidget(first)
    first.resize(700, 500)  # must fit the offscreen screen (800x800); Qt clamps otherwise
    first.show()
    qtbot.waitExposed(first)
    first.splitter.setSizes([300, 400])
    first.close()
    services.database.open()  # closeEvent closed it (SPEC §9.9)
    saved = services.settings_store.current
    assert saved.window_geometry and saved.window_state and saved.splitter_state
    reloaded = services.settings_store.load()
    assert reloaded.window_geometry == saved.window_geometry
    second = MainWindow(services)
    qtbot.addWidget(second)
    second.show()
    qtbot.waitExposed(second)
    assert second.size() == first.size()
    assert second.splitter.sizes()[0] == first.splitter.sizes()[0]


def test_unique_title() -> None:
    from pyssh.ui.main_window import unique_title

    assert unique_title("Web", []) == "Web"
    assert unique_title("Web", ["Web"]) == "Web (2)"
    assert unique_title("Web", ["Web", "Web (2)"]) == "Web (3)"
    assert unique_title("Web", ["Web (2)"]) == "Web"


def test_three_tabs_unique_titles_and_icons(
    window: MainWindow, services, fake_workers, password_answer
) -> None:
    from pyssh.models import SessionConfig
    from pyssh.ui import icons

    session = SessionConfig(name="Web", host="h", username="u", port=2200)
    services.session_store.add(session)
    for _ in range(3):
        window.open_session(session)
    titles = [window.tabs.tabText(i) for i in range(3)]
    assert titles == ["Web", "Web (2)", "Web (3)"]
    assert window.tabs.tabToolTip(1) == "u@h:2200"
    yellow = icons.dot_icon(icons.YELLOW).cacheKey()
    assert window.tabs.tabIcon(0).cacheKey() == yellow
    fake_workers.workers[0].connected.emit()
    assert window.tabs.tabIcon(0).cacheKey() == icons.dot_icon(icons.GREEN).cacheKey()
    fake_workers.workers[0].disconnected.emit("x")
    assert window.tabs.tabIcon(0).cacheKey() == icons.dot_icon(icons.RED).cacheKey()
    assert len(window.terminal_tabs()) == 3


def test_status_bar_follows_active_tab(window: MainWindow, fake_workers, password_answer) -> None:
    window.open_adhoc("a", "h1")
    window.open_adhoc("b", "h2")
    fake_workers.workers[0].connected.emit()
    assert window.state_label.text() == "Menghubungkan… — b@h2:22"
    window.tabs.setCurrentIndex(0)
    assert window.state_label.text() == "Terhubung — a@h1:22"
    assert window.state_icon.pixmap() is not None


def test_close_connected_tab_asks(
    window: MainWindow, services, fake_workers, password_answer, confirms, monkeypatch
) -> None:
    window.open_adhoc("u", "h")
    window.request_close_tab(5)  # unknown index: ignored
    fake_workers.last.connected.emit()
    monkeypatch.setattr(main_window_module, "confirm", lambda *a: confirms.append(a[2]) or False)
    window.action_close_tab.trigger()  # declined
    assert window.tabs.count() == 1
    assert confirms == [strings.CLOSE_TAB_CONFIRM]
    monkeypatch.setattr(main_window_module, "confirm", lambda *a: confirms.append(a[2]) or True)
    window.tabs.tabCloseRequested.emit(0)  # the tab's × button
    assert window.tabs.count() == 0
    assert fake_workers.last.stopped


def test_close_without_confirmation_when_disabled(
    window: MainWindow, services, fake_workers, password_answer, confirms
) -> None:
    from dataclasses import replace

    services.settings_store.save(replace(services.settings_store.current, confirm_on_close=False))
    window.open_adhoc("u", "h")
    fake_workers.last.connected.emit()
    window.close_current_tab()
    assert confirms == []
    assert window.tabs.count() == 0


def test_disconnected_tab_closes_without_question(
    window: MainWindow, fake_workers, password_answer, confirms
) -> None:
    window.open_adhoc("u", "h")
    fake_workers.last.failed.emit("E_CONNECT", "x")
    window.close_current_tab()
    assert confirms == []


def test_middle_click_closes_tab(window: MainWindow, fake_workers, password_answer, qtbot) -> None:
    window.show()
    qtbot.waitExposed(window)
    window.open_adhoc("u", "h")
    window.open_adhoc("v", "h")
    bar = window.tabs.tabBar()
    qtbot.mouseClick(bar, Qt.MouseButton.MiddleButton, pos=bar.tabRect(0).center())
    assert [window.tabs.tabText(i) for i in range(window.tabs.count())] == ["v@h"]
    qtbot.mouseClick(bar, Qt.MouseButton.LeftButton, pos=bar.tabRect(0).center())
    assert window.tabs.count() == 1


def test_close_app_declined_keeps_running(
    window: MainWindow, fake_workers, password_answer, confirms, monkeypatch, qtbot
) -> None:
    window.show()
    window.open_adhoc("u", "h")
    window.open_adhoc("v", "h")
    for worker in fake_workers.workers:
        worker.connected.emit()
    monkeypatch.setattr(main_window_module, "confirm", lambda *a: confirms.append(a[2]) or False)
    window.close()
    assert window.isVisible()
    assert confirms == ["Ada 2 sesi aktif. Keluar dari PySSH?"]
    assert not any(w.stopped for w in fake_workers.workers)


def test_close_app_stops_workers_and_locks_vault(
    window: MainWindow, services, fake_workers, password_answer, confirms, qtbot
) -> None:
    from pyssh.core.vault import VaultState

    services.vault.initialize("master-pass-1")
    window.show()
    for name in ("a", "b", "c"):
        window.open_adhoc(name, "h")
    for worker in fake_workers.workers[:2]:
        worker.connected.emit()
    window.close()
    assert not window.isVisible()
    assert confirms == ["Ada 2 sesi aktif. Keluar dari PySSH?"]
    assert all(w.stopped and w.signalsBlocked() for w in fake_workers.workers)
    assert services.vault.state is VaultState.LOCKED
    with pytest.raises(RuntimeError):
        _ = services.database.conn  # closed
    services.database.open()  # for fixture teardown
