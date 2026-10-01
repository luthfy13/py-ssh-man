"""Smoke tests: every module imports and the main window can be created."""

from __future__ import annotations

import importlib
import pkgutil

import pytest

import pyssh
from pyssh import config
from pyssh.ui.main_window import MainWindow


def _all_module_names() -> list[str]:
    names = [pyssh.__name__]
    for info in pkgutil.walk_packages(pyssh.__path__, prefix=f"{pyssh.__name__}."):
        if info.name != "pyssh.__main__":
            names.append(info.name)
    return sorted(names)


def test_package_contains_expected_subpackages() -> None:
    names = set(_all_module_names())
    assert {"pyssh.core", "pyssh.terminal", "pyssh.ui", "pyssh.app"} <= names


@pytest.mark.parametrize("module_name", _all_module_names())
def test_module_imports(module_name: str) -> None:
    importlib.import_module(module_name)


def test_version() -> None:
    assert pyssh.__version__ == "0.1.0"


def test_main_window_created(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    assert window.windowTitle() == config.APP_NAME == "PySSH"
