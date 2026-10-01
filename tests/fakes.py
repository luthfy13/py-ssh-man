"""Test doubles, including ``FakeWorker`` (SPEC §10.1)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from pyssh.core.ssh_worker import ConnectParams, HostKeyDecision


class FakeWorker(QObject):
    """Implements ``WorkerProtocol``; tests emit its signals to drive ``TerminalTab``."""

    host_key_unknown = Signal(str, int, str, str)
    connected = Signal()
    data_received = Signal(bytes)
    auth_failed = Signal(str)
    failed = Signal(str, str)
    disconnected = Signal(str)
    finished = Signal()

    def __init__(self, params: ConnectParams, known_hosts_path: Path) -> None:
        super().__init__()
        self.params = params
        self.known_hosts_path = known_hosts_path
        self.started = False
        self.stopped = False
        self.sent: list[bytes] = []
        self.resizes: list[tuple[int, int]] = []
        self.paused: list[bool] = []
        self.host_key_decisions: list[HostKeyDecision] = []

    def start(self) -> None:
        self.started = True

    def send(self, data: bytes) -> None:
        self.sent.append(data)

    def resize(self, cols: int, rows: int) -> None:
        self.resizes.append((cols, rows))

    def set_paused(self, paused: bool) -> None:
        self.paused.append(paused)

    def resolve_host_key(self, decision: HostKeyDecision) -> None:
        self.host_key_decisions.append(decision)

    def stop(self) -> None:
        self.stopped = True

    def join(self, timeout: float) -> bool:
        return True


class WorkerFactory:
    """``worker_factory`` that records every ``FakeWorker`` it creates."""

    def __init__(self) -> None:
        self.workers: list[FakeWorker] = []

    def __call__(self, params: ConnectParams, known_hosts_path: Path) -> FakeWorker:
        worker = FakeWorker(params, known_hosts_path)
        self.workers.append(worker)
        return worker

    @property
    def last(self) -> FakeWorker:
        return self.workers[-1]
