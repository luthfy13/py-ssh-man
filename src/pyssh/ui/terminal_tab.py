"""``TerminalTab``: connection state machine and credential flow (SPEC §9.6)."""

from __future__ import annotations

import logging
from enum import Enum

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from pyssh import strings
from pyssh.core.key_loader import KeyLoadError, PassphraseRequired, load_private_key
from pyssh.core.ssh_worker import ConnectParams, HostKeyDecision, WorkerProtocol
from pyssh.models import AuthType, SessionConfig
from pyssh.services import AppServices
from pyssh.terminal.view import TerminalView
from pyssh.terminal.widget import TerminalWidget
from pyssh.ui.dialogs import HostKeyDialog, PasswordDialog, wait_cursor
from pyssh.ui.vault_dialogs import ensure_vault_unlocked

log = logging.getLogger(__name__)

MAX_PASSWORD_ATTEMPTS = 3


class TabState(Enum):
    """Connection state of a tab (SPEC §9.6.1)."""

    IDLE = "idle"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    FAILED = "failed"
    CLOSED = "closed"


STATE_TEXT = {
    TabState.IDLE: strings.STATE_IDLE,
    TabState.CONNECTING: strings.STATE_CONNECTING,
    TabState.CONNECTED: strings.STATE_CONNECTED,
    TabState.DISCONNECTED: strings.STATE_DISCONNECTED,
    TabState.FAILED: strings.STATE_FAILED,
    TabState.CLOSED: strings.STATE_DISCONNECTED,
}


class Banner(QFrame):
    """Warning strip above the terminal with Reconnect and Close Tab buttons."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the (initially hidden) banner."""
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        icon = QLabel()
        icon.setPixmap(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning).pixmap(16, 16)
        )
        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        self.reconnect_button = QPushButton(strings.BANNER_RECONNECT)
        self.close_button = QPushButton(strings.BANNER_CLOSE)
        layout = QHBoxLayout(self)
        layout.addWidget(icon)
        layout.addWidget(self.message_label, 1)
        layout.addWidget(self.reconnect_button)
        layout.addWidget(self.close_button)
        self.hide()


