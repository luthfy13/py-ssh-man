"""SQLite connection, PRAGMA setup, schema creation and versioning (SPEC §6.3, §7.2)."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from pyssh import config, strings

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1

_SCHEMA_V1 = """
CREATE TABLE sessions (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    name_key        TEXT NOT NULL UNIQUE,
    host            TEXT NOT NULL,
    port            INTEGER NOT NULL CHECK (port BETWEEN 1 AND 65535),
    username        TEXT NOT NULL,
    auth_type       TEXT NOT NULL CHECK (auth_type IN ('password', 'key')),
    key_path        TEXT,
    remember_secret INTEGER NOT NULL DEFAULT 0 CHECK (remember_secret IN (0, 1)),
    created_at      TEXT NOT NULL,
    last_used_at    TEXT
);

CREATE TABLE vault (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    kdf         TEXT    NOT NULL,
    kdf_salt    BLOB    NOT NULL,
    kdf_n       INTEGER NOT NULL,
    kdf_r       INTEGER NOT NULL,
    kdf_p       INTEGER NOT NULL,
    dek_nonce   BLOB    NOT NULL,
    dek_wrapped BLOB    NOT NULL,
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);

CREATE TABLE secrets (
    session_id  TEXT PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
    nonce       BLOB NOT NULL,
    ciphertext  BLOB NOT NULL,
    updated_at  TEXT NOT NULL
);
"""


class DatabaseVersionError(Exception):
    """The database was created by a newer PySSH (``user_version`` > ``SCHEMA_VERSION``)."""

    def __init__(self, path: Path, found: int) -> None:
        """Store the offending path and schema version."""
        super().__init__(f"schema version {found} > supported {SCHEMA_VERSION}: {path}")
        self.path = path
        self.found = found


class _CorruptDatabase(Exception):
    """Internal: the file cannot be used as a database."""


class Database:
    """Owns the single SQLite connection of the application (GUI thread only, rule A2)."""

    def __init__(self, path: Path) -> None:
        """Remember the database path; nothing is opened yet."""
        self._path = path
        self._conn: sqlite3.Connection | None = None

    @property
    def path(self) -> Path:
        """Path of the database file."""
        return self._path

    def open(self) -> str | None:
        """Open or create the database.

        Returns a warning message when a corrupt file was moved aside, otherwise ``None``.
        Raises ``DatabaseVersionError`` without modifying the file when it is too new.
        """
        existed = self._path.exists()
        try:
            self._conn = self._connect_and_check()
        except _CorruptDatabase:
            backup = self._move_aside()
            log.warning("corrupt database moved to %s", backup.name)
            self._conn = self._connect_and_check()
            self._create_or_migrate()
            config.restrict_file(self._path)
            return strings.DB_CORRUPT_WARNING.format(backup=backup)
        self._create_or_migrate()
        if not existed:
            config.restrict_file(self._path)
        return None

    @property
    def conn(self) -> sqlite3.Connection:
        """The open connection; raises ``RuntimeError`` when not open."""
        if self._conn is None:
            raise RuntimeError("database is not open")
        return self._conn

    def close(self) -> None:
        """Close the connection (safe to call more than once)."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _connect_and_check(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=5)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA secure_delete = ON")
            result = conn.execute("PRAGMA quick_check").fetchone()
            if result is None or result[0] != "ok":
                raise _CorruptDatabase
            version = conn.execute("PRAGMA user_version").fetchone()[0]
        except sqlite3.DatabaseError as exc:
            conn.close()
            raise _CorruptDatabase from exc
        except _CorruptDatabase:
            conn.close()
            raise
        if version > SCHEMA_VERSION:
            conn.close()
            raise DatabaseVersionError(self._path, version)
        return conn

    def _create_or_migrate(self) -> None:
        conn = self.conn
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version == 0:
            conn.executescript(
                f"BEGIN;\n{_SCHEMA_V1}\nPRAGMA user_version = {SCHEMA_VERSION};\nCOMMIT;"
            )
            log.info("database schema created (version %d)", SCHEMA_VERSION)
        # Future schema changes: add _migrate_1_to_2() etc. and run them here in order.

    def _move_aside(self) -> Path:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = self._path.with_name(f"{self._path.name}.corrupt-{stamp}")
        counter = 1
        while backup.exists():
            counter += 1
            backup = self._path.with_name(f"{self._path.name}.corrupt-{stamp}-{counter}")
        self._path.replace(backup)
        return backup
