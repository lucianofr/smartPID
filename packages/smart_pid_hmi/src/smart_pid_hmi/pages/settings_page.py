"""SettingsPage — theme selector, connection display, refresh rate."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from smart_pid_hmi.themes.manager import ThemeManager


class SettingsPage(QWidget):
    """Application settings page with theme, connection, and refresh controls."""

    theme_changed = Signal(str)
    refresh_rate_changed = Signal(int)

    def __init__(
        self,
        theme_manager: ThemeManager,
        server_url: str = "http://localhost:8000",
        zmq_url: str = "tcp://localhost:5555",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme_manager = theme_manager

        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Settings")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        # Theme group
        theme_group = QGroupBox("Appearance")
        theme_form = QFormLayout(theme_group)

        self._theme_combo = QComboBox()
        self._theme_combo.setObjectName("theme_combo")
        self._theme_combo.addItems(theme_manager.available_themes())
        # Set current theme
        current_name = theme_manager.current.name
        idx = self._theme_combo.findText(current_name)
        if idx >= 0:
            self._theme_combo.setCurrentIndex(idx)
        self._theme_combo.currentTextChanged.connect(self._on_theme_changed)
        theme_form.addRow("Theme:", self._theme_combo)

        layout.addWidget(theme_group)

        # Connection group
        conn_group = QGroupBox("Connection")
        conn_form = QFormLayout(conn_group)

        server_edit = QLineEdit(server_url)
        server_edit.setReadOnly(True)
        conn_form.addRow("Server URL:", server_edit)

        zmq_edit = QLineEdit(zmq_url)
        zmq_edit.setReadOnly(True)
        conn_form.addRow("ZMQ URL:", zmq_edit)

        layout.addWidget(conn_group)

        # Refresh group
        refresh_group = QGroupBox("Performance")
        refresh_form = QFormLayout(refresh_group)

        self._refresh_spin = QSpinBox()
        self._refresh_spin.setObjectName("refresh_spinbox")
        self._refresh_spin.setRange(16, 5000)
        self._refresh_spin.setValue(33)
        self._refresh_spin.setSuffix(" ms")
        self._refresh_spin.valueChanged.connect(self.refresh_rate_changed)
        refresh_form.addRow("Refresh Rate:", self._refresh_spin)

        layout.addWidget(refresh_group)
        layout.addStretch()

    def _on_theme_changed(self, name: str) -> None:
        self.theme_changed.emit(name)
