"""Tests for terminal.prompt: recognising a shell prompt in one screen line (design B.2/B.5)."""

from __future__ import annotations

import time
from dataclasses import FrozenInstanceError

import pytest

from pyssh.terminal.prompt import PromptSpan, find_prompt


def _parts(text: str) -> dict[str, str]:
    """Role -> the characters of ``text`` covered by that span (``{}`` = not a prompt)."""
    spans = find_prompt(text)
    parts = {span.role: text[span.start : span.end] for span in spans}
    assert len(parts) == len(spans)  # one span per role
    return parts


def _columns(text: str) -> dict[str, tuple[int, int]]:
    """Role -> ``(start, end)`` columns."""
    return {span.role: (span.start, span.end) for span in find_prompt(text)}


def test_span_is_a_frozen_value() -> None:
    span = PromptSpan(0, 4, "userhost")
    assert (span.start, span.end, span.role) == (0, 4, "userhost")
    assert span == PromptSpan(0, 4, "userhost")
    with pytest.raises(FrozenInstanceError):
        span.start = 1  # type: ignore[misc]


def test_proxmox_root_prompt_columns() -> None:
    """The prompt from the bug report: ``root@Server-OBE-UMI:~#``."""
    text = "root@Server-OBE-UMI:~# "
    assert find_prompt(text) == [
        PromptSpan(0, 19, "userhost"),
        PromptSpan(20, 21, "path"),
    ]
    assert text[0:19] == "root@Server-OBE-UMI"
    assert text[20:21] == "~"


@pytest.mark.parametrize(
    ("text", "userhost", "path"),
    [
        # Debian / Ubuntu / Proxmox: user@host:path$ or #
        ("user@host:~$ ", "user@host", "~"),
        ("root@host:~# ", "root@host", "~"),
        ("user@host:/etc$ ", "user@host", "/etc"),
        ("root@host:/etc# ", "root@host", "/etc"),
        ("user@host:~/a/b$ ", "user@host", "~/a/b"),
        ("user@host:/$ ", "user@host", "/"),
        ("user@host:~$ ls -la", "user@host", "~"),
        ("user@host:/var/log# tail -f syslog", "user@host", "/var/log"),
        # RHEL / Fedora / CentOS: [user@host path]$ or #
        ("[user@host ~]$ ", "user@host", "~"),
        ("[root@host ~]# ", "root@host", "~"),
        ("[user@host /etc]$ ", "user@host", "/etc"),
        ("[root@host ~/a/b]# ", "root@host", "~/a/b"),
        ("[user@host ~]$ ls", "user@host", "~"),
        # zsh (macOS default): user@host path %
        ("user@host ~ % ", "user@host", "~"),
        ("user@host /etc % ", "user@host", "/etc"),
        ("user@host ~/a/b % ls -la", "user@host", "~/a/b"),
    ],
)
def test_the_three_prompt_shapes(text: str, userhost: str, path: str) -> None:
    assert _parts(text) == {"userhost": userhost, "path": path}


@pytest.mark.parametrize(
    ("text", "userhost", "path"),
    [
        ("user@host:~$", "user@host", "~"),  # the prompt character ends the line
        ("root@host:/etc#", "root@host", "/etc"),
        ("[user@host ~]$", "user@host", "~"),
        ("user@host ~ %", "user@host", "~"),
    ],
)
def test_prompt_character_may_end_the_line(text: str, userhost: str, path: str) -> None:
    assert _parts(text) == {"userhost": userhost, "path": path}


@pytest.mark.parametrize(
    ("text", "userhost", "path"),
    [
        ("(venv) user@host:~$ ", "user@host", "~"),
        ("(base) root@host:/etc# ", "root@host", "/etc"),
        ("(venv) [user@host ~]$ ", "user@host", "~"),
        ("(base) [root@host ~/a]# ", "root@host", "~/a"),
        ("(venv) user@host ~ % ", "user@host", "~"),
        ("(my-env.3) user@host:~$ ", "user@host", "~"),
    ],
)
def test_environment_prefix(text: str, userhost: str, path: str) -> None:
    assert _parts(text) == {"userhost": userhost, "path": path}


