"""SimulatorPage — preset selection, parameter sliders, disturbance injection."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from smart_pid_domain.enums import ProcessPresetName
from smart_pid_domain.models.process_preset import PRESETS

if TYPE_CHECKING:
    from smart_pid_hmi.themes.base import ThemeBase

# Slider range config: (min, max, default, decimals)
_PARAM_RANGES = {
    "gain": (0.1, 10.0, 1.2, 2),
    "tau1": (0.5, 120.0, 3.0, 1),
    "tau2": (0.5, 60.0, 15.0, 1),
    "dead_time": (0.0, 30.0, 1.0, 1),
}

# Which presets are FOPTD (tau2 disabled)
_FOPTD_PRESETS = {ProcessPresetName.FLOW, ProcessPresetName.PRESSURE}


class SimulatorPage(QWidget):
    """Simulator control page with preset selection, parameters, and disturbances."""

    # Signals emitted to MainWindow for API calls
    preset_changed = Signal(str)  # preset name
    parameters_changed = Signal(float, float, float, float)  # gain, tau1, tau2, dead_time
    step_requested = Signal(float)  # amplitude
    noise_requested = Signal(float)  # amplitude
    clear_disturbance_requested = Signal()
    pid_enabled_changed = Signal(bool)
    pid_params_changed = Signal(float, float, float)  # Kp, Ti, Td
    pid_mode_changed = Signal(str)  # "MAN" or "AUTO"

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

        # Controller selector (populated externally)
        ctrl_row = QHBoxLayout()
        ctrl_row.addWidget(QLabel("Controller:"))
        self._controller_combo = QComboBox()
        ctrl_row.addWidget(self._controller_combo, stretch=1)
        layout.addLayout(ctrl_row)

        # Preset group
        preset_group = QGroupBox("Process Model Preset")
        preset_layout = QHBoxLayout(preset_group)
        preset_layout.addWidget(QLabel("Preset:"))
        self._preset_combo = QComboBox()
        for p in ProcessPresetName:
            self._preset_combo.addItem(p.value)
        self._preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        preset_layout.addWidget(self._preset_combo, stretch=1)
        layout.addWidget(preset_group)

        # Parameters group
        param_group = QGroupBox("Parameters")
        param_layout = QVBoxLayout(param_group)

        self._gain_slider = self._make_param_row(param_layout, "Gain (K):", "gain")
        self._tau1_slider = self._make_param_row(param_layout, "Tau1 (s):", "tau1")
        self._tau2_slider = self._make_param_row(param_layout, "Tau2 (s):", "tau2")
        self._dead_time_slider = self._make_param_row(param_layout, "Dead Time (s):", "dead_time")

        apply_btn = QPushButton("Apply Parameters")
        apply_btn.clicked.connect(self._on_apply_parameters)
        param_layout.addWidget(apply_btn)
        layout.addWidget(param_group)

        # Internal PID group
        pid_group = QGroupBox("Internal PID")
        pid_layout = QVBoxLayout(pid_group)

        # Enable + Mode row
        pid_top_row = QHBoxLayout()
        self._pid_enable_cb = QCheckBox("Enable PID")
        self._pid_enable_cb.setObjectName("pid_enable_cb")
        self._pid_enable_cb.setChecked(False)
        self._pid_enable_cb.toggled.connect(self._on_pid_enable_toggled)
        pid_top_row.addWidget(self._pid_enable_cb)
        pid_top_row.addWidget(QLabel("Mode:"))
        self._pid_mode_combo = QComboBox()
        self._pid_mode_combo.setObjectName("pid_mode_combo")
        self._pid_mode_combo.addItems(["MAN", "AUTO"])
        self._pid_mode_combo.currentTextChanged.connect(self._on_pid_mode_changed)
        pid_top_row.addWidget(self._pid_mode_combo)
        pid_layout.addLayout(pid_top_row)

        # Kp row
        kp_row = QHBoxLayout()
        kp_row.addWidget(QLabel("Kp:"))
        self._pid_kp_spin = QDoubleSpinBox()
        self._pid_kp_spin.setObjectName("pid_kp_spin")
        self._pid_kp_spin.setRange(0.01, 50.0)
        self._pid_kp_spin.setValue(1.0)
        self._pid_kp_spin.setDecimals(2)
        kp_row.addWidget(self._pid_kp_spin, stretch=1)
        pid_layout.addLayout(kp_row)

        # Ti row
        ti_row = QHBoxLayout()
        ti_row.addWidget(QLabel("Ti:"))
        self._pid_ti_spin = QDoubleSpinBox()
        self._pid_ti_spin.setObjectName("pid_ti_spin")
        self._pid_ti_spin.setRange(0.1, 999.0)
        self._pid_ti_spin.setValue(10.0)
        self._pid_ti_spin.setDecimals(1)
        self._pid_ti_spin.setSuffix(" s")
        ti_row.addWidget(self._pid_ti_spin, stretch=1)
        pid_layout.addLayout(ti_row)

        # Td row
        td_row = QHBoxLayout()
        td_row.addWidget(QLabel("Td:"))
        self._pid_td_spin = QDoubleSpinBox()
        self._pid_td_spin.setObjectName("pid_td_spin")
        self._pid_td_spin.setRange(0.0, 999.0)
        self._pid_td_spin.setValue(0.0)
        self._pid_td_spin.setDecimals(1)
        self._pid_td_spin.setSuffix(" s")
        td_row.addWidget(self._pid_td_spin, stretch=1)
        pid_layout.addLayout(td_row)

        # Apply button
        pid_apply_btn = QPushButton("Apply PID Parameters")
        pid_apply_btn.setObjectName("pid_apply_btn")
        pid_apply_btn.clicked.connect(self._on_pid_apply)
        pid_layout.addWidget(pid_apply_btn)

        layout.addWidget(pid_group)

        # Initial state: PID controls disabled
        self._pid_controls = [
            self._pid_mode_combo, self._pid_kp_spin,
            self._pid_ti_spin, self._pid_td_spin, pid_apply_btn,
        ]
        for ctrl in self._pid_controls:
            ctrl.setEnabled(False)

        # Disturbance group
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
        layout.addWidget(dist_group)

        # Status
        self._status_label = QLabel("Status: Ready")
        self._status_label.setStyleSheet(f"color: {theme.fg_secondary};")
        layout.addWidget(self._status_label)

        layout.addStretch()

        # Apply initial preset
        self._on_preset_changed(self._preset_combo.currentText())

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

    def _on_preset_selected(self, index: int) -> None:
        text = self._preset_combo.itemText(index)
        self._on_preset_changed(text)
        self.preset_changed.emit(text)

    def _on_preset_changed(self, preset_name: str) -> None:
        try:
            preset_enum = ProcessPresetName(preset_name)
        except ValueError:
            return

        is_foptd = preset_enum in _FOPTD_PRESETS
        self._tau2_slider.setEnabled(not is_foptd)

        if preset_enum != ProcessPresetName.CUSTOM and preset_enum in PRESETS:
            p = PRESETS[preset_enum]
            self._gain_slider.setValue(p.gain)
            self._tau1_slider.setValue(p.tau1)
            self._tau2_slider.setValue(p.tau2 if p.tau2 is not None else 0.0)
            self._dead_time_slider.setValue(p.dead_time)

    def _on_apply_parameters(self) -> None:
        tau2 = self._tau2_slider.value() if self._tau2_slider.isEnabled() else 0.0
        self.parameters_changed.emit(
            self._gain_slider.value(),
            self._tau1_slider.value(),
            tau2,
            self._dead_time_slider.value(),
        )

    def _on_step_inject(self) -> None:
        self.step_requested.emit(self._step_amplitude.value())

    def _on_noise_inject(self) -> None:
        self.noise_requested.emit(self._noise_amplitude.value())

    def _on_clear_disturbance(self) -> None:
        self.clear_disturbance_requested.emit()

    def _on_pid_enable_toggled(self, checked: bool) -> None:
        for ctrl in self._pid_controls:
            ctrl.setEnabled(checked)
        self.pid_enabled_changed.emit(checked)

    def _on_pid_apply(self) -> None:
        self.pid_params_changed.emit(
            self._pid_kp_spin.value(),
            self._pid_ti_spin.value(),
            self._pid_td_spin.value(),
        )

    def _on_pid_mode_changed(self, mode: str) -> None:
        self.pid_mode_changed.emit(mode)

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

    def apply_theme(self, theme: ThemeBase) -> None:
        """Re-apply theme colors to dynamic elements."""
        self._theme = theme
