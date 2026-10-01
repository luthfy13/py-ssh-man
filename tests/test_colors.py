"""Tests for terminal.colors (SPEC §8.2)."""

from __future__ import annotations

import pytest

from pyssh.terminal.colors import ANSI_NAME_TO_INDEX, Theme, resolve_color

T = Theme()


def _fg(value: str, *, bold: bool = False, bright: bool = True) -> str:
    return resolve_color(value, is_fg=True, bold=bold, theme=T, bold_is_bright=bright)


def _bg(value: str, *, bold: bool = False) -> str:
    return resolve_color(value, is_fg=False, bold=bold, theme=T, bold_is_bright=True)


@pytest.mark.parametrize(("name", "index"), sorted(ANSI_NAME_TO_INDEX.items()))
def test_every_ansi_name(name: str, index: int) -> None:
    assert _fg(name) == T.ansi[index]
    assert _bg(name) == T.ansi[index]


def test_pyte_brown_is_yellow() -> None:
    assert _fg("brown") == _fg("yellow") == "#C19C00"
    assert _fg("brightbrown") == "#F9F1A5"


def test_default() -> None:
    assert _fg("default") == T.foreground
    assert _bg("default") == T.background


def test_hex_colors_uppercased() -> None:
    assert _fg("ff0000") == "#FF0000"
    assert _bg("0a0b0c") == "#0A0B0C"


@pytest.mark.parametrize("value", ["", "xyz", "12345", "1234567", "gggggg", "#ff0000"])
def test_unknown_values_fall_back_to_default(value: str) -> None:
    assert _fg(value) == T.foreground
    assert _bg(value) == T.background


def test_bold_is_bright() -> None:
    assert _fg("red", bold=True) == T.ansi[9]
    assert _fg("red", bold=True, bright=False) == T.ansi[1]
    assert _fg("brightred", bold=True) == T.ansi[9]  # already bright
    assert _bg("red", bold=True) == T.ansi[1]  # background never brightened
    assert _fg("ff0000", bold=True) == "#FF0000"


def test_theme_has_16_colors() -> None:
    assert len(T.ansi) == 16
    assert all(c.startswith("#") and len(c) == 7 for c in T.ansi)


def test_every_pyte_color_name_is_known() -> None:
    """Every name pyte can produce resolves to a theme color (Lampiran B check)."""
    from pyte import graphics

    names = set()
    for table in (graphics.FG_ANSI, graphics.BG_ANSI, graphics.FG_AIXTERM, graphics.BG_AIXTERM):
        names.update(table.values())
    names.discard("default")
    assert names <= set(ANSI_NAME_TO_INDEX)
    assert _bg(graphics.BG_AIXTERM[105]) == T.ansi[13]  # pyte spells it "bfightmagenta"
