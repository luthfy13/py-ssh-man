"""Master password vault: state, DEK wrapping and unwrapping (SPEC §6.5, §7.5).

The master password and KEK are never stored; the DEK lives in memory only while UNLOCKED.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from enum import Enum

from pyssh.core import crypto
from pyssh.core.crypto import DEFAULT_KDF, DecryptError, KdfParams
from pyssh.core.database import Database
from pyssh.models import now_iso

log = logging.getLogger(__name__)

MIN_MASTER_PASSWORD_LEN = 8
KDF_NAME = "scrypt"
DEK_AAD = b"pyssh/dek/v1"
SECRET_AAD_PREFIX = b"pyssh/secret/v1/"


class VaultState(Enum):
    """Lifecycle of the vault (SPEC §6.5)."""

    UNINITIALIZED = "uninitialized"
    LOCKED = "locked"
    UNLOCKED = "unlocked"


class VaultLocked(Exception):
    """The operation needs an UNLOCKED vault."""


def secret_aad(session_id: str) -> bytes:
    """AAD binding a secret's ciphertext to its session."""
    return SECRET_AAD_PREFIX + session_id.encode("utf-8")


class Vault:
    """Holds the DEK while unlocked; persists the wrapped DEK in the ``vault`` table."""

    def __init__(self, db: Database, kdf: KdfParams = DEFAULT_KDF) -> None:
        """Use ``kdf`` for new or re-wrapped vaults; state depends on the table contents."""
        self._db = db
        self._kdf = kdf
        self._dek: bytes | None = None
        self._listeners: list[Callable[[VaultState], None]] = []
        self._state = VaultState.LOCKED if self._row() else VaultState.UNINITIALIZED

    def __repr__(self) -> str:
        """Never expose key material."""
        return f"Vault(state={self._state.value})"

    @property
    def state(self) -> VaultState:
        """Current vault state."""
        return self._state

    def add_listener(self, callback: Callable[[VaultState], None]) -> None:
        """Call ``callback(new_state)`` after every state change (used by the UI)."""
        self._listeners.append(callback)

    def initialize(self, master_password: str) -> None:
        """Create the vault; ``ValueError`` when it already exists or the password is short."""
        if self._state is not VaultState.UNINITIALIZED:
            raise ValueError("vault already initialized")
        _check_length(master_password)
        salt = crypto.new_salt()
        kek = crypto.derive_key(master_password, salt, self._kdf)
        dek = crypto.new_key()
        nonce, wrapped = crypto.encrypt(kek, dek, DEK_AAD)
        now = now_iso()
        with self._db.conn:
            self._db.conn.execute(
                "INSERT INTO vault (id, kdf, kdf_salt, kdf_n, kdf_r, kdf_p, dek_nonce, "
                "dek_wrapped, created_at, updated_at) VALUES (1,?,?,?,?,?,?,?,?,?)",
                (KDF_NAME, salt, self._kdf.n, self._kdf.r, self._kdf.p, nonce, wrapped, now, now),
            )
        self._dek = dek
        log.info("vault initialized")
        self._set_state(VaultState.UNLOCKED)

    def unlock(self, master_password: str) -> bool:
        """Unwrap the DEK with the stored KDF parameters; ``False`` on a wrong password."""
        started = time.perf_counter()
        dek = self._unwrap(master_password)
        elapsed = round((time.perf_counter() - started) * 1000)
        if dek is None:
            log.info("vault unlock failed unlock_ms=%d", elapsed)
            return False
        self._dek = dek
        log.info("vault unlocked unlock_ms=%d", elapsed)
        self._set_state(VaultState.UNLOCKED)
        return True

    def lock(self) -> None:
        """Forget the DEK."""
        self._dek = None
        if self._state is VaultState.UNLOCKED:
            log.info("vault locked")
            self._set_state(VaultState.LOCKED)

    def change_master_password(self, old: str, new: str) -> bool:
        """Re-wrap the DEK with a new password; ``False`` when ``old`` is wrong.

        The new wrap uses a new salt and the current default KDF parameters. Secret rows
        are not touched. On success the vault is UNLOCKED.
        """
        _check_length(new)
        dek = self._unwrap(old)
        if dek is None:
            log.info("vault change master password failed")
            return False
        salt = crypto.new_salt()
        kek = crypto.derive_key(new, salt, self._kdf)
        nonce, wrapped = crypto.encrypt(kek, dek, DEK_AAD)
        with self._db.conn:
            self._db.conn.execute(
                "UPDATE vault SET kdf=?, kdf_salt=?, kdf_n=?, kdf_r=?, kdf_p=?, dek_nonce=?, "
                "dek_wrapped=?, updated_at=? WHERE id = 1",
                (KDF_NAME, salt, self._kdf.n, self._kdf.r, self._kdf.p, nonce, wrapped, now_iso()),
            )
        self._dek = dek
        log.info("vault master password changed")
        self._set_state(VaultState.UNLOCKED)
        return True

    def reset(self) -> None:
        """Delete all secrets and the vault in one transaction; sessions are kept."""
        with self._db.conn:
            self._db.conn.execute("DELETE FROM secrets")
            self._db.conn.execute("DELETE FROM vault")
            self._db.conn.execute("UPDATE sessions SET remember_secret = 0")
        self._dek = None
        log.info("vault reset")
        self._set_state(VaultState.UNINITIALIZED)

    def encrypt_secret(self, session_id: str, secret: str) -> tuple[bytes, bytes]:
        """Encrypt a secret for a session; ``VaultLocked`` when not unlocked."""
        dek = self._require_dek()
        return crypto.encrypt(dek, secret.encode("utf-8"), secret_aad(session_id))

    def decrypt_secret(self, session_id: str, nonce: bytes, ciphertext: bytes) -> str:
        """Decrypt a secret; ``VaultLocked`` or ``DecryptError`` on failure."""
        dek = self._require_dek()
        plaintext = crypto.decrypt(dek, nonce, ciphertext, secret_aad(session_id))
        try:
            return plaintext.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DecryptError("secret is not valid UTF-8") from exc

    def _require_dek(self) -> bytes:
        if self._state is not VaultState.UNLOCKED or self._dek is None:
            raise VaultLocked
        return self._dek

    def _row(self):  # -> sqlite3.Row | None
        return self._db.conn.execute("SELECT * FROM vault WHERE id = 1").fetchone()

    def _unwrap(self, master_password: str) -> bytes | None:
        row = self._row()
        if row is None:
            return None
        params = KdfParams(n=row["kdf_n"], r=row["kdf_r"], p=row["kdf_p"])
        kek = crypto.derive_key(master_password, row["kdf_salt"], params)
        try:
            return crypto.decrypt(kek, row["dek_nonce"], row["dek_wrapped"], DEK_AAD)
        except DecryptError:
            return None

    def _set_state(self, state: VaultState) -> None:
        self._state = state
        for callback in list(self._listeners):
            callback(state)


def _check_length(password: str) -> None:
    if len(password) < MIN_MASTER_PASSWORD_LEN:
        raise ValueError(f"master password shorter than {MIN_MASTER_PASSWORD_LEN} characters")
