"""Encrypted per-session secret storage (SPEC §6.6, §7.6)."""

from __future__ import annotations

import logging

from pyssh.core.crypto import DecryptError
from pyssh.core.database import Database
from pyssh.core.vault import Vault, VaultLocked, VaultState
from pyssh.models import now_iso

log = logging.getLogger(__name__)


class SecretStore:
    """Secrets are stored only as AES-GCM ciphertext in the ``secrets`` table."""

    def __init__(self, db: Database, vault: Vault) -> None:
        """Use the given database and vault."""
        self._db = db
        self._vault = vault

    @property
    def can_store(self) -> bool:
        """True when the vault is unlocked."""
        return self._vault.state is VaultState.UNLOCKED

    def get_secret(self, session_id: str) -> str | None:
        """Return the secret, or ``None`` if absent, vault not unlocked, or undecryptable."""
        if not self.can_store:
            return None
        row = self._db.conn.execute(
            "SELECT nonce, ciphertext FROM secrets WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return None
        try:
            return self._vault.decrypt_secret(session_id, row["nonce"], row["ciphertext"])
        except DecryptError:
            log.warning("secret for session %s could not be decrypted", session_id)
            return None

    def set_secret(self, session_id: str, secret: str) -> None:
        """Encrypt and store a secret and set ``remember_secret = 1``.

        Raises ``VaultLocked`` when the vault is not unlocked and ``KeyError`` when the
        session does not exist.
        """
        if not self.can_store:
            raise VaultLocked
        exists = self._db.conn.execute(
            "SELECT 1 FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if exists is None:
            raise KeyError(session_id)
        nonce, ciphertext = self._vault.encrypt_secret(session_id, secret)
        with self._db.conn:
            self._db.conn.execute(
                "INSERT OR REPLACE INTO secrets (session_id, nonce, ciphertext, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (session_id, nonce, ciphertext, now_iso()),
            )
            self._db.conn.execute(
                "UPDATE sessions SET remember_secret = 1 WHERE id = ?", (session_id,)
            )

    def delete_secret(self, session_id: str) -> None:
        """Delete a secret (works while locked; no error when absent)."""
        with self._db.conn:
            self._db.conn.execute("DELETE FROM secrets WHERE session_id = ?", (session_id,))

    def has_secret(self, session_id: str) -> bool:
        """True when a secret row exists (works while locked)."""
        row = self._db.conn.execute(
            "SELECT 1 FROM secrets WHERE session_id = ?", (session_id,)
        ).fetchone()
        return row is not None
