"""Private key loading with passphrase and ``.ppk`` detection (SPEC §7.8).

Behaviour verified against paramiko 5.0.0 + cryptography 50.0.2 (see docs/PROGRESS.md, Fase 7):
``PKey.from_path(path, password=...)`` needs ``bytes``; an encrypted key without a password
raises ``TypeError``; a wrong password raises ``ValueError``; a password for an unencrypted key
raises ``TypeError``; PKCS#8 files raise ``SSHException`` even when readable.
"""

from __future__ import annotations

import os
from pathlib import Path

import paramiko
from paramiko.pkey import UnknownKeyType

from pyssh import strings

PPK_MAGIC = b"PuTTY-User-Key-File"
PKCS8_MARKERS = (b"-----BEGIN PRIVATE KEY-----", b"-----BEGIN ENCRYPTED PRIVATE KEY-----")
HEADER_BYTES = 64


class KeyLoadError(Exception):
    """A key could not be loaded; ``code`` is one of the ``KEY_*`` codes of SPEC §7.8."""

    def __init__(self, code: str, message: str) -> None:
        """Store the code and the user-facing message."""
        super().__init__(message)
        self.code = code
        self.message = message


class PassphraseRequired(Exception):
    """The key is encrypted and no passphrase was given."""


def load_private_key(path: str, passphrase: str | None = None) -> paramiko.PKey:
    """Load an Ed25519/ECDSA/RSA key in OpenSSH or traditional PEM format."""
    full = Path(os.path.expanduser(path))
    if not full.is_file():
        raise KeyLoadError("KEY_NOT_FOUND", strings.KEY_NOT_FOUND.format(path=path))
    try:
        with full.open("rb") as fh:
            header = fh.read(HEADER_BYTES)
    except OSError as exc:
        raise KeyLoadError("KEY_INVALID", strings.KEY_INVALID.format(path=path)) from exc
    if header.startswith(PPK_MAGIC):
        raise KeyLoadError("KEY_PPK_UNSUPPORTED", strings.KEY_PPK_UNSUPPORTED)
    if any(header.startswith(marker) for marker in PKCS8_MARKERS):
        raise KeyLoadError("KEY_INVALID", strings.KEY_PKCS8_UNSUPPORTED.format(path=path))

    secret = passphrase.encode("utf-8") if passphrase else None
    try:
        return paramiko.PKey.from_path(str(full), password=secret)
    except paramiko.PasswordRequiredException as exc:
        if secret is None:
            raise PassphraseRequired from exc
        raise KeyLoadError("KEY_BAD_PASSPHRASE", strings.KEY_BAD_PASSPHRASE) from exc
    except UnknownKeyType as exc:
        raise KeyLoadError("KEY_UNSUPPORTED_TYPE", strings.KEY_UNSUPPORTED_TYPE) from exc
    except TypeError as exc:
        if "password" not in str(exc).lower():
            raise KeyLoadError("KEY_INVALID", strings.KEY_INVALID.format(path=path)) from exc
        if secret is None:
            raise PassphraseRequired from exc
        # A passphrase was given but the key is not encrypted: load it without one.
        return load_private_key(path, None)
    except (paramiko.SSHException, ValueError) as exc:
        if secret is not None:
            raise KeyLoadError("KEY_BAD_PASSPHRASE", strings.KEY_BAD_PASSPHRASE) from exc
        raise KeyLoadError("KEY_INVALID", strings.KEY_INVALID.format(path=path)) from exc
