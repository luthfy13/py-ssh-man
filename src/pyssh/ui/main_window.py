"""Main application window (SPEC §9.1)."""

from __future__ import annotations

import platform
import time
from collections.abc import Callable
from dataclasses import replace
from importlib import resources

import PySide6
from PySide6.QtCore import QByteArray, QEvent, QKeyCombination, QObject, Qt, QUrl, qVersion
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDesktopServices,
    QIcon,
    QKeySequence,
    QMouseEvent,
    QPixmap,
)
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QWidget,
)

from pyssh import __version__, config, shortcuts, strings
from pyssh.core.vault import VaultState
from pyssh.models import AppSettings, SessionConfig
from pyssh.services import AppServices
from pyssh.terminal.demo_backend import DemoBackend
from pyssh.terminal.view import TerminalView
from pyssh.terminal.widget import TerminalWidget
from pyssh.ui import icons
from pyssh.ui.dialogs import confirm
from pyssh.ui.session_panel import SessionPanel
from pyssh.ui.settings_dialog import SettingsDialog
from pyssh.ui.terminal_tab import TabState, TerminalTab
from pyssh.ui.vault_dialogs import (
    ChangeMasterPasswordDialog,
    CreateMasterPasswordDialog,
    UnlockDialog,
    confirm_reset,
)

INITIAL_WIDTH = 1200
INITIAL_HEIGHT = 750
PANEL_WIDTH = 240
SHUTDOWN_JOIN_S = 1.5

STATE_ICON_COLOR = {
    TabState.IDLE: icons.GRAY,
    TabState.CONNECTING: icons.YELLOW,
    TabState.CONNECTED: icons.GREEN,
    TabState.DISCONNECTED: icons.RED,
    TabState.FAILED: icons.RED,
    TabState.CLOSED: icons.GRAY,
}

_VAULT_STATE_TEXT = {
    VaultState.UNINITIALIZED: strings.VAULT_STATE_UNINITIALIZED,
    VaultState.LOCKED: strings.VAULT_STATE_LOCKED,
    VaultState.UNLOCKED: strings.VAULT_STATE_UNLOCKED,
}


def app_icon() -> QIcon:
    """Application icon from ``resources/icon.png`` (empty icon if the file is missing)."""
    pixmap = QPixmap()
    try:
        data = resources.files("pyssh").joinpath("resources", "icon.png").read_bytes()
    except OSError:
        return QIcon()
    pixmap.loadFromData(data)
    return QIcon(pixmap)


def unique_title(name: str, existing: list[str]) -> str:
    """``name``, or ``name (2)``, ``name (3)``… when already used by an open tab."""
    if name not in existing:
        return name
    n = 2
    while f"{name} ({n})" in existing:
        n += 1
    return f"{name} ({n})"


def key_sequences(action: str, *, mac: bool = config.IS_MAC) -> list[QKeySequence]:
    """All ``QKeySequence`` objects for an action: table text first, then every key variant."""
    result: list[QKeySequence] = []
    for row in shortcuts.shortcut_rows(action, mac=mac):
        candidates = [QKeySequence(row.sequence)]
        candidates += [QKeySequence(QKeyCombination(row.mods, Qt.Key(key))) for key in row.keys]
        for sequence in candidates:
            if sequence not in result:
                result.append(sequence)
    return result


