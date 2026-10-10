"""UI language selection: Bahasa Indonesia (default) or English. No Qt imports (rule A6).

The active texts are the attributes of ``pyssh.strings``. ``set_language`` is called once at
startup, before any window or worker thread exists; a change in Settings applies after a
restart, so the texts never change while the UI is running.
"""

from __future__ import annotations

from types import ModuleType

from pyssh import strings, strings_en

DEFAULT_LANGUAGE = "id"
LANGUAGES = ("id", "en")


def _is_text_name(name: str, value: object) -> bool:
    return name.isupper() and not name.startswith("_") and isinstance(value, str)


def _texts(module: ModuleType) -> dict[str, str]:
    return {name: value for name, value in vars(module).items() if _is_text_name(name, value)}


# Snapshot taken before any ``set_language`` call: ``strings`` still holds Indonesian here.
_TABLES: dict[str, dict[str, str]] = {"id": _texts(strings), "en": _texts(strings_en)}
_current = DEFAULT_LANGUAGE


def normalize_language(value: object) -> str:
    """``value`` if it is a supported language code, otherwise ``DEFAULT_LANGUAGE``."""
    return value if isinstance(value, str) and value in LANGUAGES else DEFAULT_LANGUAGE


def text_names() -> frozenset[str]:
    """Names of all user-visible texts (identical in every language, checked by tests)."""
    return frozenset(_TABLES[DEFAULT_LANGUAGE])


def table(language: str) -> dict[str, str]:
    """A copy of all texts of ``language`` (unsupported codes give the default language)."""
    return dict(_TABLES[normalize_language(language)])


def lookup(language: str, name: str) -> str:
    """Text ``name`` in ``language`` without changing the active language."""
    return _TABLES[normalize_language(language)][name]


def language_name(language: str) -> str:
    """Name of ``language`` written in that language (e.g. "English")."""
    return lookup(language, f"LANGUAGE_NAME_{normalize_language(language).upper()}")


def current_language() -> str:
    """Code of the language whose texts are in ``strings``."""
    return _current


def set_language(language: object) -> str:
    """Put the texts of ``language`` into ``strings``; returns the code actually applied."""
    global _current
    code = normalize_language(language)
    for name, value in _TABLES[code].items():
        setattr(strings, name, value)
    _current = code
    return code
