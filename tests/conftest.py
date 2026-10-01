"""Shared pytest fixtures (SPEC §10.1)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Must run before Qt is imported: headless Linux has no display server.
if (
    sys.platform.startswith("linux")
    and not os.environ.get("DISPLAY")
    and not os.environ.get("WAYLAND_DISPLAY")
):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def pyssh_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate every test in its own data folder via ``PYSSH_HOME``."""
    home = tmp_path / "pyssh_home"
    home.mkdir()
    monkeypatch.setenv("PYSSH_HOME", str(home))
    return home


@pytest.fixture
def fast_kdf():
    """Cheap scrypt parameters for tests; the default KDF is deliberately slow (SPEC §10.1)."""
    from pyssh.core.crypto import KdfParams

    return KdfParams(n=2**10, r=8, p=1)


@pytest.fixture
def services(pyssh_home: Path, fast_kdf):
    """Real ``AppServices`` on a fresh database in the isolated data folder."""
    from pyssh import config
    from pyssh.core.database import Database
    from pyssh.core.secret_store import SecretStore
    from pyssh.core.session_store import SessionStore
    from pyssh.core.settings_store import SettingsStore
    from pyssh.core.vault import Vault
    from pyssh.services import AppServices

    paths = config.get_paths()
    config.ensure_dirs(paths)
    database = Database(paths.db_file)
    database.open()
    vault = Vault(database, fast_kdf)
    settings_store = SettingsStore(paths.settings_file, mac=False)
    yield AppServices(
        paths=paths,
        database=database,
        session_store=SessionStore(database),
        settings_store=settings_store,
        vault=vault,
        secret_store=SecretStore(database, vault),
    )
    vault.lock()
    database.close()
