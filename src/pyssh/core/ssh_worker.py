"""SSH connection running in a worker thread (SPEC §5.4, §7.11).

Only ``PySide6.QtCore`` is used (rule A6). The worker never touches the emulator or any
widget; it only emits signals, which Qt queues to the GUI thread (rules A2, A3).
"""

from __future__ import annotations

import contextlib
import logging
import queue
import select
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Protocol

import paramiko
from PySide6.QtCore import QObject, Signal, SignalInstance

from pyssh import strings
from pyssh.core import known_hosts
from pyssh.core.errors import HostKeyRejected, UserError, describe_error

log = logging.getLogger(__name__)

HOST_KEY_WAIT_S = 300.0
HOST_KEY_POLL_S = 0.1
SELECT_TIMEOUT_S = 0.02
PAUSE_SLEEP_S = 0.01
RECV_SIZE = 65536
EXIT_STATUS_WAIT_S = 1.0
BANNER_TIMEOUT = 15
AUTH_TIMEOUT = 20


@dataclass(frozen=True)
class ConnectParams:
    """Everything the worker needs; secrets are excluded from ``repr`` (rule A5)."""

    host: str
    port: int
    username: str
    password: str | None = field(default=None, repr=False)
    pkey: paramiko.PKey | None = field(default=None, repr=False)
    cols: int = 80
    rows: int = 24
    connect_timeout: int = 10
    keepalive: int = 30


class HostKeyDecision(Enum):
    """User answer for an unknown host key."""

    ACCEPT_SAVE = "accept_save"
    ACCEPT_ONCE = "accept_once"
    REJECT = "reject"


class WorkerProtocol(Protocol):
    """Interface used by ``TerminalTab``; ``tests/fakes.py`` implements it too."""

    connected: SignalInstance
    data_received: SignalInstance
    host_key_unknown: SignalInstance
    auth_failed: SignalInstance
    failed: SignalInstance
    disconnected: SignalInstance
    finished: SignalInstance

    def start(self) -> None: ...
    def send(self, data: bytes) -> None: ...
    def resize(self, cols: int, rows: int) -> None: ...
    def set_paused(self, paused: bool) -> None: ...
    def resolve_host_key(self, decision: HostKeyDecision) -> None: ...
    def stop(self) -> None: ...
    def join(self, timeout: float) -> bool: ...
    def blockSignals(self, block: bool) -> bool: ...


class _InteractivePolicy(paramiko.MissingHostKeyPolicy):
    """Asks the GUI (through the worker) whether to trust an unknown host key."""

    def __init__(self, worker: SSHWorker, known_hosts_path: Path) -> None:
        self._worker = worker
        self._known_hosts = known_hosts_path

    def missing_host_key(self, client, hostname, key) -> None:
        decision = self._worker._ask_host_key(key)  # blocks the worker thread
        if decision is HostKeyDecision.REJECT:
            raise HostKeyRejected()
        client.get_host_keys().add(hostname, key.get_name(), key)
        if decision is HostKeyDecision.ACCEPT_SAVE:
            with known_hosts.KNOWN_HOSTS_LOCK:
                client.save_host_keys(str(self._known_hosts))


