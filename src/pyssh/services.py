"""``AppServices`` dependency container."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pyssh.config import AppPaths
from pyssh.core.database import Database
from pyssh.core.secret_store import SecretStore
from pyssh.core.session_store import SessionStore
from pyssh.core.settings_store import SettingsStore
from pyssh.core.vault import Vault


@dataclass
class AppServices:
    """Objects shared by the UI; tests build it with fakes.

    ``worker_factory`` is set when the SSH worker exists (Phase 4).
    """

    paths: AppPaths
    database: Database
    session_store: SessionStore
    settings_store: SettingsStore
    vault: Vault
    secret_store: SecretStore
    worker_factory: Callable[..., Any] | None = None
