"""Tests for i18n and the English texts in strings_en."""

from __future__ import annotations

import re
import string

import pytest

from pyssh import i18n, strings, strings_en

ID = i18n.table("id")
EN = i18n.table("en")

# Texts that are the same in both languages (loanwords, names, pure placeholders).
SAME_IN_BOTH = {
    "AUTH_KEY",
    "AUTH_PASSWORD",
    "BUTTON_EDIT",
    "BUTTON_OK",
    "DEMO_TAB_TITLE",
    "FIELD_HOST",
    "FIELD_PASSPHRASE",
    "FIELD_PASSWORD",
    "FIELD_PORT",
    "FIELD_USERNAME",
    "GRID_SIZE",
    "HOSTKEY_FINGERPRINT",
    "LANGUAGE_NAME_EN",
    "LANGUAGE_NAME_ID",
    "MENU_EDIT",
    "PASSPHRASE_FIELD",
    "PASSPHRASE_TITLE",
    "PASSWORD_FIELD",
    "PASSWORD_TITLE",
    "SETTINGS_FONT",
    "STATUS_LINE",
    "VAULT_FIELD_PASSWORD",
    "VAULT_STATUS",
    "VERSION_LINE",
}

# Common Indonesian words that must not appear in English texts.
INDONESIAN_WORDS = re.compile(
    r"\b(yang|tidak|dan|untuk|atau|ke|di|dari|dengan|akan|belum|sudah|harus|bisa|ini|itu|"
    r"sesi|simpan|buka|tutup|hapus|salin|tempel|klik|tekan|berkas|bantuan|pengaturan|kunci|"
    r"koneksi|terhubung|terputus|gagal|lupa|lama|baru|salah|coba|lagi|berlaku|setelah|ulang|"
    r"detik|karakter|wajib|diisi|tersimpan|silakan|keluar|batal|lewati|ganti|buat)\b",
    re.IGNORECASE,
)


def _fields(text: str) -> list[tuple[str, str, str]]:
    return sorted(
        (name, spec or "", conv or "")
        for _, name, spec, conv in string.Formatter().parse(text)
        if name is not None
    )


def _mnemonics(text: str) -> int:
    return len(re.findall(r"(?<!&)&(?!&)", text.replace("&&", "")))


def test_both_languages_define_the_same_texts() -> None:
    assert set(EN) == set(ID) == i18n.text_names()
    assert len(ID) > 150
    public = {n for n in vars(strings_en) if n.isupper() and not n.startswith("_")}
    assert public == set(EN)  # nothing in strings_en that is not a text


def test_placeholders_match() -> None:
    assert [n for n in sorted(ID) if _fields(EN[n]) != _fields(ID[n])] == []


def test_ampersands_match() -> None:
    """Qt mnemonics (``&F``) and escaped ``&&`` must exist in both languages or neither."""
    mismatched = [
        n
        for n in sorted(ID)
        if _mnemonics(EN[n]) != _mnemonics(ID[n]) or EN[n].count("&&") != ID[n].count("&&")
    ]
    assert mismatched == []


@pytest.mark.parametrize("language", i18n.LANGUAGES)
def test_menu_mnemonics_are_unique(language: str) -> None:
    table = i18n.table(language)
    menus = [table[n] for n in ("MENU_FILE", "MENU_SESSION", "MENU_VIEW", "MENU_HELP")]
    letters = [re.search(r"&(\w)", menu).group(1).lower() for menu in menus]
    assert len(set(letters)) == len(letters)


def test_english_texts_are_translated() -> None:
    assert {n for n in ID if EN[n] == ID[n]} == SAME_IN_BOTH


def test_english_texts_have_no_indonesian_words() -> None:
    found = {
        n: match.group(0)
        for n in sorted(set(EN) - {"LANGUAGE_NAME_ID"})
        if (match := INDONESIAN_WORDS.search(EN[n]))
    }
    assert found == {}


def test_word_check_detects_indonesian() -> None:
    """The check above is not vacuous: it flags the Indonesian texts."""
    flagged = [n for n in ID if INDONESIAN_WORDS.search(ID[n])]
    assert len(flagged) > len(ID) // 2


def test_language_names_are_written_in_their_own_language() -> None:
    assert i18n.language_name("id") == "Bahasa Indonesia"
    assert i18n.language_name("en") == "English"
    for name in ("LANGUAGE_NAME_ID", "LANGUAGE_NAME_EN"):
        assert ID[name] == EN[name]


def test_default_is_indonesian() -> None:
    assert i18n.DEFAULT_LANGUAGE == "id"
    assert i18n.current_language() == "id"
    assert strings.MENU_FILE == "&Berkas"


def test_set_language_switches_and_restores() -> None:
    assert i18n.set_language("en") == "en"
    assert i18n.current_language() == "en"
    assert {n: getattr(strings, n) for n in EN} == EN
    assert i18n.set_language("id") == "id"
    assert {n: getattr(strings, n) for n in ID} == ID


@pytest.mark.parametrize("value", ["fr", "EN", "", None, 1, ["en"]])
def test_unsupported_language_gives_default(value: object) -> None:
    assert i18n.normalize_language(value) == "id"
    i18n.set_language("en")
    assert i18n.set_language(value) == "id"
    assert strings.MENU_FILE == "&Berkas"


def test_lookup_and_table_do_not_switch() -> None:
    assert i18n.lookup("en", "MENU_FILE") == "&File"
    assert strings.MENU_FILE == "&Berkas"
    i18n.set_language("en")
    assert i18n.lookup("id", "MENU_FILE") == "&Berkas"  # tables are not changed by switching
    copy = i18n.table("en")
    copy["MENU_FILE"] = "x"
    assert i18n.lookup("en", "MENU_FILE") == "&File"
