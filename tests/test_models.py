"""Tests for models: validation, ``target()`` and default settings."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest

from pyssh import strings
from pyssh.models import AppSettings, AuthType, SessionConfig, default_settings, now_iso


def _valid(**kwargs: object) -> SessionConfig:
    base = SessionConfig(name="Web", host="10.0.0.5", username="admin")
    return replace(base, **kwargs)


def test_valid_session_passes() -> None:
    _valid().validate()
    _valid(host="::1", port=65535).validate()
    _valid(auth_type=AuthType.KEY, key_path="~/.ssh/id_ed25519").validate()
    _valid(name="x" * 64).validate()


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"name": ""}, strings.ERR_NAME_REQUIRED),
        ({"name": "   "}, strings.ERR_NAME_REQUIRED),
        ({"name": "x" * 65}, strings.ERR_NAME_TOO_LONG.format(max=64)),
        ({"host": ""}, strings.ERR_HOST_REQUIRED),
        ({"host": "a b"}, strings.ERR_HOST_INVALID),
        ({"host": "[::1]"}, strings.ERR_HOST_INVALID),
        ({"port": 0}, strings.ERR_PORT_RANGE),
        ({"port": 65536}, strings.ERR_PORT_RANGE),
        ({"port": True}, strings.ERR_PORT_RANGE),
        ({"port": "22"}, strings.ERR_PORT_RANGE),
        ({"username": ""}, strings.ERR_USERNAME_REQUIRED),
        ({"username": "a b"}, strings.ERR_USERNAME_SPACES),
        ({"auth_type": "telnet"}, strings.ERR_AUTH_TYPE),
        ({"auth_type": AuthType.KEY, "key_path": None}, strings.ERR_KEY_PATH_REQUIRED),
        ({"auth_type": AuthType.KEY, "key_path": "  "}, strings.ERR_KEY_PATH_REQUIRED),
    ],
)
def test_invalid_session(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError) as info:
        _valid(**kwargs).validate()
    assert str(info.value) == message


def test_target() -> None:
    assert _valid(port=2222).target() == "admin@10.0.0.5:2222"


def test_defaults_and_unique_ids() -> None:
    a, b = _valid(), _valid()
    assert a.port == 22
    assert a.auth_type is AuthType.PASSWORD
    assert a.remember_secret is False
    assert a.last_used_at is None
    assert len(a.id) == 32
    assert a.id != b.id


def test_auth_type_values() -> None:
    assert AuthType("password") is AuthType.PASSWORD
    assert str(AuthType.KEY) == "key"


def test_now_iso_has_offset() -> None:
    parsed = datetime.fromisoformat(now_iso())
    assert parsed.tzinfo is not None
    assert parsed.microsecond == 0


def test_session_has_no_secret_field() -> None:
    names = set(SessionConfig.__dataclass_fields__)
    assert not names & {"password", "passphrase", "secret"}


def test_default_settings() -> None:
    assert default_settings(mac=False) == AppSettings()
    assert AppSettings().font_size == 11
    assert default_settings(mac=True).font_size == 12
    assert AppSettings().font_family == ""
