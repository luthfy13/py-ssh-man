"""Tests for core.known_hosts (SPEC §7.9)."""

from __future__ import annotations

import base64
import hashlib
import io
from pathlib import Path

import paramiko
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519

from pyssh import config
from pyssh.core.known_hosts import ensure_file, entry_name, fingerprint_sha256, forget_host


def _ed25519() -> paramiko.PKey:
    pem = ed25519.Ed25519PrivateKey.generate().private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.OpenSSH,
        serialization.NoEncryption(),
    )
    return paramiko.Ed25519Key.from_private_key(io.StringIO(pem.decode()))


def _ecdsa() -> paramiko.PKey:
    pem = ec.generate_private_key(ec.SECP256R1()).private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.OpenSSH,
        serialization.NoEncryption(),
    )
    return paramiko.ECDSAKey.from_private_key(io.StringIO(pem.decode()))


def test_fingerprint_format_matches_openssh_definition() -> None:
    key = _ed25519()
    fingerprint = fingerprint_sha256(key)
    assert fingerprint.startswith("SHA256:")
    assert len(fingerprint) == len("SHA256:") + 43
    assert "=" not in fingerprint
    # Independent computation from the public key line ("ssh-ed25519 <base64 blob>").
    blob = base64.b64decode(key.get_base64())
    expected = base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")
    assert fingerprint == "SHA256:" + expected


@pytest.mark.parametrize(
    ("host", "port", "expected"),
    [
        ("example.org", 22, "example.org"),
        ("example.org", 2222, "[example.org]:2222"),
        ("10.0.0.5", 22, "10.0.0.5"),
        ("::1", 22, "::1"),
        ("::1", 2200, "[::1]:2200"),
    ],
)
def test_entry_name(host: str, port: int, expected: str) -> None:
    assert entry_name(host, port) == expected


def _write(path: Path, entries: list[tuple[str, paramiko.PKey]]) -> None:
    host_keys = paramiko.HostKeys()
    for name, key in entries:
        host_keys.add(name, key.get_name(), key)
    host_keys.save(str(path))


def test_forget_host_port_22_and_other_port(tmp_path: Path) -> None:
    path = tmp_path / "known_hosts"
    a, b, c = _ed25519(), _ecdsa(), _ed25519()
    _write(path, [("srv", a), ("srv", b), ("[srv]:2222", c), ("other", a)])
    assert forget_host(path, "srv", 22) is True
    remaining = paramiko.HostKeys(str(path))
    assert remaining.lookup("srv") is None
    assert remaining.lookup("[srv]:2222") is not None
    assert remaining.lookup("other") is not None
    assert forget_host(path, "srv", 2222) is True
    assert paramiko.HostKeys(str(path)).lookup("[srv]:2222") is None
    assert forget_host(path, "srv", 2222) is False


def test_forget_host_missing_file(tmp_path: Path) -> None:
    assert forget_host(tmp_path / "nope", "srv", 22) is False


def test_ensure_file(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "known_hosts"
    ensure_file(path)
    assert path.read_text() == ""
    path.write_text("keep\n")
    ensure_file(path)
    assert path.read_text() == "keep\n"
    if not config.IS_WINDOWS:
        assert oct(path.stat().st_mode & 0o777) == oct(0o600)
