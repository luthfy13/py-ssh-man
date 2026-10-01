"""Tests for core.secret_store (SPEC §7.6, AC-2.2)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from pyssh.core.crypto import KdfParams
from pyssh.core.database import Database
from pyssh.core.secret_store import SecretStore
from pyssh.core.session_store import SessionStore
from pyssh.core.vault import Vault, VaultLocked
from pyssh.models import SessionConfig

SECRET = "Sangat-Rahasia-42"


@pytest.fixture
def env(tmp_path: Path, fast_kdf: KdfParams):
    db = Database(tmp_path / "pyssh.db")
    db.open()
    sessions = SessionStore(db)
    vault = Vault(db, fast_kdf)
    vault.initialize("master-pass-1")
    store = SecretStore(db, vault)
    a = SessionConfig(name="A", host="h", username="u")
    b = SessionConfig(name="B", host="h", username="u")
    sessions.add(a)
    sessions.add(b)
    yield db, sessions, vault, store, a, b
    db.close()


def test_set_get_has_delete(env) -> None:
    _db, sessions, _vault, store, a, _b = env
    assert store.can_store is True
    assert store.get_secret(a.id) is None
    assert store.has_secret(a.id) is False
    store.set_secret(a.id, SECRET)
    assert store.has_secret(a.id) is True
    assert store.get_secret(a.id) == SECRET
    assert sessions.get(a.id).remember_secret is True
    store.set_secret(a.id, "replaced")
    assert store.get_secret(a.id) == "replaced"
    store.delete_secret(a.id)
    store.delete_secret(a.id)  # absent: no error
    assert store.has_secret(a.id) is False
    assert store.get_secret(a.id) is None


def test_set_for_unknown_session(env) -> None:
    *_rest, store, _a, _b = env
    with pytest.raises(KeyError):
        store.set_secret("missing", SECRET)


def test_locked_behaviour(env) -> None:
    _db, _sessions, vault, store, a, _b = env
    store.set_secret(a.id, SECRET)
    vault.lock()
    assert store.can_store is False
    assert store.get_secret(a.id) is None
    with pytest.raises(VaultLocked):
        store.set_secret(a.id, SECRET)
    assert store.has_secret(a.id) is True
    store.delete_secret(a.id)
    assert store.has_secret(a.id) is False


def test_ciphertext_moved_to_other_session_is_rejected(
    env, caplog: pytest.LogCaptureFixture
) -> None:
    db, _sessions, _vault, store, a, b = env
    store.set_secret(a.id, SECRET)
    row = db.conn.execute("SELECT nonce, ciphertext FROM secrets").fetchone()
    with db.conn:
        db.conn.execute(
            "INSERT INTO secrets VALUES (?,?,?,?)", (b.id, row["nonce"], row["ciphertext"], "t")
        )
    with caplog.at_level(logging.WARNING):
        assert store.get_secret(b.id) is None
    assert b.id in caplog.text
    assert SECRET not in caplog.text


def test_raw_database_file_contains_no_plaintext(env) -> None:
    db, _sessions, _vault, store, a, b = env
    store.set_secret(a.id, SECRET)
    store.set_secret(b.id, SECRET)
    path = db.path
    db.close()
    raw = path.read_bytes()
    assert SECRET.encode("utf-8") not in raw
    assert SECRET.encode("utf-16-le") not in raw
    db.open()


def test_deleting_session_removes_secret(env) -> None:
    _db, sessions, _vault, store, a, _b = env
    store.set_secret(a.id, SECRET)
    sessions.delete(a.id)
    assert store.has_secret(a.id) is False
