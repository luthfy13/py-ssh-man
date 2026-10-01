"""Color theme and pyte color resolution (SPEC §8.2). No Qt imports (rule A6)."""

from __future__ import annotations

from dataclasses import dataclass

_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")


@dataclass(frozen=True)
class Theme:
    """Terminal colors as ``#RRGGBB`` strings."""

    background: str = "#0C0C0C"
    foreground: str = "#CCCCCC"
    cursor: str = "#FFFFFF"
    selection: str = "#264F78"
    ansi: tuple[str, ...] = (
        "#0C0C0C", "#C50F1F", "#13A10E", "#C19C00",  # black red green yellow
        "#0037DA", "#881798", "#3A96DD", "#CCCCCC",  # blue magenta cyan white
        "#767676", "#E74856", "#16C60C", "#F9F1A5",  # bright black red green yellow
        "#3B78FF", "#B4009E", "#61D6D6", "#F2F2F2",  # bright blue magenta cyan white
    )  # fmt: skip


ANSI_NAME_TO_INDEX = {
    "black": 0,
    "red": 1,
    "green": 2,
    "brown": 3,
    "yellow": 3,
    "blue": 4,
    "magenta": 5,
    "cyan": 6,
    "white": 7,
    "brightblack": 8,
    "brightred": 9,
    "brightgreen": 10,
    "brightbrown": 11,
    "brightyellow": 11,
    "brightblue": 12,
    "brightmagenta": 13,
    # pyte 0.8.2 misspells SGR 105 (bright magenta background) in graphics.BG_AIXTERM.
    "bfightmagenta": 13,
    "brightcyan": 14,
    "brightwhite": 15,
}


def _is_hex6(value: str) -> bool:
    return len(value) == 6 and all(ch in _HEX_DIGITS for ch in value)


def resolve_color(
    value: str, *, is_fg: bool, bold: bool, theme: Theme, bold_is_bright: bool
) -> str:
    """Translate a pyte color value into ``#RRGGBB`` (rules in SPEC §8.2)."""
    default = theme.foreground if is_fg else theme.background
    if value == "default":
        return default
    index = ANSI_NAME_TO_INDEX.get(value)
    if index is not None:
        if is_fg and bold and bold_is_bright and index < 8:
            index += 8
        return theme.ansi[index]
    if _is_hex6(value):
        return "#" + value.upper()
    return default
