"""Application startup: ``main()`` creates the QApplication and the main window.

Argument parsing, logging, database and vault setup are added in Phases 1 and 2 (SPEC §9.2).
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from pyssh import config
from pyssh.ui.main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    """Run the application and return the process exit code."""
    args = sys.argv if argv is None else [sys.argv[0], *argv]
    app = QApplication(args)
    app.setApplicationName(config.APP_NAME)
    app.setOrganizationName(config.APP_ORG)

    window = MainWindow()
    window.show()
    return app.exec()
