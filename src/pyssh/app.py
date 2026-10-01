"""Application startup ``main()`` (SPEC §9.2)."""

from __future__ import annotations

import argparse
import logging
import sys
import threading
import time
from types import TracebackType

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from pyssh import __version__, config, strings
from pyssh.core.database import SCHEMA_VERSION, Database, DatabaseVersionError
from pyssh.core.session_store import SessionStore
from pyssh.core.settings_store import SettingsStore
from pyssh.logging_setup import setup_logging
from pyssh.services import AppServices
from pyssh.ui.main_window import MainWindow

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
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    if args.version:
        print(strings.VERSION_LINE.format(app=config.APP_NAME, version=__version__))
        return 0

    paths = config.get_paths()
    config.ensure_dirs(paths)
    setup_logging(paths, debug=args.debug)
    install_excepthooks(str(paths.log_file))
    log.info("starting %s %s", config.APP_NAME, __version__)

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

    settings_store = SettingsStore(paths.settings_file)
    settings_store.load()
    services = AppServices(
        paths=paths,
        database=database,
        session_store=SessionStore(database),
        settings_store=settings_store,
    )

    window = MainWindow(services)
    window.show()
    log.info("startup startup_ms=%d", round((time.perf_counter() - started) * 1000))
    if db_warning:
        QTimer.singleShot(0, lambda: QMessageBox.warning(window, strings.WARNING_TITLE, db_warning))
    try:
        return app.exec()
    finally:
        database.close()
