"""Tests for core.errors.describe_error (SPEC §7.10): every row and the priority order."""

from __future__ import annotations

import socket

import paramiko
import pytest
from paramiko.ssh_exception import NoValidConnectionsError

from pyssh import strings
from pyssh.core.errors import DETAIL_MAX, HostKeyRejected, UserError, describe_error

CTX = {"host": "srv", "port": 2222, "username": "admin", "timeout": 10}


class _StubKey:
    def get_base64(self) -> str:
        return "AAAA"

    def get_name(self) -> str:
        return "ssh-ed25519"


def _code(exc: BaseException) -> str:
    return describe_error(exc, **CTX).code


@pytest.mark.parametrize(
    ("exc", "code"),
    [
        (HostKeyRejected(), "E_HOSTKEY_REJECTED"),
        (paramiko.BadHostKeyException("srv", _StubKey(), _StubKey()), "E_HOSTKEY_CHANGED"),
        (paramiko.AuthenticationException("bad"), "E_AUTH"),
        (paramiko.BadAuthenticationType("bad", ["publickey"]), "E_AUTH"),
        (paramiko.PasswordRequiredException("locked key"), "E_AUTH"),
        (NoValidConnectionsError({("127.0.0.1", 2222): ConnectionRefusedError()}), "E_CONNECT"),
        (socket.gaierror(-2, "Name or service not known"), "E_DNS"),
        (ConnectionRefusedError(111, "refused"), "E_CONNECT"),
        (TimeoutError("timed out"), "E_TIMEOUT"),
        (paramiko.SSHException("Error reading SSH protocol banner"), "E_BANNER"),
        (paramiko.SSHException("Incompatible ssh peer"), "E_SSH"),
        (EOFError(), "E_EOF"),
        (OSError(113, "No route to host"), "E_NETWORK"),
        (ValueError("boom"), "E_UNKNOWN"),
        (RuntimeError("boom"), "E_UNKNOWN"),
    ],
)
def test_every_row(exc: BaseException, code: str) -> None:
    assert _code(exc) == code


def test_priority_specific_before_general() -> None:
    # BadHostKeyException is an SSHException; NoValidConnectionsError and gaierror are OSErrors.
    assert issubclass(paramiko.BadHostKeyException, paramiko.SSHException)
    assert issubclass(NoValidConnectionsError, OSError)
    assert issubclass(socket.gaierror, OSError)
    assert issubclass(paramiko.AuthenticationException, paramiko.SSHException)
    assert getattr(socket, "timeout") is TimeoutError  # noqa: B009 - alias since Python 3.10
    assert _code(paramiko.BadHostKeyException("srv", _StubKey(), _StubKey())) != "E_SSH"
    assert _code(NoValidConnectionsError({("h", 1): OSError()})) == "E_CONNECT"


def test_messages() -> None:
    assert describe_error(HostKeyRejected(), **CTX) == UserError(
        "E_HOSTKEY_REJECTED", strings.E_HOSTKEY_REJECTED
    )
    assert describe_error(TimeoutError(), **CTX).message == (
        "Tidak ada respons dari srv:2222 dalam 10 detik."
    )
    assert describe_error(paramiko.AuthenticationException(), **CTX).message == (
        "Autentikasi gagal untuk admin@srv."
    )
    assert describe_error(socket.gaierror(), **CTX).message == (
        'Host "srv" tidak ditemukan. Periksa nama host atau DNS.'
    )
    assert (
        "srv:2222"
        in describe_error(
            paramiko.BadHostKeyException("srv", _StubKey(), _StubKey()), **CTX
        ).message
    )
    assert describe_error(KeyError("x"), **CTX).message == (
        "Kesalahan tak terduga (KeyError). Lihat log untuk detail."
    )


def test_detail_is_truncated() -> None:
    message = describe_error(paramiko.SSHException("x" * 500), **CTX).message
    assert message == strings.E_SSH.format(detail="x" * DETAIL_MAX)
    network = describe_error(OSError("y" * 500), **CTX).message
    assert network == strings.E_NETWORK.format(detail="y" * DETAIL_MAX)
