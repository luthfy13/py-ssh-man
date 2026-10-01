"""Tests for ui.terminal_tab with FakeWorker (SPEC §9.6, §10.2)."""

from __future__ import annotations

import time

import pytest
from PySide6.QtWidgets import QMessageBox

from fakes import WorkerFactory
from pyssh import strings
from pyssh.core.ssh_worker import HostKeyDecision
from pyssh.models import SessionConfig
from pyssh.ui import terminal_tab as tab_module
from pyssh.ui.dialogs import HostKeyDialog, PasswordDialog
from pyssh.ui.terminal_tab import MAX_PASSWORD_ATTEMPTS, TabState, TerminalTab

MASTER = "master-pass-1"


@pytest.fixture
def factory(services) -> WorkerFactory:
    services.worker_factory = WorkerFactory()
    return services.worker_factory


@pytest.fixture
def session(services) -> SessionConfig:
    s = SessionConfig(name="Web", host="10.0.0.5", username="admin", port=2222)
    services.session_store.add(s)
    return s


class Prompts:
    """Scripted PasswordDialog answers; records how the dialog was configured."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.answers: list[tuple[str, bool] | None] = []
        self.calls: list[dict] = []
        prompts = self

        def fake_ask(dialog: PasswordDialog):
            prompts.calls.append(
                {
                    "error": dialog.error_label.text()
                    if not dialog.error_label.isHidden()
                    else None,
                    "remember_shown": dialog._show_remember,
                    "remember_default": dialog.remember_check.isChecked(),
                    "title": dialog.windowTitle(),
                }
            )
            return prompts.answers.pop(0)

        monkeypatch.setattr(PasswordDialog, "ask", fake_ask)


@pytest.fixture
def prompts(monkeypatch: pytest.MonkeyPatch) -> Prompts:
    return Prompts(monkeypatch)


def _tab(qtbot, session, services, **kwargs) -> TerminalTab:
    tab = TerminalTab(session, services, **kwargs)
    qtbot.addWidget(tab)
    tab.resize(800, 500)
    tab.show()
    return tab


def _states(tab: TerminalTab) -> list[TabState]:
    seen: list[TabState] = []
    tab.state_changed.connect(seen.append)
    return seen


def test_state_transitions(qtbot, services, factory, session, prompts) -> None:
    prompts.answers = [("pw", False)]
    tab = _tab(qtbot, session, services)
    states = _states(tab)
    assert tab.state is TabState.IDLE
    tab.connect_session()
    assert tab.state is TabState.CONNECTING
    worker = factory.last
    assert worker.started
    assert worker.params.password == "pw"
    assert (worker.params.host, worker.params.port, worker.params.username) == (
        "10.0.0.5",
        2222,
        "admin",
    )
    assert worker.params.connect_timeout == services.settings_store.current.connect_timeout_seconds
    assert worker.known_hosts_path == services.paths.known_hosts_file
    assert not tab.terminal.input_enabled
    worker.connected.emit()
    assert tab.state is TabState.CONNECTED
    assert tab.terminal.input_enabled
    assert tab.banner.isHidden()
    assert tab.status_text() == "Terhubung — admin@10.0.0.5:2222"
    worker.disconnected.emit("Sesi berakhir (kode keluar 0).")
    assert tab.state is TabState.DISCONNECTED
    assert not tab.banner.isHidden()
    assert tab.banner.message_label.text() == "Sesi berakhir (kode keluar 0)."
    assert not tab.terminal.input_enabled
    worker.finished.emit()
    assert tab.worker is None
    assert states == [TabState.CONNECTING, TabState.CONNECTED, TabState.DISCONNECTED]


def test_connected_marks_last_used(qtbot, services, factory, session, prompts) -> None:
    prompts.answers = [("pw", False)]
    tab = _tab(qtbot, session, services)
    tab.connect_session()
    factory.last.connected.emit()
    assert services.session_store.get(session.id).last_used_at is not None


def test_terminal_and_worker_are_wired(qtbot, services, factory, session, prompts) -> None:
    prompts.answers = [("pw", False)]
    tab = _tab(qtbot, session, services)
    tab.connect_session()
    worker = factory.last
    tab.terminal.input_bytes.emit(b"early")  # not connected yet: dropped
    worker.connected.emit()
    worker.data_received.emit(b"remote output")
    tab.terminal.flush_pending()
    assert any("remote output" in line for line in tab.terminal.emulator.screen_lines_text())
    tab.terminal.input_bytes.emit(b"ls\r")
    tab.terminal.grid_size_changed.emit(100, 30)
    tab.terminal.backpressure.emit(True)
    assert worker.sent == [b"ls\r"]
    assert worker.resizes == [(100, 30)]
    assert worker.paused == [True]


def test_prompt_when_no_secret(qtbot, services, factory, session, prompts) -> None:
    prompts.answers = [("pw", False)]
    tab = _tab(qtbot, session, services)
    tab.connect_session()
    assert len(prompts.calls) == 1
    assert prompts.calls[0]["remember_shown"] is True
    assert prompts.calls[0]["remember_default"] is False
    assert prompts.calls[0]["title"] == strings.PASSWORD_TITLE


def test_stored_secret_used_without_prompt(qtbot, services, factory, session, prompts) -> None:
    services.vault.initialize(MASTER)
    services.secret_store.set_secret(session.id, "stored-pw")
    session.remember_secret = True
    tab = _tab(qtbot, session, services)
    tab.connect_session()
    assert prompts.calls == []
    assert factory.last.params.password == "stored-pw"


def test_prompt_when_vault_locked(qtbot, services, factory, session, prompts) -> None:
    services.vault.initialize(MASTER)
    services.secret_store.set_secret(session.id, "stored-pw")
    services.vault.lock()
    session.remember_secret = True
    prompts.answers = [("typed-pw", False)]
    tab = _tab(qtbot, session, services)
    tab.connect_session()
    assert len(prompts.calls) == 1
    assert prompts.calls[0]["remember_default"] is True
    assert factory.last.params.password == "typed-pw"


def test_secret_saved_only_after_connected(qtbot, services, factory, session, prompts) -> None:
    services.vault.initialize(MASTER)
    prompts.answers = [("new-pw", True)]
    tab = _tab(qtbot, session, services)
    tab.connect_session()
    assert services.secret_store.has_secret(session.id) is False
    factory.last.connected.emit()
    assert services.secret_store.get_secret(session.id) == "new-pw"
    assert services.session_store.get(session.id).remember_secret is True


def test_wrong_stored_secret_is_replaced(qtbot, services, factory, session, prompts) -> None:
    services.vault.initialize(MASTER)
    services.secret_store.set_secret(session.id, "old-wrong")
    session.remember_secret = True
    prompts.answers = [("correct-pw", True)]
    tab = _tab(qtbot, session, services)
    tab.connect_session()
    factory.last.auth_failed.emit("Autentikasi gagal")
    assert prompts.calls[0]["error"] == strings.PASSWORD_RETRY
    assert services.secret_store.get_secret(session.id) == "old-wrong"  # not yet
    factory.last.connected.emit()
    assert services.secret_store.get_secret(session.id) == "correct-pw"


def test_failed_connection_does_not_save(qtbot, services, factory, session, prompts) -> None:
    services.vault.initialize(MASTER)
    prompts.answers = [("pw", True)]
    tab = _tab(qtbot, session, services)
    tab.connect_session()
    factory.last.failed.emit("E_CONNECT", "Tidak dapat terhubung")
    assert services.secret_store.has_secret(session.id) is False


def test_vault_not_opened_reports_info(
    qtbot, services, factory, session, prompts, monkeypatch
) -> None:
    prompts.answers = [("pw", True)]
    monkeypatch.setattr(tab_module, "ensure_vault_unlocked", lambda parent, vault: False)
    tab = _tab(qtbot, session, services)
    infos: list[str] = []
    tab.info_message.connect(infos.append)
    tab.connect_session()
    factory.last.connected.emit()
    assert infos == [strings.SECRET_NOT_SAVED_VAULT]
    assert services.secret_store.has_secret(session.id) is False


def test_password_retry_max_three(qtbot, services, factory, session, prompts) -> None:
    prompts.answers = [("p1", False), ("p2", False), ("p3", False)]
    tab = _tab(qtbot, session, services)
    tab.connect_session()
    for attempt in range(MAX_PASSWORD_ATTEMPTS):
        worker = factory.last
        assert worker.params.password == f"p{attempt + 1}"
        worker.auth_failed.emit("Autentikasi gagal untuk admin@10.0.0.5.")
    assert len(factory.workers) == 3
    assert [c["error"] for c in prompts.calls] == [
        None,
        strings.PASSWORD_RETRY,
        strings.PASSWORD_RETRY,
    ]
    assert tab.state is TabState.FAILED
    assert tab.message == "Autentikasi gagal untuk admin@10.0.0.5."
    assert factory.workers[0].stopped and factory.workers[1].stopped


def test_cancel_prompt_fails(qtbot, services, factory, session, prompts) -> None:
    prompts.answers = [None]
    tab = _tab(qtbot, session, services)
    tab.connect_session()
    assert tab.state is TabState.FAILED
    assert tab.message == strings.CANCELLED_BY_USER
    assert factory.workers == []


def test_host_key_dialog_resolves(qtbot, services, factory, session, prompts, monkeypatch) -> None:
    prompts.answers = [("pw", False)]
    asked: list[tuple] = []

    def fake_ask(dialog: HostKeyDialog) -> HostKeyDecision:
        asked.append(dialog.fingerprint_label.text())
        return HostKeyDecision.ACCEPT_ONCE

    monkeypatch.setattr(HostKeyDialog, "ask", fake_ask)
    tab = _tab(qtbot, session, services)
    tab.connect_session()
    factory.last.host_key_unknown.emit("10.0.0.5", 2222, "ssh-ed25519", "SHA256:abc")
    assert asked == ["SHA256:abc"]
    assert factory.last.host_key_decisions == [HostKeyDecision.ACCEPT_ONCE]


def test_failure_shows_message_and_hostkey_changed_box(
    qtbot, services, factory, session, prompts, monkeypatch
) -> None:
    prompts.answers = [("pw", False)]
    boxes: list[str] = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: boxes.append(a[2]))
    tab = _tab(qtbot, session, services)
    tab.connect_session()
    tab.connect_session()  # already connecting: ignored
    assert len(factory.workers) == 1
    factory.last.failed.emit("E_HOSTKEY_CHANGED", "PERINGATAN: host key berubah!")
    assert tab.state is TabState.FAILED
    assert tab.banner.message_label.text() == "PERINGATAN: host key berubah!"
    assert len(boxes) == 1 and strings.HOSTKEY_CHANGED_HINT_SESSION in boxes[0]


def test_reconnect_creates_new_worker(qtbot, services, factory, session, prompts) -> None:
    prompts.answers = [("pw", False), ("pw2", False)]
    tab = _tab(qtbot, session, services)
    tab.connect_session()
    first = factory.last
    first.connected.emit()
    tab.reconnect()  # connected: ignored
    assert len(factory.workers) == 1
    first.disconnected.emit("Koneksi terputus.")
    tab.terminal.reconnect_requested.emit()  # R / Enter in the terminal
    assert len(factory.workers) == 2
    assert first.stopped
    assert tab.state is TabState.CONNECTING
    first.connected.emit()  # stale worker: ignored
    first.data_received.emit(b"stale")
    assert tab.state is TabState.CONNECTING


def test_banner_buttons(qtbot, services, factory, session, prompts) -> None:
    prompts.answers = [None, ("pw", False)]
    tab = _tab(qtbot, session, services)
    closes: list[bool] = []
    tab.close_requested.connect(lambda: closes.append(True))
    tab.connect_session()
    tab.banner.close_button.click()
    assert closes == [True]
    tab.banner.reconnect_button.click()
    assert tab.state is TabState.CONNECTING


def test_close_session_stops_worker_quickly(qtbot, services, factory, session, prompts) -> None:
    prompts.answers = [("pw", False)]
    tab = _tab(qtbot, session, services)
    tab.connect_session()
    worker = factory.last
    worker.connected.emit()
    started = time.perf_counter()
    tab.close_session()
    elapsed = time.perf_counter() - started
    assert elapsed < 0.1
    assert worker.stopped
    assert worker.signalsBlocked()
    assert tab.state is TabState.CLOSED
    assert tab.join_workers(1.0) is True
    tab.connect_session()  # closed: ignored
    assert len(factory.workers) == 1


def test_adhoc_has_no_remember_and_no_touch(qtbot, services, factory, prompts) -> None:
    prompts.answers = [("pw", True)]
    session = SessionConfig(name="u@h", host="h", username="u")
    tab = _tab(qtbot, session, services, adhoc=True)
    tab.connect_session()
    assert prompts.calls[0]["remember_shown"] is False
    factory.last.connected.emit()
    assert tab.adhoc is True
    assert services.secret_store.has_secret(session.id) is False


def test_adhoc_hostkey_changed_hint_names_file(
    qtbot, services, factory, prompts, monkeypatch
) -> None:
    prompts.answers = [("pw", False)]
    boxes: list[str] = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: boxes.append(a[2]))
    tab = _tab(qtbot, SessionConfig(name="u@h", host="h", username="u"), services, adhoc=True)
    tab.connect_session()
    factory.last.failed.emit("E_HOSTKEY_CHANGED", "berubah")
    assert str(services.paths.known_hosts_file) in boxes[0]


def test_title_changed_forwarded(qtbot, services, factory, session, prompts) -> None:
    prompts.answers = [("pw", False)]
    tab = _tab(qtbot, session, services)
    titles: list[str] = []
    tab.title_changed.connect(titles.append)
    tab.connect_session()
    factory.last.connected.emit()
    factory.last.data_received.emit(b"\x1b]0;admin@web: ~\x07")
    tab.terminal.flush_pending()
    assert titles == ["admin@web: ~"]


def test_missing_worker_factory_raises(qtbot, services, session, prompts) -> None:
    prompts.answers = [("pw", False)]
    services.worker_factory = None
    tab = _tab(qtbot, session, services)
    with pytest.raises(RuntimeError):
        tab.connect_session()


# ----- private key authentication (SPEC §9.6.3 steps 2 and 7) ---------------------------


def _key_file(tmp_path, passphrase: str | None) -> str:
    from cryptography.hazmat.primitives import serialization as ser
    from cryptography.hazmat.primitives.asymmetric import ed25519

    enc = ser.BestAvailableEncryption(passphrase.encode()) if passphrase else ser.NoEncryption()
    path = tmp_path / ("id_pass" if passphrase else "id_plain")
    path.write_bytes(
        ed25519.Ed25519PrivateKey.generate().private_bytes(
            ser.Encoding.PEM, ser.PrivateFormat.OpenSSH, enc
        )
    )
    return str(path)


def _key_session(services, key_path: str, **kwargs) -> SessionConfig:
    from pyssh.models import AuthType

    session = SessionConfig(
        name="Key", host="h", username="u", auth_type=AuthType.KEY, key_path=key_path, **kwargs
    )
    services.session_store.add(session)
    return session


def test_key_without_passphrase(qtbot, services, factory, prompts, tmp_path) -> None:
    session = _key_session(services, _key_file(tmp_path, None))
    tab = _tab(qtbot, session, services)
    tab.connect_session()
    assert prompts.calls == []
    worker = factory.last
    assert worker.params.password is None
    assert worker.params.pkey.get_name() == "ssh-ed25519"


def test_key_passphrase_prompt_and_retry(qtbot, services, factory, prompts, tmp_path) -> None:
    session = _key_session(services, _key_file(tmp_path, "good-phrase"))
    prompts.answers = [("bad", False), ("good-phrase", False)]
    tab = _tab(qtbot, session, services)
    tab.connect_session()
    assert [c["title"] for c in prompts.calls] == [strings.PASSPHRASE_TITLE] * 2
    assert [c["error"] for c in prompts.calls] == [None, strings.PASSPHRASE_RETRY]
    assert factory.last.params.pkey is not None
    assert tab.state is TabState.CONNECTING


def test_key_passphrase_three_wrong_fails(qtbot, services, factory, prompts, tmp_path) -> None:
    session = _key_session(services, _key_file(tmp_path, "good-phrase"))
    prompts.answers = [("a", False), ("b", False), ("c", False)]
    tab = _tab(qtbot, session, services)
    tab.connect_session()
    assert len(prompts.calls) == 3
    assert tab.state is TabState.FAILED
    assert tab.message == strings.KEY_BAD_PASSPHRASE
    assert factory.workers == []


def test_key_passphrase_cancel(qtbot, services, factory, prompts, tmp_path) -> None:
    session = _key_session(services, _key_file(tmp_path, "good-phrase"))
    prompts.answers = [None]
    tab = _tab(qtbot, session, services)
    tab.connect_session()
    assert tab.message == strings.CANCELLED_BY_USER


def test_stored_passphrase_used(qtbot, services, factory, prompts, tmp_path) -> None:
    services.vault.initialize(MASTER)
    session = _key_session(services, _key_file(tmp_path, "good-phrase"))
    services.secret_store.set_secret(session.id, "good-phrase")
    session = services.session_store.get(session.id)
    tab = _tab(qtbot, session, services)
    tab.connect_session()
    assert prompts.calls == []
    assert factory.last.params.pkey is not None


def test_wrong_stored_passphrase_prompts_and_saves(
    qtbot, services, factory, prompts, tmp_path
) -> None:
    services.vault.initialize(MASTER)
    session = _key_session(services, _key_file(tmp_path, "good-phrase"))
    services.secret_store.set_secret(session.id, "old-wrong")
    session = services.session_store.get(session.id)
    prompts.answers = [("good-phrase", True)]
    tab = _tab(qtbot, session, services)
    tab.connect_session()
    assert prompts.calls[0]["error"] == strings.PASSPHRASE_RETRY
    assert services.secret_store.get_secret(session.id) == "old-wrong"
    factory.last.connected.emit()
    assert services.secret_store.get_secret(session.id) == "good-phrase"


def test_key_load_error_fails(qtbot, services, factory, prompts, tmp_path) -> None:
    ppk = tmp_path / "k.ppk"
    ppk.write_text("PuTTY-User-Key-File-3: ssh-ed25519\n")
    session = _key_session(services, str(ppk))
    tab = _tab(qtbot, session, services)
    tab.connect_session()
    assert tab.state is TabState.FAILED
    assert tab.message == strings.KEY_PPK_UNSUPPORTED


def test_key_error_after_passphrase(
    qtbot, services, factory, prompts, tmp_path, monkeypatch
) -> None:
    from pyssh.core.key_loader import KeyLoadError, PassphraseRequired

    session = _key_session(services, _key_file(tmp_path, "good-phrase"))
    calls = iter([PassphraseRequired(), KeyLoadError("KEY_INVALID", "rusak")])

    def fake_load(path, passphrase=None):
        raise next(calls)

    monkeypatch.setattr(tab_module, "load_private_key", fake_load)
    prompts.answers = [("x", False)]
    tab = _tab(qtbot, session, services)
    tab.connect_session()
    assert tab.message == "rusak"


def test_server_rejects_key(qtbot, services, factory, prompts, tmp_path) -> None:
    session = _key_session(services, _key_file(tmp_path, None))
    tab = _tab(qtbot, session, services)
    tab.connect_session()
    factory.last.auth_failed.emit("Autentikasi gagal")
    assert tab.state is TabState.FAILED
    assert tab.message == strings.KEY_REJECTED
    assert len(factory.workers) == 1  # no retry for keys