class SSHWorker(QObject):
    """One SSH connection in its own daemon thread. Must not have a Qt parent (rule A4)."""

    host_key_unknown = Signal(str, int, str, str)
    connected = Signal()
    data_received = Signal(bytes)
    auth_failed = Signal(str)
    failed = Signal(str, str)
    disconnected = Signal(str)
    finished = Signal()

    def __init__(self, params: ConnectParams, known_hosts_path: Path) -> None:
        """Prepare the worker; nothing happens until ``start()``."""
        super().__init__()
        self._params = params
        self._known_hosts = known_hosts_path
        self._out_q: queue.Queue[bytes] = queue.Queue()
        self._stop = threading.Event()
        self._paused = threading.Event()
        self._connected_flag = threading.Event()
        self._host_key_event = threading.Event()
        self._host_key_decision = HostKeyDecision.REJECT
        self._resize_lock = threading.Lock()
        self._pending_resize: tuple[int, int] | None = None
        self._client: paramiko.SSHClient | None = None
        self._thread: threading.Thread | None = None

    # ----- called from the GUI thread ---------------------------------------------------

    def start(self) -> None:
        """Start the connection thread (only once)."""
        if self._thread is not None:
            raise RuntimeError("worker already started")
        self._thread = threading.Thread(
            target=self._run, daemon=True, name=f"ssh-{self._params.host}"
        )
        self._thread.start()

    def send(self, data: bytes) -> None:
        """Queue bytes for the server; ignored when not connected."""
        if self._connected_flag.is_set() and not self._stop.is_set():
            self._out_q.put(data)

    def resize(self, cols: int, rows: int) -> None:
        """Request a PTY size; only the latest request is applied."""
        with self._resize_lock:
            self._pending_resize = (cols, rows)

    def set_paused(self, paused: bool) -> None:
        """Backpressure: stop/resume reading from the channel."""
        if paused:
            self._paused.set()
        else:
            self._paused.clear()

    def resolve_host_key(self, decision: HostKeyDecision) -> None:
        """Answer a ``host_key_unknown`` question."""
        self._host_key_decision = decision
        self._host_key_event.set()

    def stop(self) -> None:
        """Stop the connection without waiting; closing the client breaks blocking I/O."""
        self._stop.set()
        self._host_key_event.set()
        client = self._client
        if client is not None:
            try:
                client.close()
            except Exception:
                log.debug("error while closing client", exc_info=True)

    def join(self, timeout: float) -> bool:
        """Wait up to ``timeout`` seconds; ``True`` when the thread has finished."""
        if self._thread is None:
            return True
        self._thread.join(timeout)
        return not self._thread.is_alive()

    # ----- worker thread ----------------------------------------------------------------

    def _describe(self, exc: BaseException) -> UserError:
        p = self._params
        return describe_error(
            exc, host=p.host, port=p.port, username=p.username, timeout=p.connect_timeout
        )

    def _ask_host_key(self, key: paramiko.PKey) -> HostKeyDecision:
        self._host_key_event.clear()
        self._host_key_decision = HostKeyDecision.REJECT
        p = self._params
        self.host_key_unknown.emit(
            p.host, p.port, key.get_name(), known_hosts.fingerprint_sha256(key)
        )
        waited = 0.0
        while not self._host_key_event.wait(HOST_KEY_POLL_S):
            waited += HOST_KEY_POLL_S
            if self._stop.is_set() or waited >= HOST_KEY_WAIT_S:
                return HostKeyDecision.REJECT
        if self._stop.is_set():
            return HostKeyDecision.REJECT
        return self._host_key_decision

    def _run(self) -> None:
        client = paramiko.SSHClient()
        self._client = client
        p = self._params
        try:
            known_hosts.ensure_file(self._known_hosts)
            client.load_host_keys(str(self._known_hosts))
            client.set_missing_host_key_policy(_InteractivePolicy(self, self._known_hosts))
            client.connect(
                hostname=p.host,
                port=p.port,
                username=p.username,
                password=p.password,
                pkey=p.pkey,
                timeout=p.connect_timeout,
                banner_timeout=BANNER_TIMEOUT,
                auth_timeout=AUTH_TIMEOUT,
                allow_agent=False,
                look_for_keys=False,
            )
            if self._stop.is_set():
                return
            transport = client.get_transport()
            if transport is None:
                raise paramiko.SSHException("no transport after connect")
            if p.keepalive > 0:
                transport.set_keepalive(p.keepalive)
            chan = client.invoke_shell(term="xterm-256color", width=p.cols, height=p.rows)
            self._connected_flag.set()
            log.info("connected %s@%s:%s", p.username, p.host, p.port)
            self.connected.emit()
            reason = self._io_loop(chan)
            log.info("disconnected %s:%s", p.host, p.port)
            self.disconnected.emit(reason)
        except paramiko.AuthenticationException as exc:
            if not self._stop.is_set():
                log.info("authentication failed %s@%s:%s", p.username, p.host, p.port)
                self.auth_failed.emit(self._describe(exc).message)
        except Exception as exc:
            if not self._stop.is_set():
                err = self._describe(exc)
                log.warning("connect failed %s:%s code=%s", p.host, p.port, err.code, exc_info=True)
                self.failed.emit(err.code, err.message)
        finally:
            with contextlib.suppress(Exception):
                client.close()
            self.finished.emit()

    def _apply_pending_resize(self, chan: paramiko.Channel) -> None:
        with self._resize_lock:
            pending, self._pending_resize = self._pending_resize, None
        if pending is not None:
            cols, rows = pending
            chan.resize_pty(width=cols, height=rows)

    def _flush_outgoing(self, chan: paramiko.Channel) -> None:
        while True:
            try:
                data = self._out_q.get_nowait()
            except queue.Empty:
                return
            chan.sendall(data)

    def _io_loop(self, chan: paramiko.Channel) -> str:
        try:
            while not self._stop.is_set():
                self._apply_pending_resize(chan)
                self._flush_outgoing(chan)
                transport = chan.get_transport()
                if chan.closed or transport is None or not transport.is_active():
                    break
                if self._paused.is_set():
                    time.sleep(PAUSE_SLEEP_S)
                    continue
                readable, _, _ = select.select([chan], [], [], SELECT_TIMEOUT_S)
                if readable:
                    data = chan.recv(RECV_SIZE)
                    if not data:
                        break
                    self.data_received.emit(data)
        except (OSError, EOFError, paramiko.SSHException) as exc:
            log.info("connection lost: %s", type(exc).__name__)
            return strings.DISCONNECT_LOST
        if self._stop.is_set():
            return strings.DISCONNECT_BY_USER
        if self._wait_exit_status(chan):
            return strings.DISCONNECT_SESSION_ENDED.format(code=chan.recv_exit_status())
        return strings.DISCONNECT_LOST

    def _wait_exit_status(self, chan: paramiko.Channel) -> bool:
        """OpenSSH may send channel EOF before "exit-status"; wait briefly for it."""
        deadline = time.monotonic() + EXIT_STATUS_WAIT_S
        while not chan.exit_status_ready():
            transport = chan.get_transport()
            if (
                self._stop.is_set()
                or transport is None
                or not transport.is_active()
                or time.monotonic() >= deadline
            ):
                return chan.exit_status_ready()
            time.sleep(PAUSE_SLEEP_S)
        return True
