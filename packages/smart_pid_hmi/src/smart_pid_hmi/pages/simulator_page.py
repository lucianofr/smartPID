"""SimulatorPage — preset selection, parameter sliders, disturbance injection."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from smart_pid_domain.enums import ProcessPresetName
from smart_pid_domain.models.process_preset import PRESETS

if TYPE_CHECKING:
    from smart_pid_domain.dtos.simulator import ControllerSimStatus
    from smart_pid_hmi.themes.base import ThemeBase

# Slider range config: (min, max, default, decimals)
_PARAM_RANGES = {
    "gain": (0.1, 10.0, 1.2, 2),
    "tau1": (0.5, 120.0, 3.0, 1),
    "tau2": (0.0, 60.0, 15.0, 1),
    "dead_time": (0.0, 30.0, 1.0, 1),
}


class SimulatorPage(QWidget):
    """Simulator control page with preset selection, parameters, and disturbances."""

    # Signals emitted to MainWindow for API calls
    preset_changed = Signal(str)
    parameters_changed = Signal(float, float, float, float)
    step_requested = Signal(float)
    noise_requested = Signal(float)
    clear_disturbance_requested = Signal()
    pid_enabled_changed = Signal(bool)
    pid_params_changed = Signal(float, float, float)
    pid_mode_changed = Signal(str)
    pid_sp_changed = Signal(float)
    pid_co_changed = Signal(float)
    auto_sp_changed = Signal(bool, float, float)
    auto_disturbance_changed = Signal(bool, float)
    sim_start_requested = Signal()
    sim_stop_requested = Signal()
    opcua_config_changed = Signal(int)  # port
    opcua_start_requested = Signal()
    opcua_stop_requested = Signal()

    def __init__(self, theme: ThemeBase, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Title
        title = QLabel("Simulator Control")
        title.setStyleSheet(
            f"font-size: {theme.font_size_title}px; font-weight: bold; "
            f"color: {theme.fg_primary};"
        )
        layout.addWidget(title)

        # Controller selector (full width)
        ctrl_row = QHBoxLayout()
        ctrl_row.addWidget(QLabel("Controller:"))
        self._controller_combo = QComboBox()
        ctrl_row.addWidget(self._controller_combo, stretch=1)
        layout.addLayout(ctrl_row)

        # ============================================================
        # Two-column layout
        # ============================================================
        columns = QHBoxLayout()
        columns.setSpacing(16)

        # --- LEFT COLUMN ---
        left_col = QVBoxLayout()
        left_col.setSpacing(12)

        # Preset group
        preset_group = QGroupBox("Process Model Preset")
        preset_layout = QHBoxLayout(preset_group)
        preset_layout.addWidget(QLabel("Preset:"))
        self._preset_combo = QComboBox()
        for p in ProcessPresetName:
            self._preset_combo.addItem(p.value)
        preset_layout.addWidget(self._preset_combo, stretch=1)
        left_col.addWidget(preset_group)

        # Parameters group
        param_group = QGroupBox("Parameters")
        param_layout = QVBoxLayout(param_group)
        self._gain_slider = self._make_param_row(param_layout, "Gain (K):", "gain")
        self._tau1_slider = self._make_param_row(param_layout, "Tau1 (s):", "tau1")
        self._tau1_slider.valueChanged.connect(self._update_period_label)
        self._tau2_slider = self._make_param_row(param_layout, "Tau2 (s):", "tau2")
        self._dead_time_slider = self._make_param_row(
            param_layout, "Dead Time (s):", "dead_time",
        )
        left_col.addWidget(param_group)

        # Internal PID group
        pid_group = QGroupBox("Internal PID")
        pid_outer = QVBoxLayout(pid_group)

        pid_top_row = QHBoxLayout()
        self._pid_enable_cb = QCheckBox("Enable PID")
        self._pid_enable_cb.setObjectName("pid_enable_cb")
        self._pid_enable_cb.setChecked(False)
        pid_top_row.addWidget(self._pid_enable_cb)
        pid_top_row.addStretch()
        pid_top_row.addWidget(QLabel("Mode:"))
        self._pid_mode_combo = QComboBox()
        self._pid_mode_combo.setObjectName("pid_mode_combo")
        self._pid_mode_combo.addItems(["MAN", "AUTO"])
        pid_top_row.addWidget(self._pid_mode_combo)
        pid_outer.addLayout(pid_top_row)

        pid_form = QFormLayout()
        pid_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self._pid_pv_edit = QLineEdit("0.0")
        self._pid_pv_edit.setObjectName("pid_pv_edit")
        self._pid_pv_edit.setReadOnly(True)
        pid_form.addRow("PV:", self._pid_pv_edit)

        self._pid_sp_edit = QLineEdit("50.0")
        self._pid_sp_edit.setObjectName("pid_sp_edit")
        pid_form.addRow("SP:", self._pid_sp_edit)

        self._pid_co_edit = QLineEdit("0.0")
        self._pid_co_edit.setObjectName("pid_co_edit")
        pid_form.addRow("CO:", self._pid_co_edit)

        self._pid_kp_edit = QLineEdit("1.00")
        self._pid_kp_edit.setObjectName("pid_kp_edit")
        pid_form.addRow("Kp:", self._pid_kp_edit)

        self._pid_ti_edit = QLineEdit("10.0")
        self._pid_ti_edit.setObjectName("pid_ti_edit")
        pid_form.addRow("Ti:", self._pid_ti_edit)

        self._pid_td_edit = QLineEdit("0.0")
        self._pid_td_edit.setObjectName("pid_td_edit")
        pid_form.addRow("Td:", self._pid_td_edit)

        pid_outer.addLayout(pid_form)
        left_col.addWidget(pid_group)

        # PID controls list (for enable/disable toggling)
        self._pid_controls: list[QWidget] = [
            self._pid_mode_combo,
            self._pid_sp_edit,
            self._pid_co_edit,
            self._pid_kp_edit,
            self._pid_ti_edit,
            self._pid_td_edit,
        ]
        for ctrl in self._pid_controls:
            ctrl.setEnabled(False)

        # Excitation period label
        self._period_label = QLabel()
        self._period_label.setStyleSheet(
            f"font-size: {theme.font_size_normal}px; color: {theme.fg_secondary};"
        )
        left_col.addWidget(self._period_label)
        self._update_period_label()

        left_col.addStretch()
        columns.addLayout(left_col, stretch=1)

        # --- RIGHT COLUMN ---
        right_col = QVBoxLayout()
        right_col.setSpacing(12)

        # OPC-UA Server Config group
        opcua_group = QGroupBox("OPC-UA Server")
        opcua_layout = QVBoxLayout(opcua_group)

        # Status indicator row
        opcua_status_row = QHBoxLayout()
        opcua_status_row.addWidget(QLabel("Status:"))
        self._opcua_status_label = QLabel("Stopped")
        self._opcua_status_label.setObjectName("opcua_status_label")
        self._opcua_status_label.setStyleSheet(
            f"font-weight: bold; color: {theme.alarm_critical};"
        )
        opcua_status_row.addWidget(self._opcua_status_label)
        opcua_status_row.addStretch()
        opcua_layout.addLayout(opcua_status_row)

        # Start/Stop buttons row
        opcua_btn_row = QHBoxLayout()
        self._opcua_start_btn = QPushButton("Start")
        self._opcua_start_btn.setObjectName("opcua_start_btn")
        self._opcua_start_btn.clicked.connect(self._on_opcua_start)
        opcua_btn_row.addWidget(self._opcua_start_btn)
        self._opcua_stop_btn = QPushButton("Stop")
        self._opcua_stop_btn.setObjectName("opcua_stop_btn")
        self._opcua_stop_btn.setEnabled(False)
        self._opcua_stop_btn.clicked.connect(self._on_opcua_stop)
        opcua_btn_row.addWidget(self._opcua_stop_btn)
        opcua_layout.addLayout(opcua_btn_row)

        # Endpoint config row (keep existing)
        endpoint_row = QHBoxLayout()
        endpoint_row.addWidget(QLabel("Endpoint:"))
        self._opcua_endpoint_label = QLabel("opc.tcp://0.0.0.0:")
        self._opcua_endpoint_label.setObjectName("opcua_endpoint_label")
        endpoint_row.addWidget(self._opcua_endpoint_label)
        self._opcua_port_spin = QDoubleSpinBox()
        self._opcua_port_spin.setObjectName("opcua_port_spin")
        self._opcua_port_spin.setRange(1024, 65535)
        self._opcua_port_spin.setValue(4849)
        self._opcua_port_spin.setDecimals(0)
        endpoint_row.addWidget(self._opcua_port_spin, stretch=1)
        opcua_layout.addLayout(endpoint_row)
        opcua_apply = QPushButton("Apply")
        opcua_apply.setObjectName("opcua_apply_btn")
        opcua_apply.clicked.connect(self._on_opcua_apply)
        opcua_layout.addWidget(opcua_apply)
        right_col.addWidget(opcua_group)

        # Auto SP Variation group
        auto_sp_group = QGroupBox("Auto SP Variation")
        auto_sp_layout = QVBoxLayout(auto_sp_group)
        auto_sp_enable_row = QHBoxLayout()
        self._auto_sp_enable = QCheckBox("Enable")
        self._auto_sp_enable.setObjectName("auto_sp_enable")
        auto_sp_enable_row.addWidget(self._auto_sp_enable)
        auto_sp_enable_row.addStretch()
        auto_sp_layout.addLayout(auto_sp_enable_row)
        sp_min_row = QHBoxLayout()
        sp_min_row.addWidget(QLabel("SP Min (%):"))
        self._auto_sp_min = QDoubleSpinBox()
        self._auto_sp_min.setObjectName("auto_sp_min")
        self._auto_sp_min.setRange(0.0, 100.0)
        self._auto_sp_min.setValue(30.0)
        self._auto_sp_min.setDecimals(1)
        sp_min_row.addWidget(self._auto_sp_min, stretch=1)
        auto_sp_layout.addLayout(sp_min_row)
        sp_max_row = QHBoxLayout()
        sp_max_row.addWidget(QLabel("SP Max (%):"))
        self._auto_sp_max = QDoubleSpinBox()
        self._auto_sp_max.setObjectName("auto_sp_max")
        self._auto_sp_max.setRange(0.0, 100.0)
        self._auto_sp_max.setValue(70.0)
        self._auto_sp_max.setDecimals(1)
        sp_max_row.addWidget(self._auto_sp_max, stretch=1)
        auto_sp_layout.addLayout(sp_max_row)
        auto_sp_apply = QPushButton("Apply")
        auto_sp_apply.setObjectName("auto_sp_apply")
        auto_sp_apply.clicked.connect(self._on_auto_sp_apply)
        auto_sp_layout.addWidget(auto_sp_apply)
        right_col.addWidget(auto_sp_group)

        # Auto Disturbance group
        auto_dist_group = QGroupBox("Auto Disturbance")
        auto_dist_layout = QVBoxLayout(auto_dist_group)
        auto_dist_enable_row = QHBoxLayout()
        self._auto_dist_enable = QCheckBox("Enable")
        self._auto_dist_enable.setObjectName("auto_dist_enable")
        auto_dist_enable_row.addWidget(self._auto_dist_enable)
        auto_dist_enable_row.addStretch()
        auto_dist_layout.addLayout(auto_dist_enable_row)
        amp_row = QHBoxLayout()
        amp_row.addWidget(QLabel("Max Amplitude (%):"))
        self._auto_dist_amp = QDoubleSpinBox()
        self._auto_dist_amp.setObjectName("auto_dist_amp")
        self._auto_dist_amp.setRange(0.0, 100.0)
        self._auto_dist_amp.setValue(10.0)
        self._auto_dist_amp.setDecimals(1)
        amp_row.addWidget(self._auto_dist_amp, stretch=1)
        auto_dist_layout.addLayout(amp_row)
        auto_dist_apply = QPushButton("Apply")
        auto_dist_apply.setObjectName("auto_dist_apply")
        auto_dist_apply.clicked.connect(self._on_auto_dist_apply)
        auto_dist_layout.addWidget(auto_dist_apply)
        right_col.addWidget(auto_dist_group)

        # Disturbance group (immediate actions)
        dist_group = QGroupBox("Disturbances")
        dist_layout = QVBoxLayout(dist_group)

        step_row = QHBoxLayout()
        step_row.addWidget(QLabel("Step:"))
        self._step_amplitude = QDoubleSpinBox()
        self._step_amplitude.setRange(-50.0, 50.0)
        self._step_amplitude.setValue(5.0)
        self._step_amplitude.setSuffix(" %")
        step_row.addWidget(self._step_amplitude)
        step_btn = QPushButton("Inject Step")
        step_btn.clicked.connect(self._on_step_inject)
        step_row.addWidget(step_btn)
        dist_layout.addLayout(step_row)

        noise_row = QHBoxLayout()
        noise_row.addWidget(QLabel("Noise:"))
        self._noise_amplitude = QDoubleSpinBox()
        self._noise_amplitude.setRange(0.0, 10.0)
        self._noise_amplitude.setValue(0.5)
        self._noise_amplitude.setSuffix(" %")
        noise_row.addWidget(self._noise_amplitude)
        noise_btn = QPushButton("Inject Noise")
        noise_btn.clicked.connect(self._on_noise_inject)
        noise_row.addWidget(noise_btn)
        dist_layout.addLayout(noise_row)

        clear_btn = QPushButton("Clear All Disturbances")
        clear_btn.clicked.connect(self._on_clear_disturbance)
        dist_layout.addWidget(clear_btn)
        right_col.addWidget(dist_group)

        right_col.addStretch()
        columns.addLayout(right_col, stretch=1)

        layout.addLayout(columns, stretch=1)

        # ============================================================
        # Bottom row (full width): Status + Start/Stop + Apply/Cancel
        # ============================================================
        btn_row = QHBoxLayout()
        self._status_label = QLabel("Status: Stopped")
        self._status_label.setStyleSheet(f"color: {theme.fg_secondary};")
        btn_row.addWidget(self._status_label)
        btn_row.addStretch()
        self._sim_start_btn = QPushButton("Start")
        self._sim_start_btn.setObjectName("sim_start_btn")
        self._sim_start_btn.clicked.connect(self._on_sim_start)
        btn_row.addWidget(self._sim_start_btn)
        self._sim_stop_btn = QPushButton("Stop")
        self._sim_stop_btn.setObjectName("sim_stop_btn")
        self._sim_stop_btn.setEnabled(False)
        self._sim_stop_btn.clicked.connect(self._on_sim_stop)
        btn_row.addWidget(self._sim_stop_btn)
        btn_row.addStretch()
        self._sim_cancel_btn = QPushButton("Cancel")
        self._sim_cancel_btn.setObjectName("sim_cancel_btn")
        self._sim_cancel_btn.setEnabled(False)
        self._sim_cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._sim_cancel_btn)
        self._sim_apply_btn = QPushButton("Apply")
        self._sim_apply_btn.setObjectName("sim_apply_btn")
        self._sim_apply_btn.setEnabled(False)
        self._sim_apply_btn.clicked.connect(self._on_apply)
        btn_row.addWidget(self._sim_apply_btn)
        layout.addLayout(btn_row)

        # Apply initial preset without triggering change tracking
        self._on_preset_changed(self._preset_combo.currentText())

        # Store committed state
        self._committed_preset_idx = self._preset_combo.currentIndex()
        self._committed_gain = self._gain_slider.value()
        self._committed_tau1 = self._tau1_slider.value()
        self._committed_tau2 = self._tau2_slider.value()
        self._committed_dead_time = self._dead_time_slider.value()
        self._committed_pid_enable = self._pid_enable_cb.isChecked()
        self._committed_pid_mode_idx = self._pid_mode_combo.currentIndex()
        self._committed_pid_sp = self._pid_sp_edit.text()
        self._committed_pid_co = self._pid_co_edit.text()
        self._committed_kp = self._pid_kp_edit.text()
        self._committed_ti = self._pid_ti_edit.text()
        self._committed_td = self._pid_td_edit.text()

        # Connect change tracking after storing committed state
        self._preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        self._preset_combo.currentIndexChanged.connect(self._on_field_changed)
        self._gain_slider.valueChanged.connect(self._on_field_changed)
        self._tau1_slider.valueChanged.connect(self._on_field_changed)
        self._tau2_slider.valueChanged.connect(self._on_field_changed)
        self._dead_time_slider.valueChanged.connect(self._on_field_changed)
        self._pid_enable_cb.toggled.connect(self._on_pid_enable_toggled)
        self._pid_enable_cb.toggled.connect(self._on_field_changed)
        self._pid_mode_combo.currentIndexChanged.connect(self._on_field_changed)
        self._pid_sp_edit.textChanged.connect(self._on_field_changed)
        self._pid_co_edit.textChanged.connect(self._on_field_changed)
        self._pid_kp_edit.textChanged.connect(self._on_field_changed)
        self._pid_ti_edit.textChanged.connect(self._on_field_changed)
        self._pid_td_edit.textChanged.connect(self._on_field_changed)

    def _make_param_row(
        self, layout: QVBoxLayout, label: str, key: str,
    ) -> QDoubleSpinBox:
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        mn, mx, default, decimals = _PARAM_RANGES[key]
        spin = QDoubleSpinBox()
        spin.setRange(mn, mx)
        spin.setValue(default)
        spin.setDecimals(decimals)
        row.addWidget(spin, stretch=1)
        layout.addLayout(row)
        return spin

    # ------------------------------------------------------------------
    # Apply / Cancel
    # ------------------------------------------------------------------

    def _on_field_changed(self) -> None:
        changed = self.has_unsaved_changes()
        self._sim_apply_btn.setEnabled(changed)
        self._sim_cancel_btn.setEnabled(changed)

    def has_unsaved_changes(self) -> bool:
        return (
            self._preset_combo.currentIndex() != self._committed_preset_idx
            or self._gain_slider.value() != self._committed_gain
            or self._tau1_slider.value() != self._committed_tau1
            or self._tau2_slider.value() != self._committed_tau2
            or self._dead_time_slider.value() != self._committed_dead_time
            or self._pid_enable_cb.isChecked() != self._committed_pid_enable
            or self._pid_mode_combo.currentIndex() != self._committed_pid_mode_idx
            or self._pid_sp_edit.text() != self._committed_pid_sp
            or self._pid_co_edit.text() != self._committed_pid_co
            or self._pid_kp_edit.text() != self._committed_kp
            or self._pid_ti_edit.text() != self._committed_ti
            or self._pid_td_edit.text() != self._committed_td
        )

    @staticmethod
    def _parse_float(text: str, fallback: float = 0.0) -> float:
        try:
            return float(text.replace(",", "."))
        except (ValueError, AttributeError):
            return fallback

    def _on_apply(self) -> None:
        if self._preset_combo.currentIndex() != self._committed_preset_idx:
            self.preset_changed.emit(self._preset_combo.currentText())
        if (
            self._gain_slider.value() != self._committed_gain
            or self._tau1_slider.value() != self._committed_tau1
            or self._tau2_slider.value() != self._committed_tau2
            or self._dead_time_slider.value() != self._committed_dead_time
        ):
            tau2 = self._tau2_slider.value() if self._tau2_slider.isEnabled() else 0.0
            self.parameters_changed.emit(
                self._gain_slider.value(), self._tau1_slider.value(),
                tau2, self._dead_time_slider.value(),
            )
        if self._pid_enable_cb.isChecked() != self._committed_pid_enable:
            self.pid_enabled_changed.emit(self._pid_enable_cb.isChecked())
        if self._pid_mode_combo.currentIndex() != self._committed_pid_mode_idx:
            self.pid_mode_changed.emit(self._pid_mode_combo.currentText())
        if self._pid_sp_edit.text() != self._committed_pid_sp:
            self.pid_sp_changed.emit(self._parse_float(self._pid_sp_edit.text(), 50.0))
        if self._pid_co_edit.text() != self._committed_pid_co:
            self.pid_co_changed.emit(self._parse_float(self._pid_co_edit.text(), 0.0))
        if (
            self._pid_kp_edit.text() != self._committed_kp
            or self._pid_ti_edit.text() != self._committed_ti
            or self._pid_td_edit.text() != self._committed_td
        ):
            self.pid_params_changed.emit(
                self._parse_float(self._pid_kp_edit.text(), 1.0),
                self._parse_float(self._pid_ti_edit.text(), 10.0),
                self._parse_float(self._pid_td_edit.text(), 0.0),
            )

        self._committed_preset_idx = self._preset_combo.currentIndex()
        self._committed_gain = self._gain_slider.value()
        self._committed_tau1 = self._tau1_slider.value()
        self._committed_tau2 = self._tau2_slider.value()
        self._committed_dead_time = self._dead_time_slider.value()
        self._committed_pid_enable = self._pid_enable_cb.isChecked()
        self._committed_pid_mode_idx = self._pid_mode_combo.currentIndex()
        self._committed_pid_sp = self._pid_sp_edit.text()
        self._committed_pid_co = self._pid_co_edit.text()
        self._committed_kp = self._pid_kp_edit.text()
        self._committed_ti = self._pid_ti_edit.text()
        self._committed_td = self._pid_td_edit.text()
        self._sim_apply_btn.setEnabled(False)
        self._sim_cancel_btn.setEnabled(False)

    def _on_cancel(self) -> None:
        widgets = [
            self._preset_combo, self._gain_slider, self._tau1_slider,
            self._tau2_slider, self._dead_time_slider, self._pid_enable_cb,
            self._pid_mode_combo, self._pid_sp_edit, self._pid_co_edit,
            self._pid_kp_edit, self._pid_ti_edit, self._pid_td_edit,
        ]
        for w in widgets:
            w.blockSignals(True)
        self._preset_combo.setCurrentIndex(self._committed_preset_idx)
        self._gain_slider.setValue(self._committed_gain)
        self._tau1_slider.setValue(self._committed_tau1)
        self._tau2_slider.setValue(self._committed_tau2)
        self._dead_time_slider.setValue(self._committed_dead_time)
        self._pid_enable_cb.setChecked(self._committed_pid_enable)
        self._pid_mode_combo.setCurrentIndex(self._committed_pid_mode_idx)
        self._pid_sp_edit.setText(self._committed_pid_sp)
        self._pid_co_edit.setText(self._committed_pid_co)
        self._pid_kp_edit.setText(self._committed_kp)
        self._pid_ti_edit.setText(self._committed_ti)
        self._pid_td_edit.setText(self._committed_td)
        for w in widgets:
            w.blockSignals(False)
        self._sim_apply_btn.setEnabled(False)
        self._sim_cancel_btn.setEnabled(False)

    # ------------------------------------------------------------------
    # Preset handling
    # ------------------------------------------------------------------

    def _on_preset_selected(self, index: int) -> None:
        text = self._preset_combo.itemText(index)
        self._on_preset_changed(text)

    def _on_preset_changed(self, preset_name: str) -> None:
        try:
            preset_enum = ProcessPresetName(preset_name)
        except ValueError:
            return
        if preset_enum != ProcessPresetName.CUSTOM and preset_enum in PRESETS:
            p = PRESETS[preset_enum]
            self._gain_slider.setValue(p.gain)
            self._tau1_slider.setValue(p.tau1)
            self._tau2_slider.setValue(p.tau2 if p.tau2 is not None else 0.0)
            self._dead_time_slider.setValue(p.dead_time)

    # ------------------------------------------------------------------
    # Disturbance (immediate actions)
    # ------------------------------------------------------------------

    def _on_step_inject(self) -> None:
        self.step_requested.emit(self._step_amplitude.value())

    def _on_noise_inject(self) -> None:
        self.noise_requested.emit(self._noise_amplitude.value())

    def _on_clear_disturbance(self) -> None:
        self.clear_disturbance_requested.emit()

    # ------------------------------------------------------------------
    # PID enable toggle
    # ------------------------------------------------------------------

    def _on_pid_enable_toggled(self, checked: bool) -> None:
        for ctrl in self._pid_controls:
            ctrl.setEnabled(checked)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _update_period_label(self) -> None:
        tau1 = self._tau1_slider.value()
        period = max(10.0 * tau1, 1.0)
        self._period_label.setText(f"Excitation Period (10 \u00d7 \u03c41): {period:.1f} s")

    def _on_auto_sp_apply(self) -> None:
        lo = self._auto_sp_min.value()
        hi = self._auto_sp_max.value()
        if lo >= hi:
            return  # ignore invalid range
        self.auto_sp_changed.emit(self._auto_sp_enable.isChecked(), lo, hi)

    def _on_auto_dist_apply(self) -> None:
        self.auto_disturbance_changed.emit(
            self._auto_dist_enable.isChecked(),
            self._auto_dist_amp.value(),
        )

    def _on_sim_start(self) -> None:
        self.sim_start_requested.emit()

    def _on_sim_stop(self) -> None:
        self.sim_stop_requested.emit()

    def _on_opcua_apply(self) -> None:
        self.opcua_config_changed.emit(int(self._opcua_port_spin.value()))

    def _on_opcua_start(self) -> None:
        self.opcua_start_requested.emit()

    def _on_opcua_stop(self) -> None:
        self.opcua_stop_requested.emit()

    @Slot(bool)
    def set_opcua_running(self, running: bool) -> None:
        """Update OPC-UA status indicator and button states."""
        self._opcua_start_btn.setEnabled(not running)
        self._opcua_stop_btn.setEnabled(running)
        if running:
            self._opcua_status_label.setText("Running")
            self._opcua_status_label.setStyleSheet(
                f"font-weight: bold; color: {self._theme.bar_pv};"
            )
        else:
            self._opcua_status_label.setText("Stopped")
            self._opcua_status_label.setStyleSheet(
                f"font-weight: bold; color: {self._theme.alarm_critical};"
            )

    @Slot(bool)
    def set_sim_running(self, running: bool) -> None:
        """Update Start/Stop button states based on simulation status."""
        self._sim_start_btn.setEnabled(not running)
        self._sim_stop_btn.setEnabled(running)
        self._status_label.setText(f"Status: {'Running' if running else 'Stopped'}")

    def set_status_text(self, text: str) -> None:
        self._status_label.setText(f"Status: {text}")

    def populate_controllers(self, controllers: list[dict]) -> None:
        self._controller_combo.clear()
        for ctrl in controllers:
            self._controller_combo.addItem(ctrl["name"], ctrl["id"])

    @property
    def current_controller_id(self) -> int | None:
        data = self._controller_combo.currentData()
        return data if isinstance(data, int) else None

    def update_pv(self, pv: float) -> None:
        """Update the read-only PV display."""
        self._pid_pv_edit.setText(f"{pv:.2f}")

    def populate_from_status(self, status: ControllerSimStatus) -> None:
        """Populate widgets from a ControllerSimStatus DTO."""
        self._pid_sp_edit.setText(f"{getattr(status, 'pid_sp', 50.0):.1f}")
        self._pid_kp_edit.setText(f"{status.pid_kp:.2f}")
        self._pid_ti_edit.setText(f"{status.pid_ti:.1f}")
        self._pid_td_edit.setText(f"{status.pid_td:.1f}")
        self._pid_co_edit.setText(f"{status.pid_cv:.2f}")
        if status.auto_sp is not None:
            self._auto_sp_enable.setChecked(status.auto_sp.enabled)
            self._auto_sp_min.setValue(status.auto_sp.sp_min_pct)
            self._auto_sp_max.setValue(status.auto_sp.sp_max_pct)
        if status.auto_disturbance is not None:
            self._auto_dist_enable.setChecked(status.auto_disturbance.enabled)
            self._auto_dist_amp.setValue(status.auto_disturbance.max_amplitude_pct)

    def apply_theme(self, theme: ThemeBase) -> None:
        """Re-apply theme colors to dynamic elements."""
        self._theme = theme
