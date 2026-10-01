"""Data models: ``AuthType``, ``SessionConfig``, ``AppSettings`` (SPEC §6.2, §6.4)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from pyssh import strings

NAME_MAX_LEN = 64
PORT_MIN = 1
PORT_MAX = 65535


class AuthType(StrEnum):
    """Authentication method of a session."""

    PASSWORD = "password"
    KEY = "key"


def now_iso() -> str:
    """Return the current local time as ISO 8601 with offset, second precision."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _has_whitespace(text: str) -> bool:
    return any(ch.isspace() for ch in text)


@dataclass
class SessionConfig:
    """A saved SSH session. Never contains a secret (secrets live in ``SecretStore``)."""

    name: str
    host: str
    username: str
    port: int = 22
    auth_type: AuthType = AuthType.PASSWORD
    key_path: str | None = None
    remember_secret: bool = False
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: str = field(default_factory=now_iso)
    last_used_at: str | None = None

    def validate(self) -> None:
        """Raise ``ValueError`` (message from ``strings``) when a field is invalid."""
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError(strings.ERR_NAME_REQUIRED)
        if len(self.name) > NAME_MAX_LEN:
            raise ValueError(strings.ERR_NAME_TOO_LONG.format(max=NAME_MAX_LEN))
        if not isinstance(self.host, str) or not self.host:
            raise ValueError(strings.ERR_HOST_REQUIRED)
        if _has_whitespace(self.host) or "[" in self.host or "]" in self.host:
            raise ValueError(strings.ERR_HOST_INVALID)
        if (
            isinstance(self.port, bool)
            or not isinstance(self.port, int)
            or not PORT_MIN <= self.port <= PORT_MAX
        ):
            raise ValueError(strings.ERR_PORT_RANGE)
        if not isinstance(self.username, str) or not self.username:
            raise ValueError(strings.ERR_USERNAME_REQUIRED)
        if _has_whitespace(self.username):
            raise ValueError(strings.ERR_USERNAME_SPACES)
        try:
            auth = AuthType(self.auth_type)
        except ValueError:
            raise ValueError(strings.ERR_AUTH_TYPE) from None
        if auth is AuthType.KEY and not (self.key_path and self.key_path.strip()):
            raise ValueError(strings.ERR_KEY_PATH_REQUIRED)

    def target(self) -> str:
        """Return ``"user@host:port"``."""
        return f"{self.username}@{self.host}:{self.port}"


@dataclass
class AppSettings:
    """Persistent application settings stored in ``settings.json``."""

    font_family: str = ""
    font_size: int = 11
    scrollback_lines: int = 5000
    copy_on_select: bool = True
    bold_is_bright: bool = True
    confirm_on_close: bool = True
    keepalive_seconds: int = 30
    connect_timeout_seconds: int = 10
    mac_option_as_meta: bool = False
    window_geometry: str | None = None
    window_state: str | None = None
    splitter_state: str | None = None


MAC_DEFAULT_FONT_SIZE = 12


def default_settings(*, mac: bool) -> AppSettings:
    """Return default settings; macOS uses a larger default font size (SPEC §6.4)."""
    if mac:
        return AppSettings(font_size=MAC_DEFAULT_FONT_SIZE)
    return AppSettings()