class MainWindow(QMainWindow):
    """Top-level window: menus, tabs and status bar."""

    def __init__(self, services: AppServices, parent: QWidget | None = None) -> None:
        """Create the window, its menus, tab area and status bar."""
        super().__init__(parent)
        self._services = services
        self.setWindowTitle(config.APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(INITIAL_WIDTH, INITIAL_HEIGHT)

        self.tabs = QTabWidget(self)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self.request_close_tab)
        self.tabs.currentChanged.connect(self._on_current_tab_changed)
        self.tabs.tabBar().installEventFilter(self)

        self.welcome = QLabel(
            strings.WELCOME.format(
                shortcut=key_sequences("new_session")[0].toString(
                    QKeySequence.SequenceFormat.NativeText
                )
            )
        )
        self.welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.welcome.setWordWrap(True)
        self.content = QStackedWidget()
        self.content.addWidget(self.welcome)
        self.content.addWidget(self.tabs)

        self.session_panel = SessionPanel(services)
        self.session_panel.open_requested.connect(self.open_session)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.session_panel)
        self.splitter.addWidget(self.content)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([PANEL_WIDTH, INITIAL_WIDTH - PANEL_WIDTH])
        self.setCentralWidget(self.splitter)

        self._build_menus()
        self.state_icon = QLabel()
        self.state_label = QLabel()
        self.statusBar().addWidget(self.state_icon)
        self.statusBar().addWidget(self.state_label, 1)
        self.vault_label = QLabel()
        self.grid_label = QLabel()
        self.statusBar().addPermanentWidget(self.vault_label)
        self.statusBar().addPermanentWidget(self.grid_label)
        services.vault.add_listener(lambda _state: self.refresh_vault_ui())
        self.refresh_vault_ui()
        self._restore_geometry()
        self._update_content()

    @property
    def services(self) -> AppServices:
        """The shared services passed at construction."""
        return self._services

    # ----- menus ------------------------------------------------------------------------

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu(strings.MENU_FILE)
        self.action_new_session = self._action(
            strings.ACTION_NEW_SESSION, self.new_session, "new_session"
        )
        file_menu.addAction(self.action_new_session)
        file_menu.addSeparator()
        self.action_vault_create = self._action(strings.ACTION_VAULT_CREATE, self._vault_create)
        self.action_vault_unlock = self._action(strings.ACTION_VAULT_UNLOCK, self._vault_unlock)
        self.action_vault_lock = self._action(strings.ACTION_VAULT_LOCK, self._vault_lock)
        self.action_vault_change = self._action(strings.ACTION_VAULT_CHANGE, self._vault_change)
        self.action_vault_reset = self._action(strings.ACTION_VAULT_RESET, self._vault_reset)
        for action in (
            self.action_vault_create,
            self.action_vault_unlock,
            self.action_vault_lock,
            self.action_vault_change,
            self.action_vault_reset,
        ):
            file_menu.addAction(action)
        file_menu.addSeparator()
        self.action_settings = self._action(strings.ACTION_SETTINGS, self.open_settings)
        self.action_settings.setMenuRole(QAction.MenuRole.PreferencesRole)
        file_menu.addAction(self.action_settings)
        file_menu.addSeparator()
        self.action_quit = self._action(strings.ACTION_QUIT, self.close)
        self.action_quit.setMenuRole(QAction.MenuRole.QuitRole)
        file_menu.addAction(self.action_quit)

        session_menu = self.menuBar().addMenu(strings.MENU_SESSION)
        self.action_reconnect = self._action(
            strings.ACTION_RECONNECT, self.reconnect_current, "reconnect"
        )
        session_menu.addAction(self.action_reconnect)
        self.action_close_tab = self._action(
            strings.ACTION_CLOSE_TAB, self.close_current_tab, "close_tab"
        )
        self.action_next_tab = self._action(strings.ACTION_NEXT_TAB, self.next_tab, "next_tab")
        self.action_prev_tab = self._action(strings.ACTION_PREV_TAB, self.prev_tab, "prev_tab")
        for action in (self.action_close_tab, self.action_next_tab, self.action_prev_tab):
            session_menu.addAction(action)

        view_menu = self.menuBar().addMenu(strings.MENU_VIEW)
        self.action_zoom_in = self._action(
            strings.ACTION_ZOOM_IN, lambda: self._with_terminal(TerminalWidget.zoom_in), "zoom_in"
        )
        self.action_zoom_out = self._action(
            strings.ACTION_ZOOM_OUT,
            lambda: self._with_terminal(TerminalWidget.zoom_out),
            "zoom_out",
        )
        self.action_zoom_reset = self._action(
            strings.ACTION_ZOOM_RESET,
            lambda: self._with_terminal(TerminalWidget.zoom_reset),
            "zoom_reset",
        )
        for action in (self.action_zoom_in, self.action_zoom_out, self.action_zoom_reset):
            view_menu.addAction(action)
        self.action_toggle_panel = self._action(
            strings.ACTION_TOGGLE_PANEL, self.toggle_session_panel, "toggle_panel"
        )
        self.action_toggle_panel.setCheckable(True)
        self.action_toggle_panel.setChecked(True)
        view_menu.addSeparator()
        view_menu.addAction(self.action_toggle_panel)

        help_menu = self.menuBar().addMenu(strings.MENU_HELP)
        self.action_open_data = self._action(strings.ACTION_OPEN_DATA_FOLDER, self.open_data_folder)
        self.action_open_log = self._action(strings.ACTION_OPEN_LOG, self.open_log_file)
        self.action_about = self._action(
            strings.ACTION_ABOUT.format(app=config.APP_NAME), self.show_about
        )
        self.action_about.setMenuRole(QAction.MenuRole.AboutRole)
        for action in (self.action_open_data, self.action_open_log, self.action_about):
            help_menu.addAction(action)

    def open_data_folder(self) -> bool:
        """Open the data folder in the system file manager."""
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._services.paths.root)))

    def open_log_file(self) -> bool:
        """Open the log file with the system's default application."""
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._services.paths.log_file)))

    def about_text(self) -> str:
        """Text of the About box: versions and library licenses."""
        return strings.ABOUT_TEXT.format(
            app=config.APP_NAME,
            version=__version__,
            python=platform.python_version(),
            qt=qVersion(),
            pyside=PySide6.__version__,
        )

    def show_about(self) -> None:
        """Help → About."""
        QMessageBox.about(self, strings.ABOUT_TITLE.format(app=config.APP_NAME), self.about_text())

    def open_settings(self) -> None:
        """Show the settings dialog and apply the result to every open terminal."""
        dialog = SettingsDialog(self._services.settings_store, self)
        if dialog.exec() and dialog.saved_settings is not None:
            self.apply_settings(dialog.saved_settings)

    def apply_settings(self, settings: AppSettings) -> None:
        """Font and colors apply immediately; scrollback only affects new tabs (SPEC §9.10)."""
        for i in range(self.tabs.count()):
            terminal = getattr(self.tabs.widget(i), "terminal", None)
            if isinstance(terminal, TerminalWidget):
                terminal.apply_settings(settings)

    def new_session(self) -> None:
        """Create a session (Berkas → Sesi Baru…)."""
        self.session_panel.new_session()

    def toggle_session_panel(self) -> None:
        """Show or hide the session panel."""
        visible = not self.session_panel.isVisible()
        self.session_panel.setVisible(visible)
        self.action_toggle_panel.setChecked(visible)

    def _action(
        self, text: str, slot: Callable[[], object], shortcut_action: str | None = None
    ) -> QAction:
        action = QAction(text, self)
        action.triggered.connect(lambda _checked=False: slot())
        if shortcut_action is not None:
            action.setShortcuts(key_sequences(shortcut_action))
            action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        self.addAction(action)
        return action

    # ----- vault ------------------------------------------------------------------------

    def refresh_vault_ui(self) -> None:
        """Update vault menu items and the status bar to the current vault state."""
        state = self._services.vault.state
        initialized = state is not VaultState.UNINITIALIZED
        self.action_vault_create.setVisible(state is VaultState.UNINITIALIZED)
        self.action_vault_unlock.setVisible(state is VaultState.LOCKED)
        self.action_vault_lock.setVisible(state is VaultState.UNLOCKED)
        self.action_vault_change.setVisible(initialized)
        self.action_vault_reset.setVisible(initialized)
        self.vault_label.setText(strings.VAULT_STATUS.format(state=_VAULT_STATE_TEXT[state]))

    def _vault_create(self) -> None:
        CreateMasterPasswordDialog(self._services.vault, self).exec()

    def _vault_unlock(self) -> None:
        UnlockDialog(self._services.vault, self).exec()

    def _vault_lock(self) -> None:
        self._services.vault.lock()

    def _vault_change(self) -> None:
        ChangeMasterPasswordDialog(self._services.vault, self).exec()

    def _vault_reset(self) -> None:
        if confirm_reset(self):
            self._services.vault.reset()

    # ----- tabs -------------------------------------------------------------------------

    def open_demo_tab(self) -> TerminalView:
        """Open a local demo tab with the key inspector (SPEC §8.6)."""
        view = TerminalView(self._services.settings_store.current)
        backend = DemoBackend(view.terminal)
        self._add_terminal_tab(view, strings.DEMO_TAB_TITLE)
        backend.start()
        return view

    def open_session(self, session: SessionConfig) -> TerminalTab:
        """Open a saved session in a new tab and start connecting."""
        return self._open_terminal_tab(session, adhoc=False)

    def open_adhoc(self, user: str, host: str, port: int = 22) -> TerminalTab:
        """Open an unsaved ``user@host:port`` session (``--connect``)."""
        session = SessionConfig(name=f"{user}@{host}", host=host, username=user, port=port)
        return self._open_terminal_tab(session, adhoc=True)

    def active_tab(self) -> TerminalTab | None:
        """The current tab when it is an SSH tab."""
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, TerminalTab) else None

    def reconnect_current(self) -> None:
        """Reconnect the active SSH tab."""
        tab = self.active_tab()
        if tab is not None:
            tab.reconnect()

    def terminal_tabs(self) -> list[TerminalTab]:
        """All open SSH tabs."""
        return [
            widget
            for i in range(self.tabs.count())
            if isinstance(widget := self.tabs.widget(i), TerminalTab)
        ]

    def _open_terminal_tab(self, session: SessionConfig, *, adhoc: bool) -> TerminalTab:
        tab = TerminalTab(session, self._services, adhoc=adhoc)
        tab.state_changed.connect(lambda _state, t=tab: self._on_tab_state(t))
        tab.close_requested.connect(lambda t=tab: self.request_close_tab(self.tabs.indexOf(t)))
        tab.info_message.connect(lambda text: self.statusBar().showMessage(text, 10000))
        titles = [self.tabs.tabText(i) for i in range(self.tabs.count())]
        index = self._add_terminal_tab(tab, unique_title(session.name, titles))
        self.tabs.setTabToolTip(index, session.target())
        tab.title_changed.connect(lambda title, t=tab: self._on_tab_title(t, title))
        self._on_tab_state(tab)
        tab.connect_session()
        return tab

    def _on_tab_title(self, tab: TerminalTab, title: str) -> None:
        """Show the remote window title (OSC 0/2) in the tab tooltip."""
        index = self.tabs.indexOf(tab)
        if index >= 0:
            target = tab.session.target()
            self.tabs.setTabToolTip(index, f"{target}\n{title}" if title else target)

    def _on_tab_state(self, tab: TerminalTab) -> None:
        index = self.tabs.indexOf(tab)
        if index >= 0:
            self.tabs.setTabIcon(index, icons.dot_icon(STATE_ICON_COLOR[tab.state]))
        if tab is self.active_tab():
            self._show_tab_status(tab)

    def _show_tab_status(self, tab: TerminalTab | None) -> None:
        if tab is None:
            self.state_icon.clear()
            self.state_label.clear()
            return
        self.state_icon.setPixmap(icons.dot_icon(STATE_ICON_COLOR[tab.state]).pixmap(12, 12))
        self.state_label.setText(tab.status_text())

    def _add_terminal_tab(self, view: QWidget, title: str) -> int:
        terminal = getattr(view, "terminal", None)
        if isinstance(terminal, TerminalWidget):
            terminal.grid_size_changed.connect(
                lambda cols, rows, t=terminal: self._on_grid_size(t, cols, rows)
            )
        index = self.tabs.addTab(view, title)
        self.tabs.setCurrentIndex(index)
        self._update_content()
        view.setFocus()
        return index

    def active_terminal(self) -> TerminalWidget | None:
        """Terminal widget of the current tab, if any."""
        terminal = getattr(self.tabs.currentWidget(), "terminal", None)
        return terminal if isinstance(terminal, TerminalWidget) else None

    def _with_terminal(self, method: Callable[[TerminalWidget], object]) -> None:
        terminal = self.active_terminal()
        if terminal is not None:
            method(terminal)

    def request_close_tab(self, index: int) -> None:
        """Close a tab, asking first when its session is connected (SPEC §9.7, §9.9)."""
        widget = self.tabs.widget(index)
        if widget is None:
            return
        needs_confirm = (
            isinstance(widget, TerminalTab)
            and widget.state is TabState.CONNECTED
            and self._services.settings_store.current.confirm_on_close
        )
        if needs_confirm and not confirm(self, strings.CLOSE_TAB_TITLE, strings.CLOSE_TAB_CONFIRM):
            return
        self.close_tab(index)

    def close_tab(self, index: int) -> None:
        """Close the tab at ``index`` without asking; the worker is stopped, not awaited."""
        widget = self.tabs.widget(index)
        if widget is None:
            return
        if isinstance(widget, TerminalTab):
            widget.close_session()
        self.tabs.removeTab(index)
        widget.deleteLater()
        self._update_content()

    def close_current_tab(self) -> None:
        """Close the active tab (with confirmation when connected)."""
        if self.tabs.count():
            self.request_close_tab(self.tabs.currentIndex())

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Middle click on a tab closes it."""
        if (
            watched is self.tabs.tabBar()
            and event.type() == QEvent.Type.MouseButtonRelease
            and isinstance(event, QMouseEvent)
            and event.button() == Qt.MouseButton.MiddleButton
        ):
            index = self.tabs.tabBar().tabAt(event.position().toPoint())
            if index >= 0:
                self.request_close_tab(index)
                return True
        return super().eventFilter(watched, event)

    def next_tab(self) -> None:
        """Activate the next tab (wraps around)."""
        count = self.tabs.count()
        if count:
            self.tabs.setCurrentIndex((self.tabs.currentIndex() + 1) % count)

    def prev_tab(self) -> None:
        """Activate the previous tab (wraps around)."""
        count = self.tabs.count()
        if count:
            self.tabs.setCurrentIndex((self.tabs.currentIndex() - 1) % count)

    def _on_current_tab_changed(self, _index: int) -> None:
        widget = self.tabs.currentWidget()
        if widget is not None:
            widget.setFocus()
        terminal = self.active_terminal()
        if terminal is None:
            self.grid_label.clear()
        else:
            self._show_grid(*terminal.grid_size())
        self._show_tab_status(self.active_tab())

    def _on_grid_size(self, terminal: TerminalWidget, cols: int, rows: int) -> None:
        if terminal is self.active_terminal():
            self._show_grid(cols, rows)

    def _show_grid(self, cols: int, rows: int) -> None:
        self.grid_label.setText(strings.GRID_SIZE.format(cols=cols, rows=rows))

    def _update_content(self) -> None:
        self.content.setCurrentWidget(self.tabs if self.tabs.count() else self.welcome)

    # ----- window state -----------------------------------------------------------------

    def _restore_geometry(self) -> None:
        settings = self._services.settings_store.current
        if settings.window_geometry:
            self.restoreGeometry(QByteArray.fromBase64(settings.window_geometry.encode("ascii")))
        if settings.window_state:
            self.restoreState(QByteArray.fromBase64(settings.window_state.encode("ascii")))
        if settings.splitter_state:
            self.splitter.restoreState(
                QByteArray.fromBase64(settings.splitter_state.encode("ascii"))
            )

    def save_window_state(self) -> None:
        """Store geometry, window state and splitter position in ``settings.json``."""
        store = self._services.settings_store

        def encode(data: QByteArray) -> str:
            return bytes(data.toBase64()).decode("ascii")

        store.save(
            replace(
                store.current,
                window_geometry=encode(self.saveGeometry()),
                window_state=encode(self.saveState()),
                splitter_state=encode(self.splitter.saveState()),
            )
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        """Confirm, save the window state, stop every session, lock the vault (SPEC §9.9)."""
        tabs = self.terminal_tabs()
        active = sum(1 for tab in tabs if tab.state is TabState.CONNECTED)
        if (
            active
            and self._services.settings_store.current.confirm_on_close
            and not confirm(
                self, strings.QUIT_TITLE, strings.QUIT_CONFIRM.format(n=active, app=config.APP_NAME)
            )
        ):
            event.ignore()
            return
        self.save_window_state()
        for tab in tabs:
            tab.close_session()
        deadline = time.monotonic() + SHUTDOWN_JOIN_S
        for tab in tabs:
            tab.join_workers(max(0.0, deadline - time.monotonic()))
        self._services.vault.lock()
        self._services.database.close()
        event.accept()
