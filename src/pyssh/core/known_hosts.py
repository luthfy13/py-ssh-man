"""Host key fingerprints and ``known_hosts`` entry management (SPEC §6.7, §7.9)."""

from __future__ import annotations

import base64
import hashlib
import threading
from pathlib import Path

import paramiko

from pyssh import config

# Several tabs may save host keys at the same time (SPEC §6.7).
KNOWN_HOSTS_LOCK = threading.Lock()


def ensure_file(path: Path) -> None:
    """Create an empty ``known_hosts`` file when missing and restrict its permissions."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        config.restrict_file(path)


def fingerprint_sha256(key: paramiko.PKey) -> str:
    """OpenSSH-style fingerprint: ``SHA256:`` + unpadded base64 of SHA-256(key blob)."""
    digest = hashlib.sha256(key.asbytes()).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


def entry_name(host: str, port: int) -> str:
    """``host`` for port 22, otherwise ``[host]:port`` (same as OpenSSH/paramiko)."""
    return host if port == 22 else f"[{host}]:{port}"


def forget_host(path: Path, host: str, port: int) -> bool:
    """Remove every key stored for ``host:port``; ``True`` when something was removed."""
    name = entry_name(host, port)
    with KNOWN_HOSTS_LOCK:
        if not path.exists():
            return False
        host_keys = paramiko.HostKeys(str(path))
        removed = False
        while True:
            try:
                del host_keys[name]
            except KeyError:
                break
            removed = True
        if removed:
            host_keys.save(str(path))
            config.restrict_file(path)
        return removed
