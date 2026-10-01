"""Pure cryptographic helpers: scrypt key derivation and AES-256-GCM (SPEC §6.5, §7.4).

Only the primitives listed in SPEC §6.5 are used (rule A13).
"""

from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

KEY_LEN = 32
NONCE_LEN = 12
SALT_LEN = 16


@dataclass(frozen=True)
class KdfParams:
    """scrypt cost parameters (stored in the ``vault`` table)."""

    n: int = 2**17
    r: int = 8
    p: int = 1


DEFAULT_KDF = KdfParams()


class DecryptError(Exception):
    """Decryption failed: wrong key, wrong AAD, or tampered data."""


def derive_key(password: str, salt: bytes, params: KdfParams) -> bytes:
    """Derive a 32-byte key from a password (NFC-normalised, UTF-8 encoded)."""
    data = unicodedata.normalize("NFC", password).encode("utf-8")
    kdf = Scrypt(salt=salt, length=KEY_LEN, n=params.n, r=params.r, p=params.p)
    return kdf.derive(data)


def new_salt() -> bytes:
    """Return a random salt."""
    return os.urandom(SALT_LEN)


def new_key() -> bytes:
    """Return a random 256-bit key."""
    return os.urandom(KEY_LEN)


def encrypt(key: bytes, plaintext: bytes, aad: bytes) -> tuple[bytes, bytes]:
    """Encrypt with AES-256-GCM and a fresh random nonce; returns ``(nonce, ciphertext+tag)``."""
    nonce = os.urandom(NONCE_LEN)
    return nonce, AESGCM(key).encrypt(nonce, plaintext, aad)


def decrypt(key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes) -> bytes:
    """Decrypt AES-256-GCM data; any failure raises ``DecryptError``."""
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, aad)
    except (InvalidTag, ValueError) as exc:
        raise DecryptError("decryption failed") from exc
