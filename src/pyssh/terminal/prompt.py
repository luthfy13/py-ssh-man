"""Recognise a shell prompt in one screen line, so it can be colored when drawn.

Pure text logic with no Qt imports (rule A6). ``find_prompt`` is called for every visible
line on every paint, so the patterns are compiled once at module level and a line that
cannot be a prompt is rejected as early as possible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

ROLE_USERHOST = "userhost"
ROLE_PATH = "path"

# An optional environment prefix such as "(venv) " or "(base) ".
_ENV = r"(?:\(\S+\) )?"
_USER = r"[A-Za-z_][A-Za-z0-9_.-]*"
_HOST = r"[A-Za-z0-9][A-Za-z0-9.-]*"
_USERHOST = rf"(?P<{ROLE_USERHOST}>{_USER}@{_HOST})"
_PATH = rf"(?P<{ROLE_PATH}>\S+)"
# The prompt character must be followed by a space or the end of the line.
_END = r"(?= |\Z)"

# Debian/Ubuntu/Proxmox: ``user@host:path$ `` or ``#``.
_DEBIAN = re.compile(rf"{_ENV}{_USERHOST}:{_PATH}[$#]{_END}")
# RHEL/Fedora/CentOS: ``[user@host path]$ `` or ``#``.
_RHEL = re.compile(rf"{_ENV}\[{_USERHOST} {_PATH}\][$#]{_END}")
# zsh (macOS default): ``user@host path % ``.
_ZSH = re.compile(rf"{_ENV}{_USERHOST} {_PATH} %{_END}")
_PATTERNS = (_DEBIAN, _RHEL, _ZSH)


@dataclass(frozen=True)
class PromptSpan:
    """A colorable part of a prompt, in screen columns."""

    start: int  # first column (inclusive)
    end: int  # last column (exclusive)
    role: str  # ``ROLE_USERHOST`` ("userhost") or ``ROLE_PATH`` ("path")


def find_prompt(text: str) -> list[PromptSpan]:
    """Spans of ``user@host`` and the path when ``text`` starts with a known shell prompt.

    ``text`` is the content of one screen line with exactly one character per column (the
    caller replaces the stub cell of a wide character with ``"\\0"``), so a string index is a
    column. The prompt must start at column 0; anything else yields ``[]``.
    """
    if "@" not in text:
        return []
    for pattern in _PATTERNS:
        found = pattern.match(text)
        if found is not None:
            return [
                PromptSpan(found.start(ROLE_USERHOST), found.end(ROLE_USERHOST), ROLE_USERHOST),
                PromptSpan(found.start(ROLE_PATH), found.end(ROLE_PATH), ROLE_PATH),
            ]
    return []
