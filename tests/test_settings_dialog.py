"""Tests for ui.settings_dialog (SPEC §9.10)."""

from __future__ import annotations

from dataclasses import replace

import pytest
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QCheckBox, QMessageBox

from pyssh import i18n, strings
from pyssh.ui.settings_dialog import SettingsDialog


@pytest.fixture
def dialog_factory(qtbot, services):
    def make(**kwargs) -> SettingsDialog:
        dialog = SettingsDialog(services.settings_store, **kwargs)
        qtbot.addWidget(dialog)
        return dialog

    return make


def test_defaults_shown(dialog_factory, services) -> None:
    dialog = dialog_factory(mac=False)
    current = services.settings_store.current
    assert dialog.font_auto_check.isChecked()
    assert not dialog.font_combo.isEnabled()
    assert dialog.font_size_spin.value() == current.font_size
    assert (dialog.font_size_spin.minimum(), dialog.font_size_spin.maximum()) == (6, 32)
    assert (dialog.scrollback_spin.minimum(), dialog.scrollback_spin.maximum()) == (100, 100_000)
    assert (dialog.keepalive_spin.minimum(), dialog.keepalive_spin.maximum()) == (0, 600)
    assert (dialog.timeout_spin.minimum(), dialog.timeout_spin.maximum()) == (3, 120)
    assert dialog.option_meta_check.isHidden()
    assert dialog.values() == current


def test_option_as_meta_only_on_mac(dialog_factory) -> None:
    assert not dialog_factory(mac=True).option_meta_check.isHidden()


def _available_monospace(dialog: SettingsDialog) -> str:
    """A monospace family installed on this machine (the combo lists only those)."""
    if dialog.font_combo.count() == 0:
        # Seen on Windows with QT_QPA_PLATFORM=offscreen: Qt's font database is empty there.
        pytest.skip("Qt font database has no monospace fonts on this platform plugin")
    return dialog.font_combo.itemText(0)


def test_save_persists(dialog_factory, services) -> None:
    dialog = dialog_factory(mac=False)
    family = _available_monospace(dialog)
    dialog.font_auto_check.setChecked(False)
    assert dialog.font_combo.isEnabled()
    dialog.font_combo.setCurrentFont(QFont(family))
    dialog.font_size_spin.setValue(14)
    dialog.scrollback_spin.setValue(2000)
    dialog.copy_check.setChecked(False)
    dialog.bold_check.setChecked(False)
    dialog.confirm_check.setChecked(False)
    dialog.keepalive_spin.setValue(0)
    dialog.timeout_spin.setValue(30)
    dialog.save_button.click()
    expected = replace(
        services.settings_store.current,
        font_family=dialog.font_combo.currentFont().family(),
        font_size=14,
        scrollback_lines=2000,
        copy_on_select=False,
        bold_is_bright=False,
        confirm_on_close=False,
        keepalive_seconds=0,
        connect_timeout_seconds=30,
    )
    assert dialog.saved_settings == expected
    assert services.settings_store.load() == expected


def test_existing_font_preselected(dialog_factory, services) -> None:
    family = _available_monospace(dialog_factory(mac=False))
    services.settings_store.save(replace(services.settings_store.current, font_family=family))
    dialog = dialog_factory(mac=False)
    assert not dialog.font_auto_check.isChecked()
    assert dialog.font_combo.currentFont().family() == family


