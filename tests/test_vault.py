"""Tests for core.vault (SPEC §6.5, §7.5, AC-2.4)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from pyssh.core.crypto import DecryptError, KdfParams
from pyssh.core.database import Database
from pyssh.core.session_store import SessionStore
from pyssh.core.vault import Vault, VaultLocked, VaultState
from pyssh.logging_setup import setup_logging, shutdown_logging
from pyssh.models import SessionConfig

MASTER = "master-pass-1"


@pytest.fixture
def db(tmp_path: Path):
    database = Database(tmp_path / "pyssh.db")
    database.open()
    yield database
    database.close()


def _vault_row(db: Database):
    return db.conn.execute("SELECT * FROM vault").fetchone()


def test_initial_state(db: Database, fast_kdf: KdfParams) -> None:
    vault = Vault(db, fast_kdf)
    assert vault.state is VaultState.UNINITIALIZED
    vault.initialize(MASTER)
    assert vault.state is VaultState.UNLOCKED
    assert Vault(db, fast_kdf).state is VaultState.LOCKED
    assert "UNLOCKED" not in repr(vault) and "unlocked" in repr(vault)


def test_initialize_validation(db: Database, fast_kdf: KdfParams) -> None:
    vault = Vault(db, fast_kdf)
    with pytest.raises(ValueError):
        vault.initialize("1234567")
    assert vault.state is VaultState.UNINITIALIZED
    vault.initialize("12345678")
    with pytest.raises(ValueError):
        vault.initialize("another-password")


def test_initialize_stores_wrapped_dek_only(db: Database, fast_kdf: KdfParams) -> None:
    Vault(db, fast_kdf).initialize(MASTER)
    row = _vault_row(db)
    assert row["kdf"] == "scrypt"
    assert (row["kdf_n"], row["kdf_r"], row["kdf_p"]) == (2**10, 8, 1)
    assert len(row["kdf_salt"]) == 16
    assert len(row["dek_nonce"]) == 12
    assert len(row["dek_wrapped"]) == 32 + 16


def test_unlock_right_and_wrong(db: Database, fast_kdf: KdfParams) -> None:
    Vault(db, fast_kdf).initialize(MASTER)
    vault = Vault(db, fast_kdf)
    assert vault.unlock("wrong-password") is False
    assert vault.state is VaultState.LOCKED
    assert vault.unlock(MASTER) is True
    assert vault.state is VaultState.UNLOCKED


def test_unlock_uninitialized_returns_false(db: Database, fast_kdf: KdfParams) -> None:
    vault = Vault(db, fast_kdf)
    assert vault.unlock(MASTER) is False
    assert vault.state is VaultState.UNINITIALIZED


def test_lock_forgets_dek(db: Database, fast_kdf: KdfParams) -> None:
    vault = Vault(db, fast_kdf)
    vault.initialize(MASTER)
    vault.lock()
    assert vault.state is VaultState.LOCKED
    with pytest.raises(VaultLocked):
        vault.encrypt_secret("s", "x")
    with pytest.raises(VaultLocked):
        vault.decrypt_secret("s", b"n" * 12, b"c" * 20)


def test_lock_when_uninitialized_keeps_state(db: Database, fast_kdf: KdfParams) -> None:
    vault = Vault(db, fast_kdf)
    vault.lock()
    assert vault.state is VaultState.UNINITIALIZED


def test_secret_round_trip_and_aad(db: Database, fast_kdf: KdfParams) -> None:
    vault = Vault(db, fast_kdf)
    vault.initialize(MASTER)
    nonce, ciphertext = vault.encrypt_secret("session-a", "p@ssw0rd é")
    assert vault.decrypt_secret("session-a", nonce, ciphertext) == "p@ssw0rd é"
    with pytest.raises(DecryptError):
        vault.decrypt_secret("session-b", nonce, ciphertext)


def test_change_master_password(db: Database, fast_kdf: KdfParams) -> None:
    vault = Vault(db, fast_kdf)
    vault.initialize(MASTER)
    nonce, ciphertext = vault.encrypt_secret("s1", "secret-1")
    old_row = _vault_row(db)
    assert vault.change_master_password("wrong-password", "new-master-2") is False
    assert vault.change_master_password(MASTER, "new-master-2") is True
    new_row = _vault_row(db)
    assert new_row["kdf_salt"] != old_row["kdf_salt"]
    assert new_row["dek_wrapped"] != old_row["dek_wrapped"]
    with pytest.raises(ValueError):
        vault.change_master_password("new-master-2", "short")

    reopened = Vault(db, fast_kdf)
    assert reopened.unlock(MASTER) is False
    assert reopened.unlock("new-master-2") is True
    assert reopened.decrypt_secret("s1", nonce, ciphertext) == "secret-1"


def test_change_when_locked_unlocks(db: Database, fast_kdf: KdfParams) -> None:
    Vault(db, fast_kdf).initialize(MASTER)
    vault = Vault(db, fast_kdf)
    assert vault.change_master_password(MASTER, "new-master-2") is True
    assert vault.state is VaultState.UNLOCKED


def test_change_upgrades_kdf_to_instance_default(db: Database, fast_kdf: KdfParams) -> None:
    Vault(db, fast_kdf).initialize(MASTER)
    stronger = KdfParams(n=2**11, r=8, p=1)
    vault = Vault(db, stronger)
    assert vault.change_master_password(MASTER, "new-master-2") is True
    assert _vault_row(db)["kdf_n"] == 2**11


def test_unlock_uses_stored_kdf_params(db: Database, fast_kdf: KdfParams) -> None:
    Vault(db, fast_kdf).initialize(MASTER)
    other_default = KdfParams(n=2**12, r=8, p=1)
    vault = Vault(db, other_default)
    assert vault.unlock(MASTER) is True


def test_reset(db: Database, fast_kdf: KdfParams) -> None:
    sessions = SessionStore(db)
    session = SessionConfig(name="Web", host="h", username="u", remember_secret=True)
    sessions.add(session)
    vault = Vault(db, fast_kdf)
    vault.initialize(MASTER)
    nonce, ciphertext = vault.encrypt_secret(session.id, "x")
    with db.conn:
        db.conn.execute(
            "INSERT INTO secrets VALUES (?,?,?,?)", (session.id, nonce, ciphertext, "t")
        )
    vault.reset()
    assert vault.state is VaultState.UNINITIALIZED
    assert db.conn.execute("SELECT count(*) FROM secrets").fetchone()[0] == 0
    assert db.conn.execute("SELECT count(*) FROM vault").fetchone()[0] == 0
    assert sessions.get(session.id).remember_secret is False
    assert sessions.all() == [sessions.get(session.id)]
    vault.initialize("brand-new-pass")
    assert vault.state is VaultState.UNLOCKED


def test_listeners_receive_state_changes(db: Database, fast_kdf: KdfParams) -> None:
    vault = Vault(db, fast_kdf)
    seen: list[VaultState] = []
    vault.add_listener(seen.append)
    vault.initialize(MASTER)
    vault.lock()
    vault.unlock(MASTER)
    vault.reset()
    assert seen == [
        VaultState.UNLOCKED,
        VaultState.LOCKED,
        VaultState.UNLOCKED,
        VaultState.UNINITIALIZED,
    ]


def test_log_contains_no_secrets(db: Database, fast_kdf: KdfParams, pyssh_home: Path) -> None:
    """AC-2.4: master passwords, secrets and keys never reach the log file."""
    from pyssh import config

    paths = config.get_paths()
    config.ensure_dirs(paths)
    setup_logging(paths, debug=True)
    try:
        vault = Vault(db, fast_kdf)
        vault.initialize("Master-Unik-777")
        dek = vault._dek
        nonce, ciphertext = vault.encrypt_secret("s", "Secret-Unik-888")
        vault.lock()
        vault.unlock("Salah-Unik-999")
        vault.unlock("Master-Unik-777")
        vault.change_master_password("Master-Unik-777", "Baru-Unik-000")
        logging.getLogger("pyssh").info("done")
    finally:
        shutdown_logging()
    text = paths.log_file.read_text(encoding="utf-8")
    assert "vault initialized" in text
    assert "vault unlocked unlock_ms=" in text
    assert "vault unlock failed" in text
    for forbidden in ("Master-Unik-777", "Secret-Unik-888", "Salah-Unik-999", "Baru-Unik-000"):
        assert forbidden not in text
    raw = paths.log_file.read_bytes()
    for blob in (dek, nonce, ciphertext):
        assert blob.hex() not in text
        assert blob not in raw
