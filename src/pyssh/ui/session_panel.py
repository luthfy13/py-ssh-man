"""Session list panel with search (SPEC §9.4)."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QAction, QKeyEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pyssh import config, strings
from pyssh.core import known_hosts
from pyssh.models import SessionConfig
from pyssh.services import AppServices
from pyssh.ui.dialogs import confirm
from pyssh.ui.session_dialog import SessionDialog

ID_ROLE = Qt.ItemDataRole.UserRole


def matches(session: SessionConfig, query: str) -> bool:
    """Case-insensitive "contains" on name, host and username (SPEC §9.4)."""
    needle = query.strip().casefold()
    if not needle:
        return True
    fields = (session.name, session.host, session.username)
    return any(needle in value.casefold() for value in fields)


class _SessionList(QListWidget):
    """List that maps Enter, F2 and Delete (Backspace on macOS) to panel actions."""

    activate = Signal()
    edit = Signal()
    remove = Signal()

    def __init__(self, *, mac: bool = config.IS_MAC) -> None:
        super().__init__()
        self._delete_keys = {Qt.Key.Key_Delete} | ({Qt.Key.Key_Backspace} if mac else set())

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.activate.emit()
        elif key == Qt.Key.Key_F2:
            self.edit.emit()
        elif key in self._delete_keys:
            self.remove.emit()
        else:
            super().keyPressEvent(event)
            return
        event.accept()


class SessionPanel(QWidget):
    """Saved sessions: filter, list, buttons and context menu."""

    open_requested = Signal(object)  # SessionConfig
    sessions_changed = Signal()

    def __init__(self, services: AppServices, parent: QWidget | None = None) -> None:
        """Build the panel and load the sessions."""
        super().__init__(parent)
        self._services = services
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText(strings.SEARCH_PLACEHOLDER)
        self.filter_edit.setClearButtonEnabled(True)
        self.list = _SessionList()
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.setSpacing(2)
        self.empty_label = QLabel(strings.PANEL_EMPTY)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.list)
        self.stack.addWidget(self.empty_label)
        self.new_button = QPushButton(strings.BUTTON_NEW)
        self.edit_button = QPushButton(strings.BUTTON_EDIT)
        self.delete_button = QPushButton(strings.BUTTON_DELETE)

        buttons = QHBoxLayout()
        buttons.addWidget(self.new_button)
        buttons.addWidget(self.edit_button)
        buttons.addWidget(self.delete_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.filter_edit)
        layout.addWidget(self.stack, 1)
        layout.addLayout(buttons)

        self.filter_edit.textChanged.connect(self.refresh)
        self.list.itemDoubleClicked.connect(lambda _item: self.open_selected())
        self.list.activate.connect(self.open_selected)
        self.list.edit.connect(self.edit_selected)
        self.list.remove.connect(self.delete_selected)
        self.list.currentItemChanged.connect(lambda *_: self._update_buttons())
        self.list.customContextMenuRequested.connect(self._show_context_menu)
        self.new_button.clicked.connect(self.new_session)
        self.edit_button.clicked.connect(self.edit_selected)
        self.delete_button.clicked.connect(self.delete_selected)
        self.refresh()

    # ----- list -------------------------------------------------------------------------

    def refresh(self) -> None:
        """Reload sessions from the store, keep the selection when possible."""
        selected = self.selected_session()
        selected_id = selected.id if selected else None
        query = self.filter_edit.text()
        sessions = self._services.session_store.all()
        self.list.clear()
        for session in sessions:
            if not matches(session, query):
                continue
            item = QListWidgetItem(f"{session.name}\n{session.target()}")
            item.setData(ID_ROLE, session.id)
            item.setToolTip(session.target())
            self.list.addItem(item)
            if session.id == selected_id:
                self.list.setCurrentItem(item)
        self.stack.setCurrentWidget(self.list if sessions else self.empty_label)
        self._update_buttons()

    def visible_names(self) -> list[str]:
        """Names currently listed (after filtering)."""
        return [self.list.item(i).text().split("\n", 1)[0] for i in range(self.list.count())]

    def selected_session(self) -> SessionConfig | None:
        """Session of the current item, fresh from the store."""
        item = self.list.currentItem()
        if item is None:
            return None
        return self._services.session_store.get(item.data(ID_ROLE))

    def select(self, session_id: str) -> None:
        """Make the session with ``session_id`` current (if listed)."""
        for i in range(self.list.count()):
            if self.list.item(i).data(ID_ROLE) == session_id:
                self.list.setCurrentRow(i)
                return

    def _update_buttons(self) -> None:
        has = self.list.currentItem() is not None
        self.edit_button.setEnabled(has)
        self.delete_button.setEnabled(has)

    # ----- actions ----------------------------------------------------------------------

    def open_selected(self) -> None:
        """Ask the main window to open the selected session."""
        session = self.selected_session()
        if session is not None:
            self.open_requested.emit(session)

    def new_session(self) -> None:
        """Create a session with ``SessionDialog``."""
        dialog = SessionDialog(self._services, None, self)
        if dialog.exec() and dialog.saved_session is not None:
            self._after_change(dialog.saved_session.id)

    def edit_selected(self) -> None:
        """Edit the selected session."""
        session = self.selected_session()
        if session is None:
            return
        dialog = SessionDialog(self._services, session, self)
        if dialog.exec() and dialog.saved_session is not None:
            self._after_change(dialog.saved_session.id)

    def duplicate_selected(self) -> None:
        """Copy the selected session (without its secret)."""
        session = self.selected_session()
        if session is not None:
            copy = self._services.session_store.duplicate(session.id)
            self._after_change(copy.id)

    def delete_selected(self) -> None:
        """Delete the selected session after confirmation; its secret goes too (cascade)."""
        session = self.selected_session()
        if session is None:
            return
        if confirm(self, strings.DELETE_TITLE, strings.DELETE_CONFIRM.format(name=session.name)):
            self._services.session_store.delete(session.id)
            self._after_change(None)

    def forget_host_key(self) -> None:
        """Remove the stored host key of the selected session."""
        session = self.selected_session()
        if session is None:
            return
        target = f"{session.host}:{session.port}"
        removed = known_hosts.forget_host(
            self._services.paths.known_hosts_file, session.host, session.port
        )
        text = strings.FORGET_DONE if removed else strings.FORGET_NONE
        QMessageBox.information(self, strings.FORGET_TITLE, text.format(target=target))

    def _after_change(self, select_id: str | None) -> None:
        self.refresh()
        if select_id is not None:
            self.select(select_id)
        self.sessions_changed.emit()

    def context_menu(self) -> QMenu:
        """Menu for the selected session (exposed for tests)."""
        menu = QMenu(self)
        actions: list[tuple[str, object]] = [
            (strings.MENU_OPEN, self.open_selected),
            (strings.MENU_EDIT, self.edit_selected),
            (strings.MENU_DUPLICATE, self.duplicate_selected),
            (strings.MENU_DELETE, self.delete_selected),
        ]
        for text, slot in actions:
            action = QAction(text, menu)
            action.triggered.connect(lambda _checked=False, s=slot: s())
            menu.addAction(action)
        menu.addSeparator()
        forget = QAction(strings.MENU_FORGET_HOST_KEY, menu)
        forget.triggered.connect(lambda _checked=False: self.forget_host_key())
        menu.addAction(forget)
        return menu

    def _show_context_menu(self, pos: QPoint) -> None:
        item = self.list.itemAt(pos)
        if item is None:
            return
        self.list.setCurrentItem(item)
        self.context_menu().exec(self.list.viewport().mapToGlobal(pos))
