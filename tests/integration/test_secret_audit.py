"""N-01 secret audit: no plaintext secret in any file of the data folder (SPEC §10.2)."""

from __future__ import annotations

import pytest

from pyssh import config
from pyssh.app import build_services
from pyssh.core.database import Database
from pyssh.core.ssh_worker import HostKeyDecision
from pyssh.logging_setup import setup_logging, shutdown_logging
from pyssh.models import SessionConfig
from pyssh.ui.dialogs import HostKeyDialog, PasswordDialog
from pyssh.ui.terminal_tab import TabState, TerminalTab

MASTER = "Master-Audit-Z9q7-unique"
MIN_UNIQUE_LEN = 12


def test_secret_audit(qtbot, server, monkeypatch: pytest.MonkeyPatch) -> None:
    if len(server.password) < MIN_UNIQUE_LEN:
        pytest.skip(
            "PYSSH_TEST_PASSWORD harus unik (>= 12 karakter, mis. secret-Z9q7-unique) agar "
            "pencarian byte tidak cocok dengan teks lain seperti nama tabel 'secrets'"
        )
    paths = config.get_paths()  # PYSSH_HOME → tmp (tests/conftest.py)
    config.ensure_dirs(paths)
    setup_logging(paths, debug=True)
    database = Database(paths.db_file)
    database.open()
    services = build_services(paths, database)
    services.vault.initialize(MASTER)
    session = SessionConfig(name="Audit", host=server.host, port=server.port, username=server.user)
    services.session_store.add(session)

    monkeypatch.setattr(PasswordDialog, "ask", lambda self: (server.password, True))
    monkeypatch.setattr(HostKeyDialog, "ask", lambda self: HostKeyDecision.ACCEPT_SAVE)
    tab = TerminalTab(session, services)
    qtbot.addWidget(tab)
    tab.connect_session()
    qtbot.waitUntil(lambda: tab.state is TabState.CONNECTED, timeout=15_000)
    assert services.secret_store.get_secret(session.id) == server.password
    tab.terminal.input_bytes.emit(b"echo audit-done\n")
    qtbot.waitUntil(
        lambda: any("audit-done" in line for line in tab.terminal.emulator.screen_lines_text()),
        timeout=15_000,
    )
    tab.close_session()
    assert tab.join_workers(2.0)
    services.vault.lock()
    database.close()
    shutdown_logging()

    files = [p for p in paths.root.rglob("*") if p.is_file()]
    names = {p.name for p in files}
    assert {"pyssh.db", "known_hosts", "pyssh.log"} <= names
    for needle in (server.password, MASTER):
        raw = needle.encode("utf-8")
        hits = [str(p) for p in files if raw in p.read_bytes()]
        assert hits == [], f"plaintext found in {hits}"
