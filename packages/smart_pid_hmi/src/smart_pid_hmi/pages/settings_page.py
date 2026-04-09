"""SettingsPage — theme selector, connection display, refresh rate, AI config.

Apply/Cancel pattern: edits are buffered until the user clicks Apply.
Reconnect remains an immediate action (not buffered).

Layout: two-column — existing groups on the left, AI groups on the right.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from smart_pid_hmi.themes.base import ThemeBase
    from smart_pid_hmi.themes.manager import ThemeManager


class SettingsPage(QWidget):
    """Application settings page with theme, connection, refresh, and AI controls.

    Changes are buffered — nothing is emitted until Apply is clicked.
    Cancel reverts all fields to their last committed state.
    """

    theme_changed = Signal(str)
    refresh_rate_changed = Signal(int)
    opcua_connect_requested = Signal(str)  # (endpoint_url)
    opcua_disconnect_requested = Signal()
    opcua_endpoint_save_requested = Signal(str)  # emitted on Apply when endpoint changed
    ai_settings_changed = Signal(dict)  # emitted on Apply when AI settings changed

    # Project signals (immediate — not affected by Apply/Cancel)
    project_changed = Signal(str, str)  # (name, path)
    project_new_requested = Signal()  # open Welcome Dialog
    project_open_requested = Signal()  # open Welcome Dialog
    project_download_requested = Signal()
    project_import_requested = Signal()

    def __init__(
        self,
        theme_manager: ThemeManager,
        server_url: str = "http://localhost:8000",
        zmq_url: str = "tcp://localhost:5555",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme_manager = theme_manager

        root_layout = QVBoxLayout(self)

        # Title
        title = QLabel("Settings")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        root_layout.addWidget(title)

        # --- Two-column layout ---
        columns_layout = QHBoxLayout()

        # LEFT COLUMN — existing settings
        self._left_column = QWidget()
        left_layout = QVBoxLayout(self._left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self._build_project_group(left_layout)
        self._build_appearance_group(left_layout, theme_manager)
        self._build_connection_group(left_layout, server_url, zmq_url)
        self._build_performance_group(left_layout)
        self._build_opcua_group(left_layout)
        left_layout.addStretch()

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setWidget(self._left_column)
        left_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        columns_layout.addWidget(left_scroll, stretch=1)

        # RIGHT COLUMN — AI settings
        self._right_column = QWidget()
        right_layout = QVBoxLayout(self._right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self._build_fuzzy_group(right_layout)
        self._build_rl_group(right_layout)
        right_layout.addStretch()

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setWidget(self._right_column)
        right_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        columns_layout.addWidget(right_scroll, stretch=1)

        root_layout.addLayout(columns_layout, stretch=1)

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

        root_layout.addLayout(btn_row)

        # --- Committed state (snapshot of last-applied values) ---
        self._committed_theme_idx: int = self._theme_combo.currentIndex()
        self._committed_refresh: int = self._refresh_spin.value()
        self._committed_opcua_url: str = self._opcua_endpoint.text()
        self._committed_ai_settings: dict = self.get_ai_settings()

        # --- Connect field-change signals to enable Apply/Cancel ---
        self._theme_combo.currentIndexChanged.connect(self._on_field_changed)
        self._refresh_spin.valueChanged.connect(self._on_field_changed)
        self._opcua_endpoint.textChanged.connect(self._on_field_changed)
        # AI fields
        self._fuzzy_speed_factor.valueChanged.connect(self._on_field_changed)
        self._fuzzy_limit_min.valueChanged.connect(self._on_field_changed)
        self._fuzzy_limit_max.valueChanged.connect(self._on_field_changed)
        self._fuzzy_dead_time.valueChanged.connect(self._on_field_changed)
        self._rl_fallback_kp.valueChanged.connect(self._on_field_changed)
        self._rl_fallback_kd.valueChanged.connect(self._on_field_changed)
        self._rl_learning_rate.valueChanged.connect(self._on_field_changed)
        self._rl_train_interval.valueChanged.connect(self._on_field_changed)

    # ── Left column group builders ─────────────────────────────────────

    def _build_project_group(self, layout: QVBoxLayout) -> None:
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
        self._project_new_btn.clicked.connect(lambda: self.project_new_requested.emit())
        proj_btn_row.addWidget(self._project_new_btn)

        self._project_open_btn = QPushButton("Open")
        self._project_open_btn.setObjectName("project_open_btn")
        self._project_open_btn.clicked.connect(lambda: self.project_open_requested.emit())
        proj_btn_row.addWidget(self._project_open_btn)

        self._project_download_btn = QPushButton("Download")
        self._project_download_btn.setObjectName("project_download_btn")
        self._project_download_btn.clicked.connect(
            lambda: self.project_download_requested.emit()
        )
        proj_btn_row.addWidget(self._project_download_btn)

        proj_btn_row2 = QHBoxLayout()
        self._project_import_btn = QPushButton("Import")
        self._project_import_btn.setObjectName("project_import_btn")
        self._project_import_btn.clicked.connect(
            lambda: self.project_import_requested.emit()
        )
        proj_btn_row2.addWidget(self._project_import_btn)
        proj_btn_row2.addStretch()

        proj_btn_row.addStretch()
        project_form.addRow(proj_btn_row)
        project_form.addRow(proj_btn_row2)

        layout.addWidget(project_group)

    def _build_appearance_group(
        self, layout: QVBoxLayout, theme_manager: ThemeManager
    ) -> None:
        theme_group = QGroupBox("Appearance")
        theme_form = QFormLayout(theme_group)

        self._theme_combo = QComboBox()
        self._theme_combo.setObjectName("theme_combo")
        self._theme_combo.addItems(theme_manager.available_themes())
        current_name = theme_manager.current.name
        idx = self._theme_combo.findText(current_name)
        if idx >= 0:
            self._theme_combo.setCurrentIndex(idx)
        theme_form.addRow("Theme:", self._theme_combo)

        layout.addWidget(theme_group)

    def _build_connection_group(
        self, layout: QVBoxLayout, server_url: str, zmq_url: str
    ) -> None:
        conn_group = QGroupBox("Connection")
        conn_form = QFormLayout(conn_group)

        server_edit = QLineEdit(server_url)
        server_edit.setReadOnly(True)
        conn_form.addRow("Server URL:", server_edit)

        zmq_edit = QLineEdit(zmq_url)
        zmq_edit.setReadOnly(True)
        conn_form.addRow("ZMQ URL:", zmq_edit)

        layout.addWidget(conn_group)

    def _build_performance_group(self, layout: QVBoxLayout) -> None:
        refresh_group = QGroupBox("Performance")
        refresh_form = QFormLayout(refresh_group)

        self._refresh_spin = QSpinBox()
        self._refresh_spin.setObjectName("refresh_spinbox")
        self._refresh_spin.setRange(16, 5000)
        self._refresh_spin.setValue(33)
        self._refresh_spin.setSuffix(" ms")
        refresh_form.addRow("Refresh Rate:", self._refresh_spin)

        layout.addWidget(refresh_group)

    def _build_opcua_group(self, layout: QVBoxLayout) -> None:
        opcua_group = QGroupBox("OPC-UA Server")
        opcua_form = QFormLayout(opcua_group)

        self._opcua_endpoint = QLineEdit("opc.tcp://localhost:4840")
        self._opcua_endpoint.setObjectName("opcua_endpoint")
        opcua_form.addRow("Endpoint URL:", self._opcua_endpoint)

        status_row = QHBoxLayout()
        self._opcua_status = QLabel("Disconnected")
        self._opcua_status.setObjectName("opcua_status")
        self._opcua_status.setStyleSheet(
            "color: #F44336; font-weight: bold; padding: 2px 8px;"
        )
        status_row.addWidget(self._opcua_status)

        self._opcua_connect_btn = QPushButton("Connect")
        self._opcua_connect_btn.setObjectName("opcua_connect_btn")
        self._opcua_connect_btn.clicked.connect(self._on_opcua_connect)
        status_row.addWidget(self._opcua_connect_btn)

        self._opcua_disconnect_btn = QPushButton("Disconnect")
        self._opcua_disconnect_btn.setObjectName("opcua_disconnect_btn")
        self._opcua_disconnect_btn.setEnabled(False)
        self._opcua_disconnect_btn.clicked.connect(self._on_opcua_disconnect)
        status_row.addWidget(self._opcua_disconnect_btn)
        status_row.addStretch()

        opcua_form.addRow("Status:", status_row)
        layout.addWidget(opcua_group)

    # ── Right column group builders (AI) ───────────────────────────────

    def _build_fuzzy_group(self, layout: QVBoxLayout) -> None:
        group = QGroupBox("Fuzzy Engine")
        form = QFormLayout(group)

        self._fuzzy_speed_factor = QDoubleSpinBox()
        self._fuzzy_speed_factor.setObjectName("fuzzy_speed_factor")
        self._fuzzy_speed_factor.setRange(0.001, 1.0)
        self._fuzzy_speed_factor.setDecimals(3)
        self._fuzzy_speed_factor.setSingleStep(0.01)
        self._fuzzy_speed_factor.setValue(0.15)
        self._fuzzy_speed_factor.setToolTip(
            "Speed Factor (Sv) — AI tuning aggressiveness multiplier.\n"
            "Higher values make Ki/Ti adjustments bolder per cycle.\n"
            "Formula: Ki_new = Ki × (1 + gamma × Sv)\n"
            "Typical: 0.04 (slow) to 0.30 (ultra-fast processes)"
        )
        form.addRow("Speed Factor (Sv):", self._fuzzy_speed_factor)

        self._fuzzy_limit_min = QDoubleSpinBox()
        self._fuzzy_limit_min.setObjectName("fuzzy_limit_min")
        self._fuzzy_limit_min.setRange(0.001, 1000.0)
        self._fuzzy_limit_min.setDecimals(3)
        self._fuzzy_limit_min.setSingleStep(0.1)
        self._fuzzy_limit_min.setValue(0.1)
        self._fuzzy_limit_min.setToolTip(
            "Minimum clamp for Ki/Ti value.\n"
            "The AI engine will never reduce the integral parameter below this limit.\n"
            "Prevents the controller from becoming too sluggish."
        )
        form.addRow("Limit Min:", self._fuzzy_limit_min)

        self._fuzzy_limit_max = QDoubleSpinBox()
        self._fuzzy_limit_max.setObjectName("fuzzy_limit_max")
        self._fuzzy_limit_max.setRange(0.1, 10000.0)
        self._fuzzy_limit_max.setDecimals(1)
        self._fuzzy_limit_max.setSingleStep(1.0)
        self._fuzzy_limit_max.setValue(100.0)
        self._fuzzy_limit_max.setToolTip(
            "Maximum clamp for Ki/Ti value.\n"
            "The AI engine will never increase the integral parameter above this limit.\n"
            "Prevents the controller from becoming too aggressive or unstable."
        )
        form.addRow("Limit Max:", self._fuzzy_limit_max)

        self._fuzzy_dead_time = QDoubleSpinBox()
        self._fuzzy_dead_time.setObjectName("fuzzy_dead_time")
        self._fuzzy_dead_time.setRange(0.1, 3600.0)
        self._fuzzy_dead_time.setDecimals(1)
        self._fuzzy_dead_time.setSingleStep(0.5)
        self._fuzzy_dead_time.setValue(1.0)
        self._fuzzy_dead_time.setSuffix(" s")
        self._fuzzy_dead_time.setToolTip(
            "Estimated process dead time (L) in seconds.\n"
            "Used to calculate the AI optimization cycle period.\n"
            "Larger dead times require longer observation windows."
        )
        form.addRow("Dead Time (L):", self._fuzzy_dead_time)

        layout.addWidget(group)

    def _build_rl_group(self, layout: QVBoxLayout) -> None:
        group = QGroupBox("RL Engine")
        form = QFormLayout(group)

        self._rl_fallback_kp = QDoubleSpinBox()
        self._rl_fallback_kp.setObjectName("rl_fallback_kp")
        self._rl_fallback_kp.setRange(0.01, 5.0)
        self._rl_fallback_kp.setDecimals(2)
        self._rl_fallback_kp.setSingleStep(0.05)
        self._rl_fallback_kp.setValue(0.5)
        self._rl_fallback_kp.setToolTip(
            "Policy Gain — proportional sensitivity of the fallback RL policy.\n"
            "Controls how strongly the error influences the gamma (Ki/Ti adjustment factor).\n"
            "Used when stable-baselines3 is not available or the RL model is untrained.\n"
            "Higher = more aggressive Ki/Ti corrections per error unit."
        )
        form.addRow("Policy Gain:", self._rl_fallback_kp)

        self._rl_fallback_kd = QDoubleSpinBox()
        self._rl_fallback_kd.setObjectName("rl_fallback_kd")
        self._rl_fallback_kd.setRange(0.0, 5.0)
        self._rl_fallback_kd.setDecimals(2)
        self._rl_fallback_kd.setSingleStep(0.05)
        self._rl_fallback_kd.setValue(0.2)
        self._rl_fallback_kd.setToolTip(
            "Policy Damping — derivative sensitivity of the fallback RL policy.\n"
            "Controls how strongly the error rate of change influences gamma.\n"
            "Used when stable-baselines3 is not available or the RL model is untrained.\n"
            "Higher = more damping, reduces oscillation in Ki/Ti adjustments."
        )
        form.addRow("Policy Damping:", self._rl_fallback_kd)

        self._rl_learning_rate = QDoubleSpinBox()
        self._rl_learning_rate.setObjectName("rl_learning_rate")
        self._rl_learning_rate.setRange(1e-6, 0.1)
        self._rl_learning_rate.setDecimals(6)
        self._rl_learning_rate.setSingleStep(1e-4)
        self._rl_learning_rate.setValue(3e-4)
        self._rl_learning_rate.setToolTip(
            "Learning rate for the RL neural network optimizer (Adam).\n"
            "Lower values = more stable but slower learning.\n"
            "Higher values = faster adaptation but risk of instability.\n"
            "Default: 3×10⁻⁴ (stable-baselines3 default)"
        )
        form.addRow("Learning Rate:", self._rl_learning_rate)

        self._rl_train_interval = QSpinBox()
        self._rl_train_interval.setObjectName("rl_train_interval")
        self._rl_train_interval.setRange(1, 1000)
        self._rl_train_interval.setSingleStep(8)
        self._rl_train_interval.setValue(32)
        self._rl_train_interval.setToolTip(
            "Online training interval — train the RL model every N AI steps.\n"
            "Lower values = more frequent training updates (more CPU).\n"
            "Higher values = less frequent but more stable training."
        )
        form.addRow("Train Interval:", self._rl_train_interval)

        layout.addWidget(group)

    # ── OPC-UA status helpers ──────────────────────────────────────────

    def set_opcua_endpoint(self, url: str) -> None:
        """Set the OPC-UA endpoint URL externally."""
        self._opcua_endpoint.setText(url)

    def set_opcua_status(self, connected: bool) -> None:
        """Update the OPC-UA connection status indicator and button states."""
        if connected:
            self._opcua_status.setText("Connected")
            self._opcua_status.setStyleSheet(
                "color: #4CAF50; font-weight: bold; padding: 2px 8px;"
            )
            self._opcua_connect_btn.setEnabled(False)
            self._opcua_disconnect_btn.setEnabled(True)
        else:
            self._opcua_status.setText("Disconnected")
            self._opcua_status.setStyleSheet(
                "color: #F44336; font-weight: bold; padding: 2px 8px;"
            )
            self._opcua_connect_btn.setEnabled(True)
            self._opcua_disconnect_btn.setEnabled(False)

    def set_opcua_connecting(self) -> None:
        """Show connecting state while waiting for backend response."""
        self._opcua_status.setText("Connecting...")
        self._opcua_status.setStyleSheet(
            "color: #FFC107; font-weight: bold; padding: 2px 8px;"
        )
        self._opcua_connect_btn.setEnabled(False)
        self._opcua_disconnect_btn.setEnabled(False)

    def set_opcua_endpoint_and_status(self, url: str, connected: bool) -> None:
        """Bulk update endpoint + status for initial sync. Updates committed state."""
        self._opcua_endpoint.blockSignals(True)
        self._opcua_endpoint.setText(url)
        self._opcua_endpoint.blockSignals(False)
        self._committed_opcua_url = url
        self.set_opcua_status(connected)

    # ── AI settings helpers ────────────────────────────────────────────

    def load_ai_settings(self, settings: dict) -> None:
        """Populate AI fields from a dict (e.g. loaded from controller config)."""
        # Block signals during bulk load
        widgets = [
            self._fuzzy_speed_factor, self._fuzzy_limit_min, self._fuzzy_limit_max,
            self._fuzzy_dead_time, self._rl_fallback_kp, self._rl_fallback_kd,
            self._rl_learning_rate, self._rl_train_interval,
        ]
        for w in widgets:
            w.blockSignals(True)

        if "speed_factor" in settings:
            self._fuzzy_speed_factor.setValue(settings["speed_factor"])
        if "limit_min" in settings:
            self._fuzzy_limit_min.setValue(settings["limit_min"])
        if "limit_max" in settings:
            self._fuzzy_limit_max.setValue(settings["limit_max"])
        if "dead_time_l" in settings:
            self._fuzzy_dead_time.setValue(settings["dead_time_l"])
        if "rl_fallback_kp" in settings:
            self._rl_fallback_kp.setValue(settings["rl_fallback_kp"])
        if "rl_fallback_kd" in settings:
            self._rl_fallback_kd.setValue(settings["rl_fallback_kd"])
        if "rl_learning_rate" in settings:
            self._rl_learning_rate.setValue(settings["rl_learning_rate"])
        if "rl_train_interval" in settings:
            self._rl_train_interval.setValue(settings["rl_train_interval"])

        for w in widgets:
            w.blockSignals(False)

        # Update committed state
        self._committed_ai_settings = self.get_ai_settings()

    def get_ai_settings(self) -> dict:
        """Return current AI settings as a dict."""
        return {
            "speed_factor": self._fuzzy_speed_factor.value(),
            "limit_min": self._fuzzy_limit_min.value(),
            "limit_max": self._fuzzy_limit_max.value(),
            "dead_time_l": self._fuzzy_dead_time.value(),
            "rl_fallback_kp": self._rl_fallback_kp.value(),
            "rl_fallback_kd": self._rl_fallback_kd.value(),
            "rl_learning_rate": self._rl_learning_rate.value(),
            "rl_train_interval": self._rl_train_interval.value(),
        }

    # ── Apply / Cancel logic ───────────────────────────────────────────

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
        if self._opcua_endpoint.text() != self._committed_opcua_url:
            return True
        return self.get_ai_settings() != self._committed_ai_settings

    def _on_apply(self) -> None:
        """Emit signals for changed values, update committed state, disable buttons."""
        # Emit only for fields that actually changed
        if self._theme_combo.currentIndex() != self._committed_theme_idx:
            self.theme_changed.emit(self._theme_combo.currentText())
        if self._refresh_spin.value() != self._committed_refresh:
            self.refresh_rate_changed.emit(self._refresh_spin.value())
        if self._opcua_endpoint.text() != self._committed_opcua_url:
            self.opcua_endpoint_save_requested.emit(self._opcua_endpoint.text())

        current_ai = self.get_ai_settings()
        if current_ai != self._committed_ai_settings:
            self.ai_settings_changed.emit(current_ai)

        # Update committed state
        self._committed_theme_idx = self._theme_combo.currentIndex()
        self._committed_refresh = self._refresh_spin.value()
        self._committed_opcua_url = self._opcua_endpoint.text()
        self._committed_ai_settings = current_ai

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

        # Revert AI settings
        self.load_ai_settings(self._committed_ai_settings)

        self._apply_btn.setEnabled(False)
        self._cancel_btn.setEnabled(False)

    # ── Immediate actions ──────────────────────────────────────────────

    def _on_opcua_connect(self) -> None:
        url = self._opcua_endpoint.text().strip()
        if url:
            self.set_opcua_connecting()
            self.opcua_connect_requested.emit(url)

    def _on_opcua_disconnect(self) -> None:
        self.opcua_disconnect_requested.emit()

    # ── Project actions (immediate — not buffered) ─────────────────────

    def update_project_info(self, name: str, path: str, count: int) -> None:
        """Update the project information labels."""
        self._project_name.setText(name)
        self._project_path.setText(path)
        self._project_count.setText(str(count))

    def apply_theme(self, theme: ThemeBase) -> None:
        """Update styles for dynamic theme switching."""
        self.setStyleSheet(
            f"QGroupBox {{ color: {theme.fg_primary}; "
            f"font-weight: bold; border: 1px solid {theme.border}; "
            f"border-radius: 4px; margin-top: 8px; padding-top: 16px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 8px; }}"
            f"QLabel {{ color: {theme.fg_primary}; }}"
        )
