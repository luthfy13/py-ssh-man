"""Tests for core.crypto (SPEC §6.5, §7.4, N-11)."""

from __future__ import annotations

import pytest

from pyssh.core import crypto
from pyssh.core.crypto import DecryptError, KdfParams


def test_constants_and_defaults() -> None:
    assert (crypto.KEY_LEN, crypto.NONCE_LEN, crypto.SALT_LEN) == (32, 12, 16)
    assert KdfParams(n=2**17, r=8, p=1) == crypto.DEFAULT_KDF
    assert len(crypto.new_salt()) == 16
    assert len(crypto.new_key()) == 32
    assert crypto.new_key() != crypto.new_key()


def test_round_trip() -> None:
    key = crypto.new_key()
    nonce, ciphertext = crypto.encrypt(key, b"rahasia", b"aad")
    assert len(nonce) == 12
    assert len(ciphertext) == len(b"rahasia") + 16  # GCM tag
    assert b"rahasia" not in ciphertext
    assert crypto.decrypt(key, nonce, ciphertext, b"aad") == b"rahasia"


def test_wrong_key_fails() -> None:
    nonce, ciphertext = crypto.encrypt(crypto.new_key(), b"x", b"aad")
    with pytest.raises(DecryptError):
        crypto.decrypt(crypto.new_key(), nonce, ciphertext, b"aad")


def test_wrong_aad_fails() -> None:
    key = crypto.new_key()
    nonce, ciphertext = crypto.encrypt(key, b"x", b"session-a")
    with pytest.raises(DecryptError):
        crypto.decrypt(key, nonce, ciphertext, b"session-b")


def test_one_flipped_bit_fails() -> None:
    key = crypto.new_key()
    nonce, ciphertext = crypto.encrypt(key, b"secret value", b"aad")
    for index in (0, len(ciphertext) - 1):
        tampered = bytearray(ciphertext)
        tampered[index] ^= 0x01
        with pytest.raises(DecryptError):
            crypto.decrypt(key, nonce, bytes(tampered), b"aad")


def test_invalid_nonce_or_key_length_fails() -> None:
    key = crypto.new_key()
    nonce, ciphertext = crypto.encrypt(key, b"x", b"aad")
    with pytest.raises(DecryptError):
        crypto.decrypt(key, b"", ciphertext, b"aad")
    with pytest.raises(DecryptError):
        crypto.decrypt(b"short", nonce, ciphertext, b"aad")


def test_nonces_are_unique() -> None:
    key = crypto.new_key()
    nonces = {crypto.encrypt(key, b"x", b"aad")[0] for _ in range(1000)}
    assert len(nonces) == 1000


def test_derive_key_deterministic(fast_kdf: KdfParams) -> None:
    salt = crypto.new_salt()
    a = crypto.derive_key("password123", salt, fast_kdf)
    assert a == crypto.derive_key("password123", salt, fast_kdf)
    assert len(a) == 32
    assert a != crypto.derive_key("password124", salt, fast_kdf)
    assert a != crypto.derive_key("password123", crypto.new_salt(), fast_kdf)
    assert a != crypto.derive_key("password123", salt, KdfParams(n=2**11, r=8, p=1))


def test_nfc_and_nfd_give_same_key(fast_kdf: KdfParams) -> None:
    salt = crypto.new_salt()
    nfc = "café-sandi"
    nfd = "café-sandi"
    assert nfc != nfd
    assert crypto.derive_key(nfc, salt, fast_kdf) == crypto.derive_key(nfd, salt, fast_kdf)
