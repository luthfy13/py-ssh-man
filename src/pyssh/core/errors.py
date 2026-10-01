"""Map exceptions to user-facing error codes and messages (SPEC §7.10)."""

from __future__ import annotations

import socket
from dataclasses import dataclass

import paramiko
from paramiko.ssh_exception import NoValidConnectionsError

from pyssh import strings

DETAIL_MAX = 200


@dataclass(frozen=True)
class UserError:
    """Error code plus a message safe to show to the user."""

    code: str
    message: str


class HostKeyRejected(Exception):
    """The user rejected an unknown host key."""


def _detail(exc: BaseException) -> str:
    return str(exc)[:DETAIL_MAX]


def describe_error(
    exc: BaseException, *, host: str, port: int, username: str, timeout: int
) -> UserError:
    """Translate an exception, checking the most specific classes first (SPEC §7.10)."""
    if isinstance(exc, HostKeyRejected):
        return UserError("E_HOSTKEY_REJECTED", strings.E_HOSTKEY_REJECTED)
    if isinstance(exc, paramiko.BadHostKeyException):
        return UserError(
            "E_HOSTKEY_CHANGED", strings.E_HOSTKEY_CHANGED.format(host=host, port=port)
        )
    if isinstance(exc, paramiko.AuthenticationException):
        return UserError("E_AUTH", strings.E_AUTH.format(username=username, host=host))
    if isinstance(exc, NoValidConnectionsError):
        return UserError("E_CONNECT", strings.E_CONNECT.format(host=host, port=port))
    if isinstance(exc, socket.gaierror):
        return UserError("E_DNS", strings.E_DNS.format(host=host))
    if isinstance(exc, ConnectionRefusedError):
        return UserError("E_CONNECT", strings.E_CONNECT.format(host=host, port=port))
    if isinstance(exc, TimeoutError):  # socket.timeout is an alias since Python 3.10
        return UserError(
            "E_TIMEOUT", strings.E_TIMEOUT.format(host=host, port=port, timeout=timeout)
        )
    if isinstance(exc, paramiko.SSHException):
        if "protocol banner" in str(exc).lower():
            return UserError("E_BANNER", strings.E_BANNER.format(host=host, port=port))
        return UserError("E_SSH", strings.E_SSH.format(detail=_detail(exc)))
    if isinstance(exc, EOFError):
        return UserError("E_EOF", strings.E_EOF)
    if isinstance(exc, OSError):
        return UserError("E_NETWORK", strings.E_NETWORK.format(detail=_detail(exc)))
    return UserError("E_UNKNOWN", strings.E_UNKNOWN.format(name=type(exc).__name__))
