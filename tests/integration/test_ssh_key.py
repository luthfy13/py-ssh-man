"""Integration tests: private key login (SPEC §10.2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization as ser
from cryptography.hazmat.primitives.asymmetric import ed25519

from pyssh.core.key_loader import PassphraseRequired, load_private_key

TIMEOUT = 15_000


def _require(path: Path) -> None:
    if not path.is_file():
        pytest.skip(f"test key {path} missing (see SPEC §10.3)")


def test_login_with_ed25519_key(qtbot, server, make_worker) -> None:
    _require(server.key)
    pkey = load_private_key(str(server.key))
    run = make_worker(server, password=None, pkey=pkey)
    with qtbot.waitSignal(run.worker.connected, timeout=TIMEOUT):
        run.worker.start()
    run.worker.send(b"echo key-$((6*7))\n")
    qtbot.waitUntil(lambda: b"key-42" in run.output, timeout=TIMEOUT)


def test_login_with_passphrase_key(qtbot, server, make_worker) -> None:
    _require(server.key_pass)
    with pytest.raises(PassphraseRequired):
        load_private_key(str(server.key_pass))
    pkey = load_private_key(str(server.key_pass), server.key_passphrase)
    run = make_worker(server, password=None, pkey=pkey)
    with qtbot.waitSignal(run.worker.connected, timeout=TIMEOUT):
        run.worker.start()


def test_unregistered_key_is_rejected(qtbot, server, make_worker, tmp_path: Path) -> None:
    path = tmp_path / "stranger"
    path.write_bytes(
        ed25519.Ed25519PrivateKey.generate().private_bytes(
            ser.Encoding.PEM, ser.PrivateFormat.OpenSSH, ser.NoEncryption()
        )
    )
    run = make_worker(server, password=None, pkey=load_private_key(str(path)))
    with qtbot.waitSignal(run.worker.auth_failed, timeout=TIMEOUT):
        run.worker.start()
    assert run.failures == []
