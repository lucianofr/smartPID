"""SettingsPage — theme selector, connection display, refresh rate.

Apply/Cancel pattern: edits are buffered until the user clicks Apply.
Reconnect remains an immediate action (not buffered).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from smart_pid_hmi.themes.base import ThemeBase
    from smart_pid_hmi.themes.manager import ThemeManager


class SettingsPage(QWidget):
    """Application settings page with theme, connection, and refresh controls.

    Changes are buffered — nothing is emitted until Apply is clicked.
    Cancel reverts all fields to their last committed state.
    """

    theme_changed = Signal(str)
    refresh_rate_changed = Signal(int)
    opcua_reconnect_requested = Signal(str)  # (endpoint_url)

    # Project signals (immediate — not affected by Apply/Cancel)
    project_changed = Signal(str, str)  # (name, path)
    project_new_requested = Signal(str, str)  # (name, path)
    project_open_requested = Signal(str)  # (path)
    project_save_as_requested = Signal(str)  # (path)

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

        # --- Project group (at top, before Appearance) ---
        project_group = QGroupBox("Project")
        project_group.setObjectName("project_group")
        project_form = QFormLayout(project_group)

        self._project_name = QLabel("(none)")
        self._project_name.setObjectName("project_name")
        project_form.addRow("Name:", self._project_name)

        self._project_path = QLabel("(none)")
        self._project_path.setObjectName("project_path")
        project_form.addRow("Path:", self._project_path)

        self._project_count = QLabel("0")
        self._project_count.setObjectName("project_count")
        project_form.addRow("Controllers:", self._project_count)

        proj_btn_row = QHBoxLayout()
        self._project_new_btn = QPushButton("New")
        self._project_new_btn.setObjectName("project_new_btn")
        self._project_new_btn.clicked.connect(self._on_project_new)
        proj_btn_row.addWidget(self._project_new_btn)

        self._project_open_btn = QPushButton("Open")
        self._project_open_btn.setObjectName("project_open_btn")
        self._project_open_btn.clicked.connect(self._on_project_open)
        proj_btn_row.addWidget(self._project_open_btn)

        self._project_save_as_btn = QPushButton("Save As")
        self._project_save_as_btn.setObjectName("project_save_as_btn")
        self._project_save_as_btn.clicked.connect(self._on_project_save_as)
        proj_btn_row.addWidget(self._project_save_as_btn)

        proj_btn_row.addStretch()
        project_form.addRow(proj_btn_row)

        layout.addWidget(project_group)

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
        refresh_form.addRow("Refresh Rate:", self._refresh_spin)

        layout.addWidget(refresh_group)

        # OPC-UA group (Gap #46)
        opcua_group = QGroupBox("OPC-UA Server")
        opcua_form = QFormLayout(opcua_group)

        self._opcua_endpoint = QLineEdit("opc.tcp://localhost:4840")
        self._opcua_endpoint.setObjectName("opcua_endpoint")
        opcua_form.addRow("Endpoint URL:", self._opcua_endpoint)

        status_row = QHBoxLayout()
        self._opcua_status = QLabel("Unknown")
        self._opcua_status.setObjectName("opcua_status")
        self._opcua_status.setStyleSheet(
            "color: #888; font-weight: bold; padding: 2px 8px;"
        )
        status_row.addWidget(self._opcua_status)

        self._opcua_reconnect_btn = QPushButton("Reconnect")
        self._opcua_reconnect_btn.setObjectName("opcua_reconnect_btn")
        self._opcua_reconnect_btn.clicked.connect(self._on_opcua_reconnect)
        status_row.addWidget(self._opcua_reconnect_btn)
        status_row.addStretch()

        opcua_form.addRow("Status:", status_row)
        layout.addWidget(opcua_group)

        # --- Apply / Cancel buttons ---
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._apply_btn = QPushButton("Apply")
        self._apply_btn.setObjectName("apply_btn")
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._on_apply)
        btn_row.addWidget(self._apply_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("cancel_btn")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._cancel_btn)

        layout.addLayout(btn_row)
        layout.addStretch()

        # --- Committed state (snapshot of last-applied values) ---
        self._committed_theme_idx: int = self._theme_combo.currentIndex()
        self._committed_refresh: int = self._refresh_spin.value()
        self._committed_opcua_url: str = self._opcua_endpoint.text()

        # --- Connect field-change signals to enable Apply/Cancel ---
        self._theme_combo.currentIndexChanged.connect(self._on_field_changed)
        self._refresh_spin.valueChanged.connect(self._on_field_changed)
        self._opcua_endpoint.textChanged.connect(self._on_field_changed)

    def set_opcua_endpoint(self, url: str) -> None:
        """Set the OPC-UA endpoint URL externally."""
        self._opcua_endpoint.setText(url)

    def set_opcua_status(self, connected: bool) -> None:
        """Update the OPC-UA connection status indicator."""
        if connected:
            self._opcua_status.setText("Connected")
            self._opcua_status.setStyleSheet(
                "color: #4CAF50; font-weight: bold; padding: 2px 8px;"
            )
        else:
            self._opcua_status.setText("Disconnected")
            self._opcua_status.setStyleSheet(
                "color: #F44336; font-weight: bold; padding: 2px 8px;"
            )

    # --- Apply / Cancel logic ---------------------------------------------------

    def _on_field_changed(self) -> None:
        """Enable or disable Apply/Cancel based on pending changes."""
        has_changes = self.has_unsaved_changes()
        self._apply_btn.setEnabled(has_changes)
        self._cancel_btn.setEnabled(has_changes)

    def has_unsaved_changes(self) -> bool:
        """Return True if any field differs from committed state."""
        if self._theme_combo.currentIndex() != self._committed_theme_idx:
            return True
        if self._refresh_spin.value() != self._committed_refresh:
            return True
        return self._opcua_endpoint.text() != self._committed_opcua_url

    def _on_apply(self) -> None:
        """Emit signals for changed values, update committed state, disable buttons."""
        # Emit only for fields that actually changed
        if self._theme_combo.currentIndex() != self._committed_theme_idx:
            self.theme_changed.emit(self._theme_combo.currentText())
        if self._refresh_spin.value() != self._committed_refresh:
            self.refresh_rate_changed.emit(self._refresh_spin.value())
        if self._opcua_endpoint.text() != self._committed_opcua_url:
            self.opcua_reconnect_requested.emit(self._opcua_endpoint.text())

        # Update committed state
        self._committed_theme_idx = self._theme_combo.currentIndex()
        self._committed_refresh = self._refresh_spin.value()
        self._committed_opcua_url = self._opcua_endpoint.text()

        self._apply_btn.setEnabled(False)
        self._cancel_btn.setEnabled(False)

    def _on_cancel(self) -> None:
        """Revert all fields to committed state and disable buttons."""
        # Block signals during revert to avoid re-triggering _on_field_changed
        self._theme_combo.blockSignals(True)
        self._refresh_spin.blockSignals(True)
        self._opcua_endpoint.blockSignals(True)

        self._theme_combo.setCurrentIndex(self._committed_theme_idx)
        self._refresh_spin.setValue(self._committed_refresh)
        self._opcua_endpoint.setText(self._committed_opcua_url)

        self._theme_combo.blockSignals(False)
        self._refresh_spin.blockSignals(False)
        self._opcua_endpoint.blockSignals(False)

        self._apply_btn.setEnabled(False)
        self._cancel_btn.setEnabled(False)

    # --- Immediate actions -----------------------------------------------------

    def _on_opcua_reconnect(self) -> None:
        url = self._opcua_endpoint.text().strip()
        if url:
            self.opcua_reconnect_requested.emit(url)

    # --- Project actions (immediate — not buffered) ----------------------------

    def update_project_info(self, name: str, path: str, count: int) -> None:
        """Update the project information labels."""
        self._project_name.setText(name)
        self._project_path.setText(path)
        self._project_count.setText(str(count))

    def _on_project_new(self) -> None:
        name, ok = QInputDialog.getText(self, "New Project", "Project name:")
        if not ok or not name.strip():
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save New Project", "", "SmartPID Files (*.spid)"
        )
        if path:
            self.project_new_requested.emit(name.strip(), path)

    def _on_project_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", "SmartPID Files (*.spid)"
        )
        if path:
            self.project_open_requested.emit(path)

    def _on_project_save_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project As", "", "SmartPID Files (*.spid)"
        )
        if path:
            self.project_save_as_requested.emit(path)

    def apply_theme(self, theme: ThemeBase) -> None:
        """Update styles for dynamic theme switching."""
        self.setStyleSheet(
            f"QGroupBox {{ color: {theme.fg_primary}; "
            f"font-weight: bold; border: 1px solid {theme.border}; "
            f"border-radius: 4px; margin-top: 8px; padding-top: 16px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 8px; }}"
            f"QLabel {{ color: {theme.fg_primary}; }}"
        )
