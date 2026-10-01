"""Architecture rules checked by scanning the source with ``ast`` (SPEC §4: A6, A11, A12)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import pyssh

SRC = Path(pyssh.__file__).parent

# SPEC §5.3 "Boleh impor Qt?" column, made binding by rule A6.
NO_QT = [
    "config.py",
    "models.py",
    "core/__init__.py",
    "core/database.py",
    "core/session_store.py",
    "core/crypto.py",
    "core/vault.py",
    "core/secret_store.py",
    "core/settings_store.py",
    "core/key_loader.py",
    "core/known_hosts.py",
    "core/errors.py",
    "terminal/emulator.py",
    "terminal/colors.py",
]
QTCORE_ONLY = ["core/ssh_worker.py", "shortcuts.py", "terminal/keymap.py"]


def _all_sources() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.append(node.module)
            names.extend(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def _qt_imports(path: Path) -> set[str]:
    return {
        name for name in _imported_modules(path) if name == "PySide6" or name.startswith("PySide6.")
    }


def test_every_core_module_except_worker_is_listed_as_no_qt() -> None:
    core = {f"core/{p.name}" for p in (SRC / "core").glob("*.py")}
    assert core - {"core/ssh_worker.py"} == {m for m in NO_QT if m.startswith("core/")}


@pytest.mark.parametrize("rel", NO_QT)
def test_module_has_no_pyside6(rel: str) -> None:
    path = SRC / rel
    assert path.exists(), rel
    assert _qt_imports(path) == set(), rel


@pytest.mark.parametrize("rel", QTCORE_ONLY)
def test_module_uses_only_qtcore(rel: str) -> None:
    path = SRC / rel
    assert path.exists(), rel
    allowed = {"PySide6", "PySide6.QtCore"}
    bad = {
        name
        for name in _qt_imports(path)
        if name not in allowed and not name.startswith("PySide6.QtCore.")
    }
    assert bad == set(), (rel, bad)


def _uses_sys_platform(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "platform"
            and isinstance(node.value, ast.Name)
            and node.value.id == "sys"
        ):
            return True
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == "sys"
            and any(alias.name == "platform" for alias in node.names)
        ):
            return True
    return False


def test_sys_platform_only_in_config() -> None:
    offenders = [str(p.relative_to(SRC)) for p in _all_sources() if _uses_sys_platform(p)]
    assert offenders == ["config.py"]


def _print_calls(path: Path) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "print"
    )


def test_no_print_except_version_output() -> None:
    counts = {str(p.relative_to(SRC)): _print_calls(p) for p in _all_sources()}
    offenders = {name: n for name, n in counts.items() if n and name != "app.py"}
    assert offenders == {}
    assert counts["app.py"] == 1  # the --version line


def test_every_module_uses_future_annotations() -> None:
    missing = []
    for path in _all_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        has = any(
            isinstance(node, ast.ImportFrom)
            and node.module == "__future__"
            and any(alias.name == "annotations" for alias in node.names)
            for node in tree.body
        )
        if not has:
            missing.append(str(path.relative_to(SRC)))
    assert missing == []


def test_ui_does_not_import_paramiko() -> None:
    """AC-4.3: network code stays in the worker; ui/ never imports paramiko directly."""
    offenders = [
        str(p.relative_to(SRC))
        for p in sorted((SRC / "ui").glob("*.py"))
        if any(n == "paramiko" or n.startswith("paramiko.") for n in _imported_modules(p))
    ]
    assert offenders == []
