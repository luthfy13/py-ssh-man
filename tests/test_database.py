"""Tests for core.database: schema, PRAGMAs, corrupt files and newer versions (SPEC §6.3)."""

from __future__ import annotations

import hashlib
import sqlite3
import stat
from pathlib import Path

import pytest

from pyssh import config
from pyssh.core.database import SCHEMA_VERSION, Database, DatabaseVersionError

# (name, type, notnull, pk) per column, from SPEC §6.3.
EXPECTED_SCHEMA = {
    "sessions": [
        ("id", "TEXT", 0, 1),
        ("name", "TEXT", 1, 0),
        ("name_key", "TEXT", 1, 0),
        ("host", "TEXT", 1, 0),
        ("port", "INTEGER", 1, 0),
        ("username", "TEXT", 1, 0),
        ("auth_type", "TEXT", 1, 0),
        ("key_path", "TEXT", 0, 0),
        ("remember_secret", "INTEGER", 1, 0),
        ("created_at", "TEXT", 1, 0),
        ("last_used_at", "TEXT", 0, 0),
    ],
    "vault": [
        ("id", "INTEGER", 0, 1),
        ("kdf", "TEXT", 1, 0),
        ("kdf_salt", "BLOB", 1, 0),
        ("kdf_n", "INTEGER", 1, 0),
        ("kdf_r", "INTEGER", 1, 0),
        ("kdf_p", "INTEGER", 1, 0),
        ("dek_nonce", "BLOB", 1, 0),
        ("dek_wrapped", "BLOB", 1, 0),
        ("created_at", "TEXT", 1, 0),
        ("updated_at", "TEXT", 1, 0),
    ],
    "secrets": [
        ("session_id", "TEXT", 0, 1),
        ("nonce", "BLOB", 1, 0),
        ("ciphertext", "BLOB", 1, 0),
        ("updated_at", "TEXT", 1, 0),
    ],
}


@pytest.fixture
def db(tmp_path: Path):
    database = Database(tmp_path / "pyssh.db")
    assert database.open() is None
    yield database
    database.close()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_schema_matches_spec(db: Database) -> None:
    tables = {
        row[0]
        for row in db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    assert tables == set(EXPECTED_SCHEMA)
    for table, expected in EXPECTED_SCHEMA.items():
        info = db.conn.execute(f"PRAGMA table_info({table})").fetchall()
        actual = [(r["name"], r["type"], r["notnull"], r["pk"]) for r in info]
        assert actual == expected, table


def test_unique_name_key_and_cascade(db: Database) -> None:
    indexes = db.conn.execute("PRAGMA index_list(sessions)").fetchall()
    unique_cols = set()
    for idx in indexes:
        if idx["unique"]:
            cols = db.conn.execute(f"PRAGMA index_info({idx['name']})").fetchall()
            unique_cols.update(c["name"] for c in cols)
    assert "name_key" in unique_cols
    fks = db.conn.execute("PRAGMA foreign_key_list(secrets)").fetchall()
    assert [(f["table"], f["from"], f["to"], f["on_delete"]) for f in fks] == [
        ("sessions", "session_id", "id", "CASCADE")
    ]


def test_check_constraints(db: Database) -> None:
    base = "INSERT INTO sessions (id,name,name_key,host,port,username,auth_type,created_at)"
    with pytest.raises(sqlite3.IntegrityError):
        db.conn.execute(base + " VALUES ('a','n','n','h',0,'u','password','t')")
    with pytest.raises(sqlite3.IntegrityError):
        db.conn.execute(base + " VALUES ('a','n','n','h',22,'u','telnet','t')")
    db.conn.rollback()


def test_user_version_and_pragmas(db: Database) -> None:
    assert db.conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 1
    assert db.conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert db.conn.execute("PRAGMA secure_delete").fetchone()[0] == 1


def test_reopen_keeps_data(tmp_path: Path) -> None:
    first = Database(tmp_path / "x.db")
    first.open()
    with first.conn:
        first.conn.execute(
            "INSERT INTO sessions (id,name,name_key,host,port,username,auth_type,created_at)"
            " VALUES ('a','n','n','h',22,'u','password','t')"
        )
    first.close()
    second = Database(tmp_path / "x.db")
    assert second.open() is None
    assert second.conn.execute("SELECT count(*) FROM sessions").fetchone()[0] == 1
    second.close()


def test_garbage_file_is_moved_aside(tmp_path: Path) -> None:
    path = tmp_path / "pyssh.db"
    path.write_bytes(b"not a database at all " * 50)
    original = path.read_bytes()
    database = Database(path)
    warning = database.open()
    assert warning is not None
    backups = list(tmp_path.glob("pyssh.db.corrupt-*"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == original
    assert str(backups[0]) in warning
    # The new database is usable.
    assert database.conn.execute("PRAGMA user_version").fetchone()[0] == 1
    assert database.conn.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0
    database.close()


def test_two_corrupt_backups_in_same_second(tmp_path: Path) -> None:
    path = tmp_path / "pyssh.db"
    for _ in range(2):
        path.write_bytes(b"garbage" * 200)
        database = Database(path)
        assert database.open() is not None
        database.close()
    assert len(list(tmp_path.glob("pyssh.db.corrupt-*"))) == 2


def test_newer_version_raises_without_modifying_file(tmp_path: Path) -> None:
    path = tmp_path / "pyssh.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE future (x)")
    conn.execute("PRAGMA user_version = 99")
    conn.commit()
    conn.close()
    before = _sha256(path)
    database = Database(path)
    with pytest.raises(DatabaseVersionError) as info:
        database.open()
    assert info.value.found == 99
    assert info.value.path == path
    assert _sha256(path) == before
    assert list(tmp_path.glob("*.corrupt-*")) == []
    with pytest.raises(RuntimeError):
        _ = database.conn


def test_conn_before_open_raises(tmp_path: Path) -> None:
    database = Database(tmp_path / "x.db")
    assert database.path == tmp_path / "x.db"
    with pytest.raises(RuntimeError):
        _ = database.conn
    database.close()  # safe when not open


@pytest.mark.skipif(config.IS_WINDOWS, reason="POSIX permissions")
def test_new_file_permissions(tmp_path: Path) -> None:
    database = Database(tmp_path / "p.db")
    database.open()
    database.close()
    assert stat.S_IMODE((tmp_path / "p.db").stat().st_mode) == 0o600
