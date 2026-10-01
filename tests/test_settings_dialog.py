"""Tests for ui.settings_dialog (SPEC §9.10)."""

from __future__ import annotations

from dataclasses import replace

import pytest
from PySide6.QtGui import QFont

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


def test_save_persists(dialog_factory, services) -> None:
    dialog = dialog_factory(mac=False)
    dialog.font_auto_check.setChecked(False)
    assert dialog.font_combo.isEnabled()
    dialog.font_combo.setCurrentFont(QFont("DejaVu Sans Mono"))
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
        font_family="DejaVu Sans Mono",
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
    services.settings_store.save(
        replace(services.settings_store.current, font_family="DejaVu Sans Mono")
    )
    dialog = dialog_factory(mac=False)
    assert not dialog.font_auto_check.isChecked()
    assert dialog.font_combo.currentFont().family() == "DejaVu Sans Mono"
