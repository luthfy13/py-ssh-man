"""Main application window (SPEC §9.1)."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QKeyCombination, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QLabel, QMainWindow, QTabWidget, QWidget

from pyssh import config, shortcuts, strings
from pyssh.core.vault import VaultState
from pyssh.services import AppServices
from pyssh.terminal.demo_backend import DemoBackend
from pyssh.terminal.view import TerminalView
from pyssh.terminal.widget import TerminalWidget
from pyssh.ui.vault_dialogs import (
    ChangeMasterPasswordDialog,
    CreateMasterPasswordDialog,
    UnlockDialog,
    confirm_reset,
)

INITIAL_WIDTH = 1200
INITIAL_HEIGHT = 750

_VAULT_STATE_TEXT = {
    VaultState.UNINITIALIZED: strings.VAULT_STATE_UNINITIALIZED,
    VaultState.LOCKED: strings.VAULT_STATE_LOCKED,
    VaultState.UNLOCKED: strings.VAULT_STATE_UNLOCKED,
}


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
        self.resize(INITIAL_WIDTH, INITIAL_HEIGHT)

        self.tabs = QTabWidget(self)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self._on_current_tab_changed)
        self.setCentralWidget(self.tabs)

        self._build_menus()
        self.vault_label = QLabel()
        self.grid_label = QLabel()
        self.statusBar().addPermanentWidget(self.vault_label)
        self.statusBar().addPermanentWidget(self.grid_label)
        services.vault.add_listener(lambda _state: self.refresh_vault_ui())
        self.refresh_vault_ui()

    @property
    def services(self) -> AppServices:
        """The shared services passed at construction."""
        return self._services

    # ----- menus ------------------------------------------------------------------------

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu(strings.MENU_FILE)
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
        self.action_quit = self._action(strings.ACTION_QUIT, self.close)
        self.action_quit.setMenuRole(QAction.MenuRole.QuitRole)
        file_menu.addAction(self.action_quit)

        session_menu = self.menuBar().addMenu(strings.MENU_SESSION)
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

    def _add_terminal_tab(self, view: QWidget, title: str) -> int:
        terminal = getattr(view, "terminal", None)
        if isinstance(terminal, TerminalWidget):
            terminal.grid_size_changed.connect(
                lambda cols, rows, t=terminal: self._on_grid_size(t, cols, rows)
            )
        index = self.tabs.addTab(view, title)
        self.tabs.setCurrentIndex(index)
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

    def close_tab(self, index: int) -> None:
        """Close the tab at ``index``."""
        widget = self.tabs.widget(index)
        if widget is None:
            return
        self.tabs.removeTab(index)
        widget.deleteLater()

    def close_current_tab(self) -> None:
        """Close the active tab."""
        if self.tabs.count():
            self.close_tab(self.tabs.currentIndex())

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

    def _on_grid_size(self, terminal: TerminalWidget, cols: int, rows: int) -> None:
        if terminal is self.active_terminal():
            self._show_grid(cols, rows)

    def _show_grid(self, cols: int, rows: int) -> None:
        self.grid_label.setText(strings.GRID_SIZE.format(cols=cols, rows=rows))
