"""Integration tests: password login against a real SSH server (SPEC §10.3, 11 scenarios)."""

from __future__ import annotations

import io
import time
from pathlib import Path

import paramiko
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from pyssh.core.known_hosts import entry_name
from pyssh.core.ssh_worker import HostKeyDecision

TIMEOUT = 15_000


def _connect(qtbot, run) -> None:
    with qtbot.waitSignal(run.worker.connected, timeout=TIMEOUT):
        run.worker.start()


def _wait_output(qtbot, run, needle: bytes) -> None:
    qtbot.waitUntil(lambda: needle in run.output, timeout=TIMEOUT)


def test_01_connect_accept_once(qtbot, server, make_worker) -> None:
    run = make_worker(server, decision=HostKeyDecision.ACCEPT_ONCE)
    _connect(qtbot, run)
    assert len(run.host_key_questions) == 1
    host, port, key_type, fingerprint = run.host_key_questions[0]
    assert key_type == "ssh-ed25519"
    assert (host, port) == (server.host, server.port)
    assert fingerprint.startswith("SHA256:")


def test_02_command_output(qtbot, server, make_worker) -> None:
    run = make_worker(server)
    _connect(qtbot, run)
    run.worker.send(b"echo pyssh-$((40+2))\n")
    _wait_output(qtbot, run, b"pyssh-42")
    assert b"pyssh-42" in run.output


def test_03_resize_pty(qtbot, server, make_worker) -> None:
    run = make_worker(server)
    _connect(qtbot, run)
    run.worker.resize(100, 30)
    run.worker.send(b"stty size\n")
    _wait_output(qtbot, run, b"30 100")


def test_04_wrong_password(qtbot, server, make_worker) -> None:
    run = make_worker(server, password="definitely-wrong")
    with qtbot.waitSignal(run.worker.auth_failed, timeout=TIMEOUT):
        run.worker.start()
    assert run.auth_failures and run.failures == []


def test_05_exit_disconnects(qtbot, server, make_worker) -> None:
    run = make_worker(server)
    _connect(qtbot, run)
    with qtbot.waitSignal(run.worker.disconnected, timeout=TIMEOUT):
        run.worker.send(b"exit\n")
    assert run.disconnects == ["Sesi berakhir (kode keluar 0)."]


def test_06_reject_host_key(qtbot, server, make_worker) -> None:
    run = make_worker(server, decision=HostKeyDecision.REJECT)
    with qtbot.waitSignal(run.worker.failed, timeout=TIMEOUT):
        run.worker.start()
    assert run.failures[0][0] == "E_HOSTKEY_REJECTED"


def test_07_accept_save_then_no_question(qtbot, server, make_worker, tmp_path: Path) -> None:
    known_hosts = tmp_path / "saved_known_hosts"
    first = make_worker(server, decision=HostKeyDecision.ACCEPT_SAVE, known_hosts=known_hosts)
    _connect(qtbot, first)
    assert entry_name(server.host, server.port) in known_hosts.read_text()
    second = make_worker(server, decision=HostKeyDecision.REJECT, known_hosts=known_hosts)
    _connect(qtbot, second)
    assert second.host_key_questions == []


def test_08_changed_host_key(qtbot, server, make_worker, tmp_path: Path) -> None:
    pem = ed25519.Ed25519PrivateKey.generate().private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.OpenSSH,
        serialization.NoEncryption(),
    )
    fake = paramiko.Ed25519Key.from_private_key(io.StringIO(pem.decode()))
    known_hosts = tmp_path / "fake_known_hosts"
    host_keys = paramiko.HostKeys()
    host_keys.add(entry_name(server.host, server.port), fake.get_name(), fake)
    host_keys.save(str(known_hosts))
    run = make_worker(server, known_hosts=known_hosts)
    with qtbot.waitSignal(run.worker.failed, timeout=TIMEOUT):
        run.worker.start()
    assert run.failures[0][0] == "E_HOSTKEY_CHANGED"
    assert run.host_key_questions == []


def test_09_closed_port(qtbot, server, make_worker) -> None:
    run = make_worker(server, port=1)
    started = time.monotonic()
    with qtbot.waitSignal(run.worker.failed, timeout=TIMEOUT):
        run.worker.start()
    assert time.monotonic() - started <= 5
    assert run.failures[0][0] == "E_CONNECT"


def test_10_unknown_host(qtbot, server, make_worker) -> None:
    run = make_worker(server, host="nonexistent.invalid")
    with qtbot.waitSignal(run.worker.failed, timeout=TIMEOUT):
        run.worker.start()
    assert run.failures[0][0] == "E_DNS"


def test_11_stop_while_connected(qtbot, server, make_worker) -> None:
    run = make_worker(server)
    _connect(qtbot, run)
    run.worker.stop()
    assert run.worker.join(2.0) is True


def test_12_exit_status_reported_reliably(qtbot, server, make_worker, tmp_path: Path) -> None:
    """Regression: OpenSSH may send EOF before exit-status; the reason must still be exact."""
    known_hosts = tmp_path / "kh"
    for _ in range(10):
        run = make_worker(server, decision=HostKeyDecision.ACCEPT_SAVE, known_hosts=known_hosts)
        _connect(qtbot, run)
        with qtbot.waitSignal(run.worker.disconnected, timeout=TIMEOUT):
            run.worker.send(b"seq 1 500; exit 3\n")
        assert run.disconnects == ["Sesi berakhir (kode keluar 3)."]
