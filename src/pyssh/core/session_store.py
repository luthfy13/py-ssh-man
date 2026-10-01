"""CRUD operations on the ``sessions`` table (SPEC §7.3)."""

from __future__ import annotations

import logging
import sqlite3
import uuid
from dataclasses import replace

from pyssh import strings
from pyssh.core.database import Database
from pyssh.models import NAME_MAX_LEN, AuthType, SessionConfig, now_iso

log = logging.getLogger(__name__)

_COLUMNS = (
    "id, name, name_key, host, port, username, auth_type, key_path, "
    "remember_secret, created_at, last_used_at"
)


def _name_key(name: str) -> str:
    return name.casefold()


def _row_to_session(row: sqlite3.Row) -> SessionConfig:
    session = SessionConfig(
        id=row["id"],
        name=row["name"],
        host=row["host"],
        port=row["port"],
        username=row["username"],
        auth_type=AuthType(row["auth_type"]),
        key_path=row["key_path"],
        remember_secret=bool(row["remember_secret"]),
        created_at=row["created_at"],
        last_used_at=row["last_used_at"],
    )
    session.validate()
    return session


def _params(session: SessionConfig) -> tuple[object, ...]:
    return (
        session.id,
        session.name,
        _name_key(session.name),
        session.host,
        session.port,
        session.username,
        str(AuthType(session.auth_type)),
        session.key_path,
        int(bool(session.remember_secret)),
        session.created_at,
        session.last_used_at,
    )


class SessionStore:
    """Saved sessions in SQLite. Returned objects are fresh copies."""

    def __init__(self, db: Database) -> None:
        """Use the given (already opened) database."""
        self._db = db

    def all(self) -> list[SessionConfig]:
        """All valid sessions ordered by ``name_key``; invalid rows are skipped and logged."""
        rows = self._db.conn.execute(
            f"SELECT {_COLUMNS} FROM sessions ORDER BY name_key, id"
        ).fetchall()
        result = []
        for row in rows:
            session = self._convert(row)
            if session is not None:
                result.append(session)
        return result

    def get(self, session_id: str) -> SessionConfig | None:
        """Return the session or ``None`` when it does not exist (or is invalid)."""
        row = self._db.conn.execute(
            f"SELECT {_COLUMNS} FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return None if row is None else self._convert(row)

    def add(self, session: SessionConfig) -> None:
        """Insert a session; ``ValueError`` when invalid or the name is already used."""
        session.validate()
        self._ensure_unique_name(session.name, exclude_id=None)
        try:
            with self._db.conn:
                self._db.conn.execute(
                    f"INSERT INTO sessions ({_COLUMNS}) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    _params(session),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError(strings.ERR_NAME_DUPLICATE.format(name=session.name)) from exc

    def update(self, session: SessionConfig) -> None:
        """Replace a session; ``KeyError`` when the id is unknown, ``ValueError`` when invalid."""
        if not self._exists(session.id):
            raise KeyError(session.id)
        session.validate()
        self._ensure_unique_name(session.name, exclude_id=session.id)
        params = _params(session)
        try:
            with self._db.conn:
                self._db.conn.execute(
                    "UPDATE sessions SET name=?, name_key=?, host=?, port=?, username=?, "
                    "auth_type=?, key_path=?, remember_secret=?, created_at=?, last_used_at=? "
                    "WHERE id=?",
                    (*params[1:], params[0]),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError(strings.ERR_NAME_DUPLICATE.format(name=session.name)) from exc

    def delete(self, session_id: str) -> None:
        """Delete a session; its secret is removed by ``ON DELETE CASCADE``. Unknown id is ok."""
        with self._db.conn:
            self._db.conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    def duplicate(self, session_id: str) -> SessionConfig:
        """Copy a session with a new id and name; the secret is NOT copied."""
        original = self.get(session_id)
        if original is None:
            raise KeyError(session_id)
        copy = replace(
            original,
            id=uuid.uuid4().hex,
            name=self._copy_name(original.name),
            remember_secret=False,
            created_at=now_iso(),
            last_used_at=None,
        )
        self.add(copy)
        return copy

    def touch(self, session_id: str) -> None:
        """Set ``last_used_at`` to now."""
        with self._db.conn:
            self._db.conn.execute(
                "UPDATE sessions SET last_used_at = ? WHERE id = ?", (now_iso(), session_id)
            )

    def set_remember(self, session_id: str, remember: bool) -> None:
        """Set the ``remember_secret`` flag; ``KeyError`` when the id is unknown."""
        with self._db.conn:
            cursor = self._db.conn.execute(
                "UPDATE sessions SET remember_secret = ? WHERE id = ?",
                (int(remember), session_id),
            )
        if cursor.rowcount == 0:
            raise KeyError(session_id)

    def _exists(self, session_id: str) -> bool:
        row = self._db.conn.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return row is not None

    def _name_taken(self, name: str, exclude_id: str | None) -> bool:
        row = self._db.conn.execute(
            "SELECT id FROM sessions WHERE name_key = ?", (_name_key(name),)
        ).fetchone()
        return row is not None and row["id"] != exclude_id

    def _ensure_unique_name(self, name: str, exclude_id: str | None) -> None:
        if self._name_taken(name, exclude_id):
            raise ValueError(strings.ERR_NAME_DUPLICATE.format(name=name))

    def _copy_name(self, name: str) -> str:
        counter = 1
        while True:
            suffix = (
                strings.SESSION_COPY_SUFFIX
                if counter == 1
                else strings.SESSION_COPY_SUFFIX_N.format(n=counter)
            )
            candidate = name[: NAME_MAX_LEN - len(suffix)].rstrip() + suffix
            if not self._name_taken(candidate, exclude_id=None):
                return candidate
            counter += 1

    @staticmethod
    def _convert(row: sqlite3.Row) -> SessionConfig | None:
        try:
            return _row_to_session(row)
        except (ValueError, TypeError) as exc:
            log.warning("skipping invalid session row id=%s: %s", row["id"], exc)
            return None
