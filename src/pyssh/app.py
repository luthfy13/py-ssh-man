"""Application startup ``main()`` (SPEC §9.2)."""

from __future__ import annotations

import argparse
import logging
import sys
import threading
import time
from types import TracebackType

from PySide6.QtCore import QCoreApplication, Qt, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from pyssh import __version__, config, strings
from pyssh.core.database import SCHEMA_VERSION, Database, DatabaseVersionError
from pyssh.core.secret_store import SecretStore
from pyssh.core.session_store import SessionStore
from pyssh.core.settings_store import SettingsStore
from pyssh.core.ssh_worker import SSHWorker
from pyssh.core.vault import Vault, VaultState
from pyssh.logging_setup import setup_logging
from pyssh.services import AppServices
from pyssh.ui.main_window import MainWindow
from pyssh.ui.vault_dialogs import UnlockDialog

log = logging.getLogger(__name__)

EXIT_DB_VERSION = 2


def build_parser() -> argparse.ArgumentParser:
    """Command line options (SPEC §9.2 step 1)."""
    parser = argparse.ArgumentParser(prog=config.APP_NAME.lower())
    parser.add_argument("--demo", action="store_true", help="open the terminal demo tab")
    parser.add_argument("--connect", metavar="USER@HOST[:PORT]", help="ad-hoc connection")
    parser.add_argument("--debug", action="store_true", help="verbose logging")
    parser.add_argument("--version", action="store_true", help="print the version and exit")
    return parser


def parse_target(text: str) -> tuple[str, str, int]:
    """Parse ``user@host[:port]``; IPv6 hosts may be written as ``[addr]:port``."""
    user, sep, rest = text.partition("@")
    if not sep or not user or not rest:
        raise ValueError(text)
    port = 22
    if rest.startswith("["):
        host, bracket, tail = rest[1:].partition("]")
        if not bracket or (tail and not tail.startswith(":")):
            raise ValueError(text)
        if tail:
            port = int(tail[1:])
    elif rest.count(":") == 1:
        host, _, port_text = rest.partition(":")
        port = int(port_text)
    else:
        host = rest  # no port, or a bare IPv6 address
    if not host or not 1 <= port <= 65535:
        raise ValueError(text)
    return user, host, port


def install_excepthooks(log_file: str) -> None:
    """Log unhandled exceptions; on the GUI thread also show a short message box."""

    def handle(
        exc_type: type[BaseException],
        exc: BaseException,
        tb: TracebackType | None,
    ) -> None:
        log.critical("unhandled exception", exc_info=(exc_type, exc, tb))
        app = QApplication.instance()
        if app is not None and threading.current_thread() is threading.main_thread():
            QMessageBox.critical(
                None,
                strings.UNHANDLED_ERROR_TITLE,
                strings.UNHANDLED_ERROR.format(name=exc_type.__name__, log_file=log_file),
            )

    def thread_handle(args: threading.ExceptHookArgs) -> None:
        log.critical(
            "unhandled exception in thread %s",
            args.thread.name if args.thread else "?",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = handle  # type: ignore[assignment]
    threading.excepthook = thread_handle


def main(argv: list[str] | None = None) -> int:
    """Run the application and return the process exit code."""
    started = time.perf_counter()
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    target = None
    if args.connect:
        try:
            target = parse_target(args.connect)
        except ValueError:
            parser.error(strings.ERR_CONNECT_ARG)
    if args.version:
        print(strings.VERSION_LINE.format(app=config.APP_NAME, version=__version__))
        return 0

    paths = config.get_paths()
    config.ensure_dirs(paths)
    setup_logging(paths, debug=args.debug)
    install_excepthooks(str(paths.log_file))
    log.info("starting %s %s", config.APP_NAME, __version__)

    if config.IS_MAC:
        # Must precede QApplication: Ctrl = physical Control, Meta = Command (SPEC §8.3.1).
        QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_MacDontSwapCtrlAndMeta, True)
    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setApplicationName(config.APP_NAME)
    app.setOrganizationName(config.APP_ORG)

    database = Database(paths.db_file)
    try:
        db_warning = database.open()
    except DatabaseVersionError as exc:
        log.error("database schema version %d is newer than supported", exc.found)
        QMessageBox.critical(
            None,
            strings.DB_NEWER_VERSION_TITLE,
            strings.DB_NEWER_VERSION.format(
                found=exc.found, supported=SCHEMA_VERSION, path=exc.path
            ),
        )
        return EXIT_DB_VERSION

    services = build_services(paths, database)
    dialog_ms = 0.0
    if services.vault.state is VaultState.LOCKED:
        dialog_started = time.perf_counter()
        UnlockDialog(services.vault, startup=True).exec()
        dialog_ms = (time.perf_counter() - dialog_started) * 1000

    window = MainWindow(services)
    window.show()
    startup_ms = (time.perf_counter() - started) * 1000 - dialog_ms
    log.info("startup startup_ms=%d", round(startup_ms))
    if args.demo:
        window.open_demo_tab()
    if target is not None:
        window.open_adhoc(*target)
    if db_warning:
        QTimer.singleShot(0, lambda: QMessageBox.warning(window, strings.WARNING_TITLE, db_warning))
    try:
        return app.exec()
    finally:
        services.vault.lock()
        database.close()


def build_services(paths: config.AppPaths, database: Database) -> AppServices:
    """Create stores and the vault on an opened database (SPEC §9.2 step 5)."""
    settings_store = SettingsStore(paths.settings_file)
    settings_store.load()
    vault = Vault(database)
    return AppServices(
        paths=paths,
        database=database,
        session_store=SessionStore(database),
        settings_store=settings_store,
        vault=vault,
        secret_store=SecretStore(database, vault),
        worker_factory=SSHWorker,
    )
