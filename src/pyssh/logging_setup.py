"""Rotating file logging setup (SPEC §6.8)."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from pyssh.config import AppPaths

LOG_FORMAT = "%(asctime)s %(levelname)s [%(threadName)s] %(name)s: %(message)s"
MAX_BYTES = 1_000_000
BACKUP_COUNT = 3

_handler: RotatingFileHandler | None = None


def setup_logging(paths: AppPaths, *, debug: bool = False) -> RotatingFileHandler:
    """Attach a rotating file handler to the root logger.

    Calling it again replaces the previous handler (used by tests).
    """
    global _handler
    root = logging.getLogger()
    if _handler is not None:
        root.removeHandler(_handler)
        _handler.close()
    handler = RotatingFileHandler(
        paths.log_file, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    logging.getLogger("paramiko").setLevel(logging.DEBUG if debug else logging.WARNING)
    _handler = handler
    return handler


def shutdown_logging() -> None:
    """Detach and close the handler installed by ``setup_logging``."""
    global _handler
    if _handler is not None:
        logging.getLogger().removeHandler(_handler)
        _handler.close()
        _handler = None
