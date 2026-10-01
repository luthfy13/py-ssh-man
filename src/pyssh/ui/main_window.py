"""Main application window (SPEC §9.1)."""

from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QLabel, QMainWindow, QWidget

from pyssh import config, strings
from pyssh.core.vault import VaultState
from pyssh.services import AppServices
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


class MainWindow(QMainWindow):
    """Top-level window: menus, status bar (sessions and tabs follow in later phases)."""

    def __init__(self, services: AppServices, parent: QWidget | None = None) -> None:
        """Create the window, its menus and status bar."""
        super().__init__(parent)
        self._services = services
        self.setWindowTitle(config.APP_NAME)
        self.resize(INITIAL_WIDTH, INITIAL_HEIGHT)
        self._build_menus()
        self.vault_label = QLabel()
        self.statusBar().addPermanentWidget(self.vault_label)
        services.vault.add_listener(lambda _state: self.refresh_vault_ui())
        self.refresh_vault_ui()

    @property
    def services(self) -> AppServices:
        """The shared services passed at construction."""
        return self._services

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

    def _action(self, text: str, slot) -> QAction:  # slot: Callable[[], object]
        action = QAction(text, self)
        action.triggered.connect(lambda _checked=False: slot())
        return action

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
