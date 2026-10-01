"""Integration test configuration (SPEC §10.3).

The test server is read from ``PYSSH_TEST_*`` variables. When its port cannot be reached
within 2 s, every integration test is skipped (not failed).
"""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from pathlib import Path

import pytest

from pyssh.core.ssh_worker import ConnectParams, HostKeyDecision, SSHWorker

ROOT = Path(__file__).resolve().parents[2]
SIGNAL_TIMEOUT_MS = 15_000


@dataclass(frozen=True)
class TestServer:
    """Connection data of the SSH test server."""

    __test__ = False  # not a test class

    host: str
    port: int
    user: str
    password: str
    key: Path
    key_pass: Path
    key_passphrase: str


def _server_from_env() -> TestServer:
    env = os.environ
    return TestServer(
        host=env.get("PYSSH_TEST_HOST", "127.0.0.1"),
        port=int(env.get("PYSSH_TEST_PORT", "2222")),
        user=env.get("PYSSH_TEST_USER", "tester"),
        password=env.get("PYSSH_TEST_PASSWORD", "secret"),
        key=ROOT / env.get("PYSSH_TEST_KEY", "tests/keys/id_ed25519"),
        key_pass=ROOT / env.get("PYSSH_TEST_KEY_PASS", "tests/keys/id_ed25519_pass"),
        key_passphrase=env.get("PYSSH_TEST_KEY_PASSPHRASE", "testpass"),
    )


def _reachable(server: TestServer) -> bool:
    try:
        with socket.create_connection((server.host, server.port), timeout=2):
            return True
    except OSError:
        return False


def pytest_collection_modifyitems(config, items) -> None:
    here = Path(__file__).parent
    for item in items:
        if here in Path(str(item.fspath)).parents:
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def server() -> TestServer:
    """The test server; skips the test when it is not reachable."""
    srv = _server_from_env()
    if not _reachable(srv):
        pytest.skip(f"SSH test server {srv.host}:{srv.port} not reachable within 2 s")
    return srv


class WorkerRun:
    """Collects everything a worker emits and answers host key questions."""

    def __init__(self, worker: SSHWorker, decision: HostKeyDecision) -> None:
        self.worker = worker
        self.decision = decision
        self.output = bytearray()
        self.host_key_questions: list[tuple] = []
        self.auth_failures: list[str] = []
        self.failures: list[tuple[str, str]] = []
        self.disconnects: list[str] = []
        worker.host_key_unknown.connect(self._on_host_key)
        worker.data_received.connect(self.output.extend)
        worker.auth_failed.connect(self.auth_failures.append)
        worker.failed.connect(lambda code, msg: self.failures.append((code, msg)))
        worker.disconnected.connect(self.disconnects.append)

    def _on_host_key(self, *args) -> None:
        self.host_key_questions.append(args)
        self.worker.resolve_host_key(self.decision)

    def text(self) -> str:
        return self.output.decode("utf-8", errors="replace")


@pytest.fixture
def make_worker(tmp_path: Path):
    """Factory: ``make_worker(**ConnectParams overrides, decision=..., known_hosts=...)``."""
    created: list[SSHWorker] = []

    def make(
        server: TestServer,
        *,
        decision: HostKeyDecision = HostKeyDecision.ACCEPT_ONCE,
        known_hosts: Path | None = None,
        **overrides,
    ) -> WorkerRun:
        params = {
            "host": server.host,
            "port": server.port,
            "username": server.user,
            "password": server.password,
            "connect_timeout": 5,
        }
        params.update(overrides)
        worker = SSHWorker(ConnectParams(**params), known_hosts or tmp_path / "known_hosts")
        created.append(worker)
        return WorkerRun(worker, decision)

    yield make
    for worker in created:
        worker.blockSignals(True)
        worker.stop()
        worker.join(2.0)