def test_columns_after_environment_prefix() -> None:
    assert _columns("(venv) user@host:~$ ") == {"userhost": (7, 16), "path": (17, 18)}
    assert _columns("(base) [user@host ~]$ ") == {"userhost": (8, 17), "path": (18, 19)}
    assert _columns("(venv) user@host ~ % ") == {"userhost": (7, 16), "path": (17, 18)}


def test_columns_of_each_shape() -> None:
    assert _columns("user@host:~/a/b$ ") == {"userhost": (0, 9), "path": (10, 15)}
    assert _columns("[user@host ~/a]$ ") == {"userhost": (1, 10), "path": (11, 14)}
    assert _columns("user@host /etc % ") == {"userhost": (0, 9), "path": (10, 14)}


@pytest.mark.parametrize(
    ("text", "userhost"),
    [
        ("_svc.acct-1@web-01.example.com:/var/log$ ", "_svc.acct-1@web-01.example.com"),
        ("deploy@10.0.0.5:~$ ", "deploy@10.0.0.5"),
        ("a@b:~$ ", "a@b"),
        ("Admin_2@Server-OBE-UMI:~# ", "Admin_2@Server-OBE-UMI"),
    ],
)
def test_user_and_host_characters(text: str, userhost: str) -> None:
    assert _parts(text)["userhost"] == userhost


@pytest.mark.parametrize(
    "text",
    [
        "",
        " ",
        "hello world",
        "ls -la",
        "$ ",
        "# a comment",
        "Last login: Tue Oct 21 10:00:00 2026 from 192.168.1.5",
        "total 12",
        "drwxr-xr-x 2 root root 4096 Oct 21 10:00 .",
        # a '@' that is not part of a prompt
        "contact me at a@b.com",
        "a@b.com",
        "a@b.com is my address",
        "mail from a@b.com:~$ ",
        "git@github.com: Permission denied (publickey).",
        "ssh user@host",
        "echo user@host:~$ ",
        "ls; user@host:~$ ",
    ],
)
def test_ordinary_text_is_not_a_prompt(text: str) -> None:
    assert find_prompt(text) == []
    assert find_prompt(text.ljust(80)) == []


@pytest.mark.parametrize(
    "text",
    [
        "user@host",  # no ':' / path / prompt character
        "user@host ",
        "user@host:",
        "user@host:~",
        "user@host:~ ",
        "[user@host ~]",
        "[user@host ~] ",
        "user@host ~",
        "user@host ~ ",
        "user@host path",
    ],
)
def test_user_at_host_without_a_prompt_character_is_not_a_prompt(text: str) -> None:
    assert find_prompt(text) == []


@pytest.mark.parametrize(
    "text",
    [
        " user@host:~$ ",  # leading space
        "  [user@host ~]$ ",
        " user@host ~ % ",
        "\tuser@host:~$ ",
        "x user@host:~$ ",  # the prompt must start at column 0
        "> user@host:~$ ",
    ],
)
def test_prompt_must_start_at_column_zero(text: str) -> None:
    assert find_prompt(text) == []


@pytest.mark.parametrize(
    "text",
    [
        "user@host:~$ls",  # nothing separates the prompt character from the next text
        "user@host:~#x",
        "[user@host ~]$ls",
        "[user@host ~]#x",
        "user@host ~ %x",
        "user@host:~$x ",
    ],
)
def test_prompt_character_must_be_followed_by_space_or_end(text: str) -> None:
    assert find_prompt(text) == []


@pytest.mark.parametrize(
    "text",
    [
        "user@host:$ ",  # the path has at least one character
        "user@host:# ",
        "[user@host ]$ ",
        "[user@host]$ ",
        "user@host  % ",
        "user@host % ",
    ],
)
def test_path_has_at_least_one_character(text: str) -> None:
    assert find_prompt(text) == []