@pytest.fixture
def infos(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Record information boxes instead of showing them (modal boxes would block)."""
    shown: list[tuple[str, str]] = []
    monkeypatch.setattr(QMessageBox, "information", lambda _parent, t, x: shown.append((t, x)))
    return shown


def _languages(dialog: SettingsDialog) -> list[tuple[str, str]]:
    combo = dialog.language_combo
    return [(combo.itemText(i), combo.itemData(i)) for i in range(combo.count())]


def test_language_choices_and_default(dialog_factory) -> None:
    dialog = dialog_factory(mac=False)
    assert _languages(dialog) == [("Bahasa Indonesia", "id"), ("English", "en")]
    assert dialog.language_combo.currentData() == "id"
    assert dialog.values().language == "id"


def test_saved_language_preselected(dialog_factory, services) -> None:
    services.settings_store.save(replace(services.settings_store.current, language="en"))
    assert dialog_factory(mac=False).language_combo.currentData() == "en"


def test_changing_language_saves_and_says_restart_in_new_language(
    dialog_factory, services, infos
) -> None:
    dialog = dialog_factory(mac=False)
    dialog.language_combo.setCurrentIndex(dialog.language_combo.findData("en"))
    dialog.save_button.click()
    assert services.settings_store.load().language == "en"
    assert infos == [("Language", "The new language will be used after PySSH is restarted.")]
    assert i18n.current_language() == "id"  # applies after restart only
    assert strings.MENU_FILE == "&Berkas"


def test_no_restart_message_without_language_change(dialog_factory, infos) -> None:
    dialog = dialog_factory(mac=False)
    dialog.font_size_spin.setValue(15)
    dialog.save_button.click()
    assert infos == []


def test_switching_back_to_running_language_needs_no_restart(
    dialog_factory, services, infos
) -> None:
    services.settings_store.save(replace(services.settings_store.current, language="en"))
    dialog = dialog_factory(mac=False)  # running in Indonesian, English chosen earlier
    dialog.language_combo.setCurrentIndex(dialog.language_combo.findData("id"))
    dialog.save_button.click()
    assert services.settings_store.load().language == "id"
    assert infos == []


def test_restart_message_in_indonesian(dialog_factory, services, infos) -> None:
    i18n.set_language("en")
    services.settings_store.save(replace(services.settings_store.current, language="en"))
    dialog = dialog_factory(mac=False)
    assert dialog.windowTitle() == "Settings"
    dialog.language_combo.setCurrentIndex(dialog.language_combo.findData("id"))
    dialog.save_button.click()
    assert infos == [("Bahasa", "Bahasa baru akan dipakai setelah PySSH dibuka ulang.")]


# ----- highlight_prompt checkbox (design B.4) ----------------------------------------------


def _prompt_check(dialog: SettingsDialog) -> QCheckBox:
    """The "highlight the shell prompt" checkbox, found by its text."""
    found = [
        box
        for box in dialog.findChildren(QCheckBox)
        if box.text() == strings.SETTINGS_HIGHLIGHT_PROMPT
    ]
    assert len(found) == 1
    return found[0]


def test_highlight_prompt_texts_exist_in_both_languages() -> None:
    assert i18n.lookup("id", "SETTINGS_HIGHLIGHT_PROMPT") == "Warnai prompt shell (user@host:path)"
    assert (
        i18n.lookup("en", "SETTINGS_HIGHLIGHT_PROMPT")
        == "Highlight the shell prompt (user@host:path)"
    )
    assert "SETTINGS_HIGHLIGHT_PROMPT" in i18n.text_names()


def test_highlight_prompt_checkbox_defaults_to_checked(dialog_factory, services) -> None:
    dialog = dialog_factory(mac=False)
    box = _prompt_check(dialog)
    assert box.isChecked()
    assert box.text() == "Warnai prompt shell (user@host:path)"
    assert dialog.values().highlight_prompt is True
    assert dialog.values() == services.settings_store.current


def test_highlight_prompt_checkbox_text_in_english(dialog_factory) -> None:
    i18n.set_language("en")
    assert _prompt_check(dialog_factory(mac=False)).text() == (
        "Highlight the shell prompt (user@host:path)"
    )


def test_highlight_prompt_checkbox_sits_between_bold_and_confirm(dialog_factory, qtbot) -> None:
    dialog = dialog_factory(mac=False)
    dialog.show()
    qtbot.waitExposed(dialog)
    box = _prompt_check(dialog)

    def top(widget) -> int:
        return widget.mapTo(dialog, widget.rect().topLeft()).y()

    assert top(dialog.bold_check) < top(box) < top(dialog.confirm_check)


def test_highlight_prompt_unchecked_is_saved(dialog_factory, services) -> None:
    dialog = dialog_factory(mac=False)
    _prompt_check(dialog).setChecked(False)
    assert dialog.values().highlight_prompt is False
    dialog.save_button.click()
    assert dialog.saved_settings is not None
    assert dialog.saved_settings.highlight_prompt is False
    assert services.settings_store.load().highlight_prompt is False
    assert services.settings_store.current.highlight_prompt is False


def test_highlight_prompt_checkbox_changes_nothing_else(dialog_factory, services) -> None:
    before = services.settings_store.current
    dialog = dialog_factory(mac=False)
    _prompt_check(dialog).setChecked(False)
    dialog.save_button.click()
    assert services.settings_store.load() == replace(before, highlight_prompt=False)


def test_saved_highlight_prompt_off_is_preselected(dialog_factory, services) -> None:
    services.settings_store.save(replace(services.settings_store.current, highlight_prompt=False))
    dialog = dialog_factory(mac=False)
    assert not _prompt_check(dialog).isChecked()
    assert dialog.values().highlight_prompt is False


def test_highlight_prompt_can_be_switched_back_on(dialog_factory, services) -> None:
    services.settings_store.save(replace(services.settings_store.current, highlight_prompt=False))
    dialog = dialog_factory(mac=False)
    _prompt_check(dialog).setChecked(True)
    dialog.save_button.click()
    assert services.settings_store.load().highlight_prompt is True


def test_highlight_prompt_checkbox_is_independent_of_bold_checkbox(dialog_factory) -> None:
    dialog = dialog_factory(mac=False)
    dialog.bold_check.setChecked(False)
    assert _prompt_check(dialog).isChecked()
    values = dialog.values()
    assert (values.bold_is_bright, values.highlight_prompt) == (False, True)
