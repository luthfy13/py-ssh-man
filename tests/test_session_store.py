"""Tests for core.session_store (SPEC §7.3)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from pyssh import strings
from pyssh.core.database import Database
from pyssh.core.session_store import SessionStore
from pyssh.models import AuthType, SessionConfig


@pytest.fixture
def db(tmp_path: Path):
    database = Database(tmp_path / "pyssh.db")
    database.open()
    yield database
    database.close()


@pytest.fixture
def store(db: Database) -> SessionStore:
    return SessionStore(db)


def _session(name: str = "Web", **kwargs: object) -> SessionConfig:
    return SessionConfig(name=name, host="10.0.0.5", username="admin", **kwargs)


def test_add_get_all(store: SessionStore) -> None:
    s = _session(port=2222, auth_type=AuthType.KEY, key_path="/k", remember_secret=True)
    store.add(s)
    assert store.get(s.id) == s
    assert store.all() == [s]
    assert store.get("missing") is None


def test_returned_objects_are_copies(store: SessionStore) -> None:
    s = _session()
    store.add(s)
    got = store.get(s.id)
    got.name = "Changed"
    assert store.get(s.id).name == "Web"


def test_all_sorted_by_name_case_insensitive(store: SessionStore) -> None:
    for name in ("charlie", "Bravo", "alpha"):
        store.add(_session(name))
    assert [s.name for s in store.all()] == ["alpha", "Bravo", "charlie"]


def test_unique_name_case_insensitive(store: SessionStore) -> None:
    store.add(_session("Web"))
    with pytest.raises(ValueError) as info:
        store.add(_session("WEB"))
    assert str(info.value) == strings.ERR_NAME_DUPLICATE.format(name="WEB")


def test_add_invalid_raises(store: SessionStore) -> None:
    with pytest.raises(ValueError):
        store.add(_session(""))
    assert store.all() == []


def test_add_duplicate_id_raises_value_error(store: SessionStore) -> None:
    s = _session("A")
    store.add(s)
    with pytest.raises(ValueError):
        store.add(_session("B", id=s.id))


def test_update(store: SessionStore) -> None:
    a, b = _session("A"), _session("B")
    store.add(a)
    store.add(b)
    a.host = "example.org"
    a.name = "a"  # rename to itself with different case is allowed
    store.update(a)
    assert store.get(a.id).host == "example.org"
    assert store.get(a.id).name == "a"
    a.name = "b"
    with pytest.raises(ValueError):
        store.update(a)
    with pytest.raises(KeyError):
        store.update(_session("New"))
    a.name = "A"
    a.port = 0
    with pytest.raises(ValueError):
        store.update(a)


def test_delete(store: SessionStore, db: Database) -> None:
    s = _session()
    store.add(s)
    with db.conn:
        db.conn.execute(
            "INSERT INTO secrets (session_id, nonce, ciphertext, updated_at) VALUES (?,?,?,?)",
            (s.id, b"n" * 12, b"c" * 20, "t"),
        )
    store.delete(s.id)
    store.delete("missing")  # no error
    assert store.all() == []
    assert db.conn.execute("SELECT count(*) FROM secrets").fetchone()[0] == 0


def test_duplicate(store: SessionStore, db: Database) -> None:
    s = _session("Web", remember_secret=True)
    store.add(s)
    with db.conn:
        db.conn.execute(
            "INSERT INTO secrets (session_id, nonce, ciphertext, updated_at) VALUES (?,?,?,?)",
            (s.id, b"n" * 12, b"c" * 20, "t"),
        )
    first = store.duplicate(s.id)
    second = store.duplicate(s.id)
    assert first.name == "Web (salinan)"
    assert second.name == "Web (salinan 2)"
    assert first.id != s.id
    assert first.remember_secret is False
    assert first.last_used_at is None
    assert (first.host, first.port, first.username) == (s.host, s.port, s.username)
    rows = db.conn.execute("SELECT session_id FROM secrets").fetchall()
    assert [r[0] for r in rows] == [s.id]
    with pytest.raises(KeyError):
        store.duplicate("missing")


def test_duplicate_long_name_stays_within_limit(store: SessionStore) -> None:
    s = _session("x" * 64)
    store.add(s)
    copy = store.duplicate(s.id)
    assert len(copy.name) <= 64
    assert copy.name.endswith(" (salinan)")


def test_touch_and_set_remember(store: SessionStore) -> None:
    s = _session()
    store.add(s)
    store.touch(s.id)
    assert store.get(s.id).last_used_at is not None
    store.set_remember(s.id, True)
    assert store.get(s.id).remember_secret is True
    store.set_remember(s.id, False)
    assert store.get(s.id).remember_secret is False
    with pytest.raises(KeyError):
        store.set_remember("missing", True)


def test_persists_across_database_instances(tmp_path: Path) -> None:
    path = tmp_path / "p.db"
    db1 = Database(path)
    db1.open()
    s = _session()
    SessionStore(db1).add(s)
    db1.close()
    db2 = Database(path)
    db2.open()
    assert SessionStore(db2).all() == [s]
    db2.close()


def test_invalid_row_is_skipped_and_logged(
    store: SessionStore, db: Database, caplog: pytest.LogCaptureFixture
) -> None:
    store.add(_session("Good"))
    with db.conn:
        db.conn.execute(
            "INSERT INTO sessions (id,name,name_key,host,port,username,auth_type,created_at)"
            " VALUES ('bad','Bad','bad','h h',22,'u','password','t')"
        )
    with caplog.at_level(logging.WARNING):
        names = [s.name for s in store.all()]
        assert store.get("bad") is None
    assert names == ["Good"]
    assert "bad" in caplog.text