@pytest.mark.parametrize(
    "text",
    [
        "1user@host:~$ ",  # a user starts with a letter or '_'
        "-user@host:~$ ",
        ".user@host:~$ ",
        "@host:~$ ",
        "user@:~$ ",
        "user@-host:~$ ",  # a host starts with a letter or digit
        "user@.host:~$ ",
        "us er@host:~$ ",
        "[1user@host ~]$ ",
        "[user@-host ~]$ ",
    ],
)
def test_invalid_user_or_host_is_not_a_prompt(text: str) -> None:
    assert find_prompt(text) == []


@pytest.mark.parametrize(
    "text",
    [
        "user@host:/my dir$ ",  # a path has no spaces
        "(venv)user@host:~$ ",  # the environment prefix is followed by a space
        "(a) (b) user@host:~$ ",  # at most one environment prefix
        "(my env) user@host:~$ ",
        "() user@host:~$ ",
        "(venv user@host:~$ ",
        "{venv} user@host:~$ ",
    ],
)
def test_other_shapes_are_not_prompts(text: str) -> None:
    assert find_prompt(text) == []


def test_full_screen_line_padded_with_blanks() -> None:
    """The widget passes the whole line (one character per column, blanks included)."""
    for text in ("root@host:~# ", "root@host:~#", "[user@host ~]$", "user@host ~ %"):
        assert find_prompt(text.ljust(80)) == find_prompt(text)
        assert find_prompt(text.ljust(80)) != []


def test_prompt_filling_the_whole_line() -> None:
    text = "user@host:~/" + "d" * 67 + "#"
    assert len(text) == 80
    assert _columns(text) == {"userhost": (0, 9), "path": (10, 79)}


def test_wide_characters_in_the_path_keep_columns_exact() -> None:
    # '文' and '档' take two columns each; the stub cell of each is "\0".
    text = "user@host:~/文\0档\0/x$ ls"
    start = text.index("~")
    end = text.index("$")
    assert _columns(text) == {"userhost": (0, 9), "path": (start, end)}
    assert text[start:end] == "~/文\0档\0/x"
    assert end == start + 2 + 4 + 2  # '~/' + two wide characters + '/x'


def test_wide_character_right_before_the_prompt_character() -> None:
    text = "[user@host ~/文\0]$ ".ljust(80)
    assert _parts(text) == {"userhost": "user@host", "path": "~/文\0"}
    assert _columns(text)["path"] == (11, 15)


def test_wide_characters_in_the_environment_prefix_shift_columns() -> None:
    text = "(漢\0字\0) user@host:~$ "
    assert text.index("user") == 7  # '(' + 4 columns + ')' + ' '
    assert _columns(text) == {"userhost": (7, 16), "path": (17, 18)}
    assert _parts(text) == {"userhost": "user@host", "path": "~"}


def test_wide_text_before_the_prompt_character_in_zsh_shape() -> None:
    text = "user@host ~/ü文\0 % "
    assert _parts(text)["path"] == "~/ü文\0"


def test_result_is_a_fresh_list_each_call() -> None:
    first = find_prompt("user@host:~$ ")
    first.clear()
    assert len(find_prompt("user@host:~$ ")) == 2


def test_long_and_pathological_lines_are_handled_quickly() -> None:
    """The function runs for every visible line on every paint; it must not blow up."""
    lines = [
        "@" * 5000,
        "a@" + "a" * 5000,
        "user@host:" + "x" * 5000,
        "(" + "a) " * 2000,
        "[" + "u@h " * 2000,
        "user@host " + "~ " * 2000,
        ("user@host:~ " * 400) + "$x",
    ]
    started = time.perf_counter()
    for line in lines:
        assert find_prompt(line) == []
    assert time.perf_counter() - started < 5.0  # generous: only catches runaway backtracking
