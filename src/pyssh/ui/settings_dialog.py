"""Application settings dialog (SPEC §9.10)."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFontComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pyssh import config, strings
from pyssh.core.settings_store import CLAMP_RANGES, SettingsStore
from pyssh.models import AppSettings


def _spin(name: str, value: int) -> QSpinBox:
    low, high = CLAMP_RANGES[name]
    spin = QSpinBox()
    spin.setRange(low, high)
    spin.setValue(value)
    return spin


class SettingsDialog(QDialog):
    """Edit ``AppSettings``; ``saved_settings`` is set after Save."""

    def __init__(
        self, store: SettingsStore, parent: QWidget | None = None, *, mac: bool = config.IS_MAC
    ) -> None:
        """Build the form from the current settings."""
        super().__init__(parent)
        self._store = store
        self.saved_settings: AppSettings | None = None
        current = store.current
        self.setWindowTitle(strings.SETTINGS_TITLE)

        self.font_auto_check = QCheckBox(strings.SETTINGS_FONT_AUTO)
        self.font_combo = QFontComboBox()
        self.font_combo.setFontFilters(QFontComboBox.FontFilter.MonospacedFonts)
        if current.font_family:
            self.font_combo.setCurrentFont(QFont(current.font_family))
        self.font_auto_check.setChecked(not current.font_family)
        self.font_combo.setEnabled(bool(current.font_family))
        self.font_auto_check.toggled.connect(lambda auto: self.font_combo.setEnabled(not auto))

        self.font_size_spin = _spin("font_size", current.font_size)
        self.scrollback_spin = _spin("scrollback_lines", current.scrollback_lines)
        self.keepalive_spin = _spin("keepalive_seconds", current.keepalive_seconds)
        self.timeout_spin = _spin("connect_timeout_seconds", current.connect_timeout_seconds)
        self.copy_check = QCheckBox(strings.SETTINGS_COPY_ON_SELECT)
        self.copy_check.setChecked(current.copy_on_select)
        self.bold_check = QCheckBox(strings.SETTINGS_BOLD_BRIGHT)
        self.bold_check.setChecked(current.bold_is_bright)
        self.confirm_check = QCheckBox(strings.SETTINGS_CONFIRM_CLOSE)
        self.confirm_check.setChecked(current.confirm_on_close)
        self.option_meta_check = QCheckBox(strings.SETTINGS_OPTION_META)
        self.option_meta_check.setChecked(current.mac_option_as_meta)
        self.option_meta_check.setVisible(mac)

        font_row = QHBoxLayout()
        font_row.addWidget(self.font_combo, 1)
        font_row.addWidget(self.font_auto_check)
        form = QFormLayout()
        form.addRow(strings.SETTINGS_FONT, font_row)
        form.addRow(strings.SETTINGS_FONT_SIZE, self.font_size_spin)
        form.addRow(strings.SETTINGS_SCROLLBACK, self.scrollback_spin)
        form.addRow("", self.copy_check)
        form.addRow("", self.bold_check)
        form.addRow("", self.confirm_check)
        form.addRow(strings.SETTINGS_KEEPALIVE, self.keepalive_spin)
        form.addRow(strings.SETTINGS_TIMEOUT, self.timeout_spin)
        form.addRow("", self.option_meta_check)

        note = QLabel(strings.SETTINGS_NOTE)
        note.setWordWrap(True)
        buttons = QDialogButtonBox()
        self.save_button = buttons.addButton(
            strings.BUTTON_SAVE, QDialogButtonBox.ButtonRole.AcceptRole
        )
        buttons.addButton(strings.BUTTON_CANCEL, QDialogButtonBox.ButtonRole.RejectRole)
        self.save_button.clicked.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addWidget(buttons)

    def values(self) -> AppSettings:
        """Settings as currently entered (window state fields unchanged)."""
        family = "" if self.font_auto_check.isChecked() else self.font_combo.currentFont().family()
        return replace(
            self._store.current,
            font_family=family,
            font_size=self.font_size_spin.value(),
            scrollback_lines=self.scrollback_spin.value(),
            copy_on_select=self.copy_check.isChecked(),
            bold_is_bright=self.bold_check.isChecked(),
            confirm_on_close=self.confirm_check.isChecked(),
            keepalive_seconds=self.keepalive_spin.value(),
            connect_timeout_seconds=self.timeout_spin.value(),
            mac_option_as_meta=self.option_meta_check.isChecked(),
        )

    def _save(self) -> None:
        settings = self.values()
        self._store.save(settings)
        self.saved_settings = settings
        self.accept()
