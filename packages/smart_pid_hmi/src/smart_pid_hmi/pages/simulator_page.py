"""SimulatorPage — preset selection, parameter fields, disturbance injection."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal, Slot
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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

# Parameter config: (default, decimals)
_PARAM_DEFAULTS = {
    "gain": (1.2, 2),
    "tau1": (3.0, 1),
    "tau2": (15.0, 1),
    "dead_time": (1.0, 1),
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
        self._tau2_slider = self._make_param_row(param_layout, "Tau2 (s):", "tau2")
        self._dead_time_slider = self._make_param_row(
            param_layout, "Dead Time (s):", "dead_time",
        )
        left_col.addWidget(param_group)

        # --- PID + Computed Variables side-by-side ---
        pid_computed_row = QHBoxLayout()
        pid_computed_row.setSpacing(12)

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
        self._btn_pid_auto = QPushButton("AUTO")
        self._btn_pid_man = QPushButton("MAN")
        self._btn_pid_auto.setFixedHeight(28)
        self._btn_pid_man.setFixedHeight(28)
        self._btn_pid_auto.setFixedWidth(60)
        self._btn_pid_man.setFixedWidth(60)
        self._pid_active_mode = "MAN"
        self._btn_pid_auto.clicked.connect(lambda: self._on_pid_mode_click("AUTO"))
        self._btn_pid_man.clicked.connect(lambda: self._on_pid_mode_click("MAN"))
        self._apply_pid_mode_style()
        pid_top_row.addWidget(self._btn_pid_auto)
        pid_top_row.addWidget(self._btn_pid_man)
        pid_outer.addLayout(pid_top_row)

        pid_form = QFormLayout()
        pid_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self._pid_pv_edit = QLineEdit("0.0")
        self._pid_pv_edit.setObjectName("pid_pv_edit")
        self._pid_pv_edit.setReadOnly(True)
        pid_form.addRow("PV:", self._pid_pv_edit)

        sp_row = QHBoxLayout()
        self._pid_sp_edit = QLineEdit("50.0")
        self._pid_sp_edit.setObjectName("pid_sp_edit")
        sp_row.addWidget(self._pid_sp_edit, stretch=1)
        sp_row.addWidget(QLabel("SP_WRK:"))
        self._pid_sp_wrk_edit = QLineEdit("50.0")
        self._pid_sp_wrk_edit.setObjectName("pid_sp_wrk_edit")
        self._pid_sp_wrk_edit.setReadOnly(True)
        sp_row.addWidget(self._pid_sp_wrk_edit, stretch=1)
        pid_form.addRow("SP:", sp_row)

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
        pid_computed_row.addWidget(pid_group, stretch=1)

        # PID controls list (for enable/disable toggling)
        self._pid_controls: list[QWidget] = [
            self._btn_pid_auto, self._btn_pid_man,
            self._pid_sp_edit,
            self._pid_co_edit,
            self._pid_kp_edit,
            self._pid_ti_edit,
            self._pid_td_edit,
        ]
        for ctrl in self._pid_controls:
            ctrl.setEnabled(False)

        # Computed Variables group (side-by-side with PID)
        live_group = QGroupBox("Computed Variables")
        live_form = QFormLayout(live_group)
        live_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self._proc_in_edit = QLineEdit("0.00")
        self._proc_in_edit.setObjectName("proc_in_edit")
        self._proc_in_edit.setReadOnly(True)
        live_form.addRow("Process In:", self._proc_in_edit)

        self._proc_out_edit = QLineEdit("0.00")
        self._proc_out_edit.setObjectName("proc_out_edit")
        self._proc_out_edit.setReadOnly(True)
        live_form.addRow("Process Out:", self._proc_out_edit)

        self._dist_out_edit = QLineEdit("0.00")
        self._dist_out_edit.setObjectName("dist_out_edit")
        self._dist_out_edit.setReadOnly(True)
        live_form.addRow("D_OUT:", self._dist_out_edit)

        self._auto_sp_edit = QLineEdit("---")
        self._auto_sp_edit.setObjectName("auto_sp_edit")
        self._auto_sp_edit.setReadOnly(True)
        live_form.addRow("SP_V:", self._auto_sp_edit)

        self._auto_dist_edit = QLineEdit("---")
        self._auto_dist_edit.setObjectName("auto_dist_edit")
        self._auto_dist_edit.setReadOnly(True)
        live_form.addRow("D_AUTO:", self._auto_dist_edit)

        pid_computed_row.addWidget(live_group, stretch=1)
        left_col.addLayout(pid_computed_row)

        # Excitation period label
        self._period_label = QLabel()
        self._period_label.setStyleSheet(
            f"font-size: {theme.font_size_normal}px; color: {theme.fg_secondary};"
        )
        left_col.addWidget(self._period_label)
        self._update_period_label()

        # Block diagram SVG
        self._svg_widget = QSvgWidget()
        self._svg_widget.setObjectName("block_diagram_svg")
        self._svg_widget.setMinimumHeight(140)
        self._svg_widget.load(self._build_block_diagram_svg(theme).encode("utf-8"))
        left_col.addWidget(self._svg_widget, stretch=1)

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
        self._opcua_port_edit = QLineEdit("4849")
        self._opcua_port_edit.setObjectName("opcua_port_edit")
        endpoint_row.addWidget(self._opcua_port_edit, stretch=1)
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
        self._auto_sp_min = QLineEdit("30.0")
        self._auto_sp_min.setObjectName("auto_sp_min")
        sp_min_row.addWidget(self._auto_sp_min, stretch=1)
        auto_sp_layout.addLayout(sp_min_row)
        sp_max_row = QHBoxLayout()
        sp_max_row.addWidget(QLabel("SP Max (%):"))
        self._auto_sp_max = QLineEdit("70.0")
        self._auto_sp_max.setObjectName("auto_sp_max")
        sp_max_row.addWidget(self._auto_sp_max, stretch=1)
        auto_sp_layout.addLayout(sp_max_row)
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
        self._auto_dist_amp = QLineEdit("10.0")
        self._auto_dist_amp.setObjectName("auto_dist_amp")
        amp_row.addWidget(self._auto_dist_amp, stretch=1)
        auto_dist_layout.addLayout(amp_row)
        right_col.addWidget(auto_dist_group)

        # Disturbance group (immediate actions)
        dist_group = QGroupBox("Disturbances")
        dist_layout = QVBoxLayout(dist_group)

        step_row = QHBoxLayout()
        step_row.addWidget(QLabel("Step:"))
        self._step_amplitude = QLineEdit("5.0")
        self._step_amplitude.setObjectName("step_amplitude")
        step_row.addWidget(self._step_amplitude)
        step_btn = QPushButton("Inject Step")
        step_btn.clicked.connect(self._on_step_inject)
        step_row.addWidget(step_btn)
        dist_layout.addLayout(step_row)

        noise_row = QHBoxLayout()
        noise_row.addWidget(QLabel("Noise:"))
        self._noise_amplitude = QLineEdit("0.5")
        self._noise_amplitude.setObjectName("noise_amplitude")
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

        # Store committed state (process model params only — PID controls are immediate)
        self._committed_preset_idx = self._preset_combo.currentIndex()
        self._committed_gain = self._gain_slider.text()
        self._committed_tau1 = self._tau1_slider.text()
        self._committed_tau2 = self._tau2_slider.text()
        self._committed_dead_time = self._dead_time_slider.text()

        # Connect change tracking for PROCESS MODEL params (Apply required)
        self._preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        self._preset_combo.currentIndexChanged.connect(self._on_field_changed)
        self._gain_slider.textChanged.connect(self._on_field_changed)
        self._tau1_slider.textChanged.connect(self._on_field_changed)
        self._tau1_slider.textChanged.connect(lambda _: self._update_period_label())
        self._tau2_slider.textChanged.connect(self._on_field_changed)
        self._dead_time_slider.textChanged.connect(self._on_field_changed)

        # PID controls act IMMEDIATELY (real-time, no Apply needed)
        self._pid_enable_cb.toggled.connect(self._on_pid_enable_toggled)
        self._pid_enable_cb.toggled.connect(lambda v: self.pid_enabled_changed.emit(v))
        # Mode buttons connected via _on_pid_mode_click
        self._pid_sp_edit.editingFinished.connect(
            lambda: self.pid_sp_changed.emit(
                self._parse_float(self._pid_sp_edit.text(), 50.0)
            )
        )
        self._pid_co_edit.editingFinished.connect(
            lambda: self.pid_co_changed.emit(
                self._parse_float(self._pid_co_edit.text(), 0.0)
            )
        )
        self._pid_kp_edit.editingFinished.connect(self._on_pid_params_edited)
        self._pid_ti_edit.editingFinished.connect(self._on_pid_params_edited)
        self._pid_td_edit.editingFinished.connect(self._on_pid_params_edited)

        # Auto SP / Auto Disturbance act IMMEDIATELY (no Apply needed)
        self._auto_sp_enable.toggled.connect(lambda _: self._emit_auto_sp())
        self._auto_sp_min.editingFinished.connect(self._emit_auto_sp)
        self._auto_sp_max.editingFinished.connect(self._emit_auto_sp)
        self._auto_dist_enable.toggled.connect(lambda _: self._emit_auto_dist())
        self._auto_dist_amp.editingFinished.connect(self._emit_auto_dist)

    def _make_param_row(
        self, layout: QVBoxLayout, label: str, key: str,
    ) -> QLineEdit:
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        default, decimals = _PARAM_DEFAULTS[key]
        edit = QLineEdit(f"{default:.{decimals}f}")
        row.addWidget(edit, stretch=1)
        layout.addLayout(row)
        return edit

    # ------------------------------------------------------------------
    # Apply / Cancel
    # ------------------------------------------------------------------

    def _on_field_changed(self) -> None:
        changed = self.has_unsaved_changes()
        self._sim_apply_btn.setEnabled(changed)
        self._sim_cancel_btn.setEnabled(changed)

    def _on_pid_mode_click(self, mode: str) -> None:
        """Handle AUTO/MAN button click."""
        self._pid_active_mode = mode
        self._apply_pid_mode_style()
        self.pid_mode_changed.emit(mode)

    def _apply_pid_mode_style(self) -> None:
        """Highlight active mode button."""
        active_css = (
            "background-color: #424242; color: #FFFFFF;"
            " font-weight: bold; border: 1px solid #616161;"
            " padding: 2px 8px;"
        )
        inactive_css = (
            "background-color: #E0E0E0; color: #757575;"
            " border: 1px solid #BDBDBD;"
            " padding: 2px 8px;"
        )
        self._btn_pid_auto.setStyleSheet(
            active_css if self._pid_active_mode == "AUTO" else inactive_css
        )
        self._btn_pid_man.setStyleSheet(
            active_css if self._pid_active_mode == "MAN" else inactive_css
        )

    def _on_pid_params_edited(self) -> None:
        """Send PID Kp/Ti/Td immediately on Enter or focus loss."""
        self.pid_params_changed.emit(
            self._parse_float(self._pid_kp_edit.text(), 1.0),
            self._parse_float(self._pid_ti_edit.text(), 10.0),
            self._parse_float(self._pid_td_edit.text(), 0.0),
        )

    def has_unsaved_changes(self) -> bool:
        # Only process model params require Apply — PID controls act immediately
        return (
            self._preset_combo.currentIndex() != self._committed_preset_idx
            or self._gain_slider.text() != self._committed_gain
            or self._tau1_slider.text() != self._committed_tau1
            or self._tau2_slider.text() != self._committed_tau2
            or self._dead_time_slider.text() != self._committed_dead_time
        )

    @staticmethod
    def _parse_float(text: str, fallback: float = 0.0) -> float:
        try:
            return float(text.replace(",", "."))
        except (ValueError, AttributeError):
            return fallback

    def _on_apply(self) -> None:
        # Apply only process model changes — PID controls act immediately
        if self._preset_combo.currentIndex() != self._committed_preset_idx:
            self.preset_changed.emit(self._preset_combo.currentText())
        if (
            self._gain_slider.text() != self._committed_gain
            or self._tau1_slider.text() != self._committed_tau1
            or self._tau2_slider.text() != self._committed_tau2
            or self._dead_time_slider.text() != self._committed_dead_time
        ):
            tau2 = self._parse_float(self._tau2_slider.text(), 0.0)
            self.parameters_changed.emit(
                self._parse_float(self._gain_slider.text(), 1.2),
                self._parse_float(self._tau1_slider.text(), 3.0),
                tau2,
                self._parse_float(self._dead_time_slider.text(), 1.0),
            )

        self._committed_preset_idx = self._preset_combo.currentIndex()
        self._committed_gain = self._gain_slider.text()
        self._committed_tau1 = self._tau1_slider.text()
        self._committed_tau2 = self._tau2_slider.text()
        self._committed_dead_time = self._dead_time_slider.text()
        self._sim_apply_btn.setEnabled(False)
        self._sim_cancel_btn.setEnabled(False)

    def _on_cancel(self) -> None:
        # Cancel only reverts process model params — PID controls are immediate
        widgets = [
            self._preset_combo, self._gain_slider, self._tau1_slider,
            self._tau2_slider, self._dead_time_slider,
        ]
        for w in widgets:
            w.blockSignals(True)
        self._preset_combo.setCurrentIndex(self._committed_preset_idx)
        self._gain_slider.setText(self._committed_gain)
        self._tau1_slider.setText(self._committed_tau1)
        self._tau2_slider.setText(self._committed_tau2)
        self._dead_time_slider.setText(self._committed_dead_time)
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
            self._gain_slider.setText(f"{p.gain:.2f}")
            self._tau1_slider.setText(f"{p.tau1:.1f}")
            tau2 = p.tau2 if p.tau2 is not None else 0.0
            self._tau2_slider.setText(f"{tau2:.1f}")
            self._dead_time_slider.setText(f"{p.dead_time:.1f}")

    # ------------------------------------------------------------------
    # Disturbance (immediate actions)
    # ------------------------------------------------------------------

    def _on_step_inject(self) -> None:
        self.step_requested.emit(self._parse_float(self._step_amplitude.text(), 5.0))

    def _on_noise_inject(self) -> None:
        self.noise_requested.emit(self._parse_float(self._noise_amplitude.text(), 0.5))

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
        tau1 = self._parse_float(self._tau1_slider.text(), 3.0)
        period = max(10.0 * tau1, 1.0)
        self._period_label.setText(f"Excitation Period (10 \u00d7 \u03c41): {period:.1f} s")

    def _emit_auto_sp(self) -> None:
        lo = self._parse_float(self._auto_sp_min.text(), 30.0)
        hi = self._parse_float(self._auto_sp_max.text(), 70.0)
        if lo >= hi:
            return  # ignore invalid range
        self.auto_sp_changed.emit(self._auto_sp_enable.isChecked(), lo, hi)

    def _emit_auto_dist(self) -> None:
        self.auto_disturbance_changed.emit(
            self._auto_dist_enable.isChecked(),
            self._parse_float(self._auto_dist_amp.text(), 10.0),
        )

    def _on_sim_start(self) -> None:
        self.sim_start_requested.emit()

    def _on_sim_stop(self) -> None:
        self.sim_stop_requested.emit()

    def _on_opcua_apply(self) -> None:
        self.opcua_config_changed.emit(
            int(self._parse_float(self._opcua_port_edit.text(), 4849))
        )

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

    @Slot(str)
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

    def update_live_values(
        self,
        *,
        pv: float,
        co: float,
        error: float,
        pid_cv: float,
        process_in: float,
        process_out: float,
        disturbance_out: float,
        sp: float | None = None,
        kp: float | None = None,
        ti: float | None = None,
        td: float | None = None,
        mode: int | None = None,
        pid_enabled: bool | None = None,
        auto_sp_enabled: bool | None = None,
        auto_sp_min: float | None = None,
        auto_sp_max: float | None = None,
        auto_dist_enabled: bool | None = None,
        auto_dist_amp: float | None = None,
    ) -> None:
        """Bulk update all read-only live variables from simulation tick.

        CO is only updated when PID is enabled+AUTO (computed by PID).
        In MAN mode, CO is user-editable and must not be overwritten.
        SP is never overwritten — user controls it directly.
        Kp/Ti/Td updated only when field not focused (user may be editing).
        Auto SP/Disturbance/PID-enable synced from backend (simulation is
        authoritative — HMI is a view).
        """
        # --- PID enable (sync from backend) ---
        if pid_enabled is not None and self._pid_enable_cb.isChecked() != pid_enabled:
            self._pid_enable_cb.blockSignals(True)
            self._pid_enable_cb.setChecked(pid_enabled)
            self._pid_enable_cb.blockSignals(False)
            for ctrl in self._pid_controls:
                ctrl.setEnabled(pid_enabled)

        self._pid_pv_edit.setText(f"{pv:.2f}")
        if kp is not None and not self._pid_kp_edit.hasFocus():
            self._pid_kp_edit.setText(f"{kp:.2f}")
        if ti is not None and not self._pid_ti_edit.hasFocus():
            self._pid_ti_edit.setText(f"{ti:.1f}")
        if td is not None and not self._pid_td_edit.hasFocus():
            self._pid_td_edit.setText(f"{td:.1f}")
        if mode is not None:
            mode_str = "AUTO" if mode == 1 else "MAN"
            if mode_str != self._pid_active_mode:
                self._pid_active_mode = mode_str
                self._apply_pid_mode_style()
        # Only overwrite CO when PID is computing it (enabled + AUTO)
        if self._pid_enable_cb.isChecked() and self._pid_active_mode == "AUTO":
            self._pid_co_edit.blockSignals(True)
            self._pid_co_edit.setText(f"{co:.2f}")
            self._pid_co_edit.blockSignals(False)
        self._proc_in_edit.setText(f"{process_in:.2f}")
        self._proc_out_edit.setText(f"{process_out:.2f}")
        self._dist_out_edit.setText(f"{disturbance_out:.2f}")

        # --- Auto SP Variation (sync from backend) ---
        if auto_sp_enabled is not None and self._auto_sp_enable.isChecked() != auto_sp_enabled:
            self._auto_sp_enable.blockSignals(True)
            self._auto_sp_enable.setChecked(auto_sp_enabled)
            self._auto_sp_enable.blockSignals(False)
        if auto_sp_min is not None and not self._auto_sp_min.hasFocus():
            self._auto_sp_min.blockSignals(True)
            self._auto_sp_min.setText(f"{auto_sp_min:.1f}")
            self._auto_sp_min.blockSignals(False)
        if auto_sp_max is not None and not self._auto_sp_max.hasFocus():
            self._auto_sp_max.blockSignals(True)
            self._auto_sp_max.setText(f"{auto_sp_max:.1f}")
            self._auto_sp_max.blockSignals(False)

        if sp is not None:
            if self._auto_sp_enable.isChecked():
                # Auto SP active: working SP comes from the auto-variation algorithm
                self._pid_sp_wrk_edit.setText(f"{sp:.2f}")
                self._auto_sp_edit.setText(f"{sp:.2f}")
            else:
                # Manual SP: working SP = user's SP input
                self._pid_sp_wrk_edit.setText(self._pid_sp_edit.text())
                self._auto_sp_edit.setText(f"{sp:.2f}")

        # --- Auto Disturbance (sync from backend) ---
        if (
            auto_dist_enabled is not None
            and self._auto_dist_enable.isChecked() != auto_dist_enabled
        ):
            self._auto_dist_enable.blockSignals(True)
            self._auto_dist_enable.setChecked(auto_dist_enabled)
            self._auto_dist_enable.blockSignals(False)
        if auto_dist_amp is not None and not self._auto_dist_amp.hasFocus():
            self._auto_dist_amp.blockSignals(True)
            self._auto_dist_amp.setText(f"{auto_dist_amp:.1f}")
            self._auto_dist_amp.blockSignals(False)

        if abs(disturbance_out) > 1e-9:
            self._auto_dist_edit.setText(f"{disturbance_out:.2f}")

    def populate_from_status(self, status: ControllerSimStatus) -> None:
        """Populate widgets from a ControllerSimStatus DTO."""
        self._pid_sp_edit.setText(f"{getattr(status, 'pid_sp', 50.0):.1f}")
        self._pid_kp_edit.setText(f"{status.pid_kp:.2f}")
        self._pid_ti_edit.setText(f"{status.pid_ti:.1f}")
        self._pid_td_edit.setText(f"{status.pid_td:.1f}")
        self._pid_co_edit.setText(f"{status.pid_cv:.2f}")
        self._pid_active_mode = "AUTO" if status.pid_mode == 1 else "MAN"
        self._apply_pid_mode_style()
        if status.auto_sp is not None:
            self._auto_sp_enable.setChecked(status.auto_sp.enabled)
            self._auto_sp_min.setText(f"{status.auto_sp.sp_min_pct:.1f}")
            self._auto_sp_max.setText(f"{status.auto_sp.sp_max_pct:.1f}")
        if status.auto_disturbance is not None:
            self._auto_dist_enable.setChecked(status.auto_disturbance.enabled)
            self._auto_dist_amp.setText(f"{status.auto_disturbance.max_amplitude_pct:.1f}")

    @staticmethod
    def _build_block_diagram_svg(theme: ThemeBase) -> str:
        """Build an SVG block diagram showing the simulator signal flow."""
        fg = theme.fg_primary
        fg2 = theme.fg_secondary
        sp_c = theme.bar_sp
        pv_c = theme.bar_pv
        co_c = "#4FC3F7"
        dist_c = theme.alarm_warning
        bg = theme.bg_card

        return f"""\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 140">
  <rect width="560" height="140" fill="{bg}" rx="6"/>

  <!-- SP -->
  <text x="10" y="48" fill="{sp_c}" font-size="11" font-family="monospace">SP</text>
  <line x1="32" y1="44" x2="62" y2="44" stroke="{sp_c}" stroke-width="1.5"
        marker-end="url(#ah)"/>

  <!-- Summing junction -->
  <circle cx="74" cy="44" r="10" fill="none" stroke="{fg}" stroke-width="1.5"/>
  <text x="69" y="48" fill="{fg}" font-size="11" font-family="monospace">+</text>
  <text x="70" y="39" fill="{fg}" font-size="8" font-family="monospace">\u2212</text>

  <!-- Error -->
  <line x1="84" y1="44" x2="120" y2="44" stroke="{fg}" stroke-width="1.5"
        marker-end="url(#ah)"/>
  <text x="92" y="37" fill="{fg2}" font-size="9" font-family="monospace">e</text>

  <!-- PID Sim -->
  <rect x="120" y="26" width="80" height="36" rx="4" fill="none" stroke="{co_c}"
        stroke-width="1.5"/>
  <text x="130" y="49" fill="{co_c}" font-size="12" font-weight="bold"
        font-family="monospace">PID Sim</text>

  <!-- CO -->
  <line x1="200" y1="44" x2="250" y2="44" stroke="{co_c}" stroke-width="1.5"
        marker-end="url(#ah)"/>
  <text x="212" y="37" fill="{co_c}" font-size="9" font-family="monospace">CO</text>

  <!-- Process -->
  <rect x="250" y="26" width="90" height="36" rx="4" fill="none" stroke="{pv_c}"
        stroke-width="1.5"/>
  <text x="260" y="49" fill="{pv_c}" font-size="12" font-weight="bold"
        font-family="monospace">Process</text>

  <!-- Process out -->
  <line x1="340" y1="44" x2="380" y2="44" stroke="{pv_c}" stroke-width="1.5"
        marker-end="url(#ah)"/>

  <!-- Disturbance summing junction -->
  <circle cx="392" cy="44" r="10" fill="none" stroke="{fg}" stroke-width="1.5"/>
  <text x="387" y="48" fill="{fg}" font-size="11" font-family="monospace">+</text>

  <!-- Disturbance input -->
  <rect x="365" y="85" width="56" height="26" rx="4" fill="none" stroke="{dist_c}"
        stroke-width="1.5"/>
  <text x="370" y="103" fill="{dist_c}" font-size="10" font-weight="bold"
        font-family="monospace">D_OUT</text>
  <line x1="392" y1="85" x2="392" y2="54" stroke="{dist_c}" stroke-width="1.5"
        marker-end="url(#ah)"/>

  <!-- PV output -->
  <line x1="402" y1="44" x2="530" y2="44" stroke="{pv_c}" stroke-width="1.5"/>
  <text x="510" y="37" fill="{pv_c}" font-size="11" font-weight="bold"
        font-family="monospace">PV</text>

  <!-- PV feedback -->
  <line x1="530" y1="44" x2="530" y2="12" stroke="{pv_c}" stroke-width="1"/>
  <line x1="530" y1="12" x2="74" y2="12" stroke="{pv_c}" stroke-width="1"/>
  <line x1="74" y1="12" x2="74" y2="34" stroke="{pv_c}" stroke-width="1"
        marker-end="url(#ah)"/>

  <defs>
    <marker id="ah" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
      <path d="M0,0 L8,3 L0,6 Z" fill="{fg}"/>
    </marker>
  </defs>
</svg>"""

    def apply_theme(self, theme: ThemeBase) -> None:
        """Re-apply theme colors to dynamic elements."""
        self._theme = theme
        self._svg_widget.load(
            self._build_block_diagram_svg(theme).encode("utf-8"),
        )