class TerminalTab(QWidget):
    """One SSH session: a terminal view plus the worker that feeds it."""

    state_changed = Signal(object)
    title_changed = Signal(str)
    close_requested = Signal()
    info_message = Signal(str)

    def __init__(
        self,
        session: SessionConfig,
        services: AppServices,
        *,
        adhoc: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        """Create the view; call ``connect_session()`` to start connecting."""
        super().__init__(parent)
        self._session = session
        self._services = services
        self._adhoc = adhoc
        self._state = TabState.IDLE
        self._worker: WorkerProtocol | None = None
        self._retired: list[WorkerProtocol] = []
        self._attempts = 0
        self._prompted: tuple[str, bool] | None = None
        self._message = ""

        self.banner = Banner(self)
        self.view = TerminalView(services.settings_store.current, parent=self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.banner)
        layout.addWidget(self.view, 1)
        self.setFocusProxy(self.view)

        terminal = self.view.terminal
        terminal.set_input_enabled(False)
        terminal.input_bytes.connect(self._on_input)
        terminal.grid_size_changed.connect(self._on_grid_size)
        terminal.backpressure.connect(self._on_backpressure)
        terminal.reconnect_requested.connect(self.reconnect)
        terminal.title_changed.connect(self.title_changed)
        self.banner.reconnect_button.clicked.connect(self.reconnect)
        self.banner.close_button.clicked.connect(self.close_requested)

    # ----- properties -------------------------------------------------------------------

    @property
    def state(self) -> TabState:
        """Current connection state."""
        return self._state

    @property
    def terminal(self) -> TerminalWidget:
        """The terminal widget."""
        return self.view.terminal

    @property
    def session(self) -> SessionConfig:
        """The session shown in this tab."""
        return self._session

    @property
    def adhoc(self) -> bool:
        """True for ``--connect`` sessions that are not stored."""
        return self._adhoc

    @property
    def message(self) -> str:
        """Last failure or disconnect message (shown in the banner)."""
        return self._message

    @property
    def worker(self) -> WorkerProtocol | None:
        """Active worker, if any."""
        return self._worker

    def status_text(self) -> str:
        """Status bar text, e.g. "Terhubung — admin@10.0.0.5:22"."""
        return strings.STATUS_LINE.format(
            state=STATE_TEXT[self._state], target=self._session.target()
        )

    # ----- public actions ---------------------------------------------------------------

    def connect_session(self) -> None:
        """Start connecting (SPEC §9.6.3)."""
        if self._state in (TabState.CONNECTING, TabState.CONNECTED, TabState.CLOSED):
            return
        self._attempts = 0
        self._prompted = None
        self._set_state(TabState.CONNECTING)
        self.terminal.write_local(strings.CONNECTING.format(target=self._session.target()))
        if self._session.auth_type is AuthType.KEY:
            self._connect_with_key()
            return
        secret = None
        if self._session.remember_secret and not self._adhoc:
            secret = self._services.secret_store.get_secret(self._session.id)
        if secret is not None:
            self._start_worker(password=secret)
        else:
            self._prompt_password_and_start(error=None)

    def reconnect(self) -> None:
        """Connect again after a failure or disconnect."""
        if self._state not in (TabState.IDLE, TabState.FAILED, TabState.DISCONNECTED):
            return
        self._retire_worker()
        self.connect_session()

    def close_session(self) -> None:
        """Stop the worker without waiting for its thread (SPEC §9.9)."""
        self._retire_worker()
        self._set_state(TabState.CLOSED)

    def join_workers(self, timeout: float) -> bool:
        """Wait for stopped worker threads; ``True`` when all have finished."""
        done = True
        for worker in self._retired:
            done = worker.join(timeout) and done
        return done

    # ----- credential flow --------------------------------------------------------------

    def _connect_with_key(self) -> None:
        path = self._session.key_path or ""
        try:
            with wait_cursor():
                pkey = load_private_key(path)
        except PassphraseRequired:
            pkey = self._load_key_with_passphrase(path)
            if pkey is None:
                return
        except KeyLoadError as exc:
            self._fail(exc.message)
            return
        self._start_worker(pkey=pkey)

    def _load_key_with_passphrase(self, path: str):  # -> paramiko.PKey | None
        """Stored passphrase first, then up to 3 prompts (SPEC §9.6.3 step 2)."""
        candidate = None
        if self._session.remember_secret and not self._adhoc:
            candidate = self._services.secret_store.get_secret(self._session.id)
        error: str | None = None
        prompts = 0
        while True:
            if candidate is None:
                if prompts >= MAX_PASSWORD_ATTEMPTS:
                    self._fail(strings.KEY_BAD_PASSPHRASE)
                    return None
                answer = PasswordDialog(
                    title=strings.PASSPHRASE_TITLE,
                    prompt=strings.PASSPHRASE_PROMPT.format(path=path),
                    field_label=strings.PASSPHRASE_FIELD,
                    remember_label=strings.PASSPHRASE_REMEMBER,
                    error=error,
                    show_remember=not self._adhoc,
                    remember_default=self._session.remember_secret,
                    parent=self,
                ).ask()
                prompts += 1
                if answer is None:
                    self._fail(strings.CANCELLED_BY_USER)
                    return None
                candidate = answer[0]
                self._prompted = answer
            try:
                with wait_cursor():
                    return load_private_key(path, candidate)
            except KeyLoadError as exc:
                if exc.code != "KEY_BAD_PASSPHRASE":
                    self._fail(exc.message)
                    return None
                error = strings.PASSPHRASE_RETRY
                candidate = None
                self._prompted = None

    def _prompt_password_and_start(self, error: str | None) -> None:
        answer = PasswordDialog(
            title=strings.PASSWORD_TITLE,
            prompt=strings.PASSWORD_PROMPT.format(target=self._session.target()),
            error=error,
            show_remember=not self._adhoc,
            remember_default=self._session.remember_secret,
            parent=self,
        ).ask()
        if answer is None:
            self._fail(strings.CANCELLED_BY_USER)
            return
        self._prompted = answer
        self._start_worker(password=answer[0])

    def _start_worker(self, password: str | None = None, pkey=None) -> None:
        settings = self._services.settings_store.current
        cols, rows = self.terminal.grid_size()
        params = ConnectParams(
            host=self._session.host,
            port=self._session.port,
            username=self._session.username,
            password=password,
            pkey=pkey,
            cols=cols,
            rows=rows,
            connect_timeout=settings.connect_timeout_seconds,
            keepalive=settings.keepalive_seconds,
        )
        factory = self._services.worker_factory
        if factory is None:
            raise RuntimeError("AppServices.worker_factory is not set")
        worker = factory(params, self._services.paths.known_hosts_file)
        self._worker = worker
        worker.host_key_unknown.connect(
            lambda host, port, kt, fp, w=worker: self._on_host_key_unknown(w, host, port, kt, fp)
        )
        worker.connected.connect(lambda w=worker: self._on_connected(w))
        worker.data_received.connect(lambda data, w=worker: self._on_data(w, data))
        worker.auth_failed.connect(lambda msg, w=worker: self._on_auth_failed(w, msg))
        worker.failed.connect(lambda code, msg, w=worker: self._on_failed(w, code, msg))
        worker.disconnected.connect(lambda reason, w=worker: self._on_disconnected(w, reason))
        worker.finished.connect(lambda w=worker: self._on_finished(w))
        worker.start()

    def _save_prompted_secret(self) -> None:
        if self._prompted is None:
            return
        secret, remember = self._prompted
        self._prompted = None
        if not remember or self._adhoc:
            return
        if ensure_vault_unlocked(self, self._services.vault):
            self._services.secret_store.set_secret(self._session.id, secret)
            self._session.remember_secret = True
        else:
            self.info_message.emit(strings.SECRET_NOT_SAVED_VAULT)

    # ----- worker signals ---------------------------------------------------------------

    def _on_host_key_unknown(
        self, worker: WorkerProtocol, host: str, port: int, key_type: str, fingerprint: str
    ) -> None:
        if worker is not self._worker:
            return
        decision = HostKeyDialog(host, port, key_type, fingerprint, self).ask()
        if worker is self._worker:
            worker.resolve_host_key(decision)
        else:
            worker.resolve_host_key(HostKeyDecision.REJECT)

    def _on_connected(self, worker: WorkerProtocol) -> None:
        if worker is not self._worker:
            return
        self._attempts = 0
        self._set_state(TabState.CONNECTED)
        self._save_prompted_secret()
        if not self._adhoc:
            self._services.session_store.touch(self._session.id)
        self.terminal.setFocus()

    def _on_data(self, worker: WorkerProtocol, data: bytes) -> None:
        if worker is self._worker:
            self.terminal.feed(data)

    def _on_auth_failed(self, worker: WorkerProtocol, message: str) -> None:
        if worker is not self._worker:
            return
        if self._session.auth_type is AuthType.KEY:
            self._fail(strings.KEY_REJECTED)
            return
        self._attempts += 1
        self._prompted = None
        if self._attempts < MAX_PASSWORD_ATTEMPTS:
            self._retire_worker()
            self._prompt_password_and_start(error=strings.PASSWORD_RETRY)
        else:
            self._fail(message)

    def _on_failed(self, worker: WorkerProtocol, code: str, message: str) -> None:
        if worker is self._worker:
            self._fail(message, code)

    def _on_disconnected(self, worker: WorkerProtocol, reason: str) -> None:
        if worker is not self._worker:
            return
        self._message = reason
        self._set_state(TabState.DISCONNECTED)
        self.terminal.write_local(strings.PRESS_R_TO_RECONNECT.format(reason=reason), "yellow")

    def _on_finished(self, worker: WorkerProtocol) -> None:
        if worker is self._worker:
            self._worker = None
            self._retired.append(worker)

    # ----- terminal signals -------------------------------------------------------------

    def _on_input(self, data: bytes) -> None:
        if self._worker is not None and self._state is TabState.CONNECTED:
            self._worker.send(data)

    def _on_grid_size(self, cols: int, rows: int) -> None:
        if self._worker is not None:
            self._worker.resize(cols, rows)

    def _on_backpressure(self, paused: bool) -> None:
        if self._worker is not None:
            self._worker.set_paused(paused)

    # ----- helpers ----------------------------------------------------------------------

    def _fail(self, message: str, code: str | None = None) -> None:
        self._message = message
        self._set_state(TabState.FAILED)
        self.terminal.write_local(message, "red")
        if code == "E_HOSTKEY_CHANGED":
            if self._adhoc:
                hint = strings.HOSTKEY_CHANGED_HINT_ADHOC.format(
                    path=self._services.paths.known_hosts_file
                )
            else:
                hint = strings.HOSTKEY_CHANGED_HINT_SESSION
            QMessageBox.critical(self, strings.HOSTKEY_CHANGED_TITLE, f"{message}\n\n{hint}")

    def _retire_worker(self) -> None:
        worker, self._worker = self._worker, None
        if worker is not None:
            worker.blockSignals(True)
            worker.stop()
            self._retired.append(worker)

    def _set_state(self, state: TabState) -> None:
        self._state = state
        self.terminal.set_input_enabled(state is TabState.CONNECTED)
        if state in (TabState.DISCONNECTED, TabState.FAILED):
            self.banner.message_label.setText(self._message)
            self.banner.show()
        else:
            self.banner.hide()
        self.state_changed.emit(state)
