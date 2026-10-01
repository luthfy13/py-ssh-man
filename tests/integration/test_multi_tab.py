"""Integration tests: parallel sessions and lifecycle (SPEC §10.2, AC-6.2, AC-6.3, N-08)."""

from __future__ import annotations

import threading
import time

import pytest

from pyssh.core.ssh_worker import HostKeyDecision, SSHWorker
from pyssh.ui import main_window as main_window_module
from pyssh.ui.dialogs import HostKeyDialog, PasswordDialog
from pyssh.ui.main_window import MainWindow
from pyssh.ui.terminal_tab import TabState

TIMEOUT = 15_000


def _ssh_threads() -> list[str]:
    return [t.name for t in threading.enumerate() if t.name.startswith("ssh-") and t.is_alive()]


def test_five_parallel_sessions_get_their_own_output(qtbot, server, make_worker) -> None:
    runs = [make_worker(server) for _ in range(5)]
    for run in runs:
        run.worker.start()
    for run in runs:
        qtbot.waitUntil(lambda run=run: run.worker._connected_flag.is_set(), timeout=TIMEOUT)
    for i, run in enumerate(runs):
        run.worker.send(f"echo tab-{i}-$(({i}*7+1000))\n".encode())
    for i, run in enumerate(runs):
        marker = f"tab-{i}-{i * 7 + 1000}".encode()
        qtbot.waitUntil(lambda run=run, marker=marker: marker in run.output, timeout=TIMEOUT)
    for i, run in enumerate(runs):
        others = [f"tab-{j}-{j * 7 + 1000}".encode() for j in range(5) if j != i]
        assert not any(other in run.output for other in others)


def test_twenty_connect_disconnect_cycles_leave_no_threads(
    qtbot, server, make_worker, tmp_path
) -> None:
    known_hosts = tmp_path / "kh"
    for _ in range(20):
        run = make_worker(server, decision=HostKeyDecision.ACCEPT_SAVE, known_hosts=known_hosts)
        with qtbot.waitSignal(run.worker.connected, timeout=TIMEOUT):
            run.worker.start()
        run.worker.stop()
        assert run.worker.join(2.0)
    qtbot.waitUntil(lambda: _ssh_threads() == [], timeout=5000)


@pytest.fixture
def real_services(services, monkeypatch: pytest.MonkeyPatch, server):
    """AppServices with the real SSHWorker; dialogs answer automatically."""
    services.worker_factory = SSHWorker
    monkeypatch.setattr(PasswordDialog, "ask", lambda self: (server.password, False))
    monkeypatch.setattr(HostKeyDialog, "ask", lambda self: HostKeyDecision.ACCEPT_ONCE)
    monkeypatch.setattr(main_window_module, "confirm", lambda *a: True)
    return services


def test_closing_connected_tab_does_not_block(qtbot, real_services, server) -> None:
    window = MainWindow(real_services)
    qtbot.addWidget(window)
    window.show()
    tab = window.open_adhoc(server.user, server.host, server.port)
    qtbot.waitUntil(lambda: tab.state is TabState.CONNECTED, timeout=TIMEOUT)
    started = time.perf_counter()
    tab.close_session()
    assert time.perf_counter() - started < 0.1  # AC-6.3
    assert tab.join_workers(2.0)
    window.close()
    real_services.database.open()  # closed by closeEvent; reopened for fixture teardown


def test_closing_app_with_five_sessions(qtbot, real_services, server) -> None:
    window = MainWindow(real_services)
    qtbot.addWidget(window)
    window.show()
    tabs = [window.open_adhoc(server.user, server.host, server.port) for _ in range(5)]
    for tab in tabs:
        qtbot.waitUntil(lambda tab=tab: tab.state is TabState.CONNECTED, timeout=TIMEOUT)
    assert len(_ssh_threads()) == 5
    started = time.perf_counter()
    window.close()
    elapsed = time.perf_counter() - started
    assert not window.isVisible()
    assert elapsed < 2.0  # N-08 / MT-6.2 budget; join budget is 1.5 s
    qtbot.waitUntil(lambda: _ssh_threads() == [], timeout=3000)
    real_services.database.open()
