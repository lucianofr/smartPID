"""Dialog for adding or editing a controller loop — all 30+ fields in tabbed layout."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStyle,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from smart_pid_domain.enums import (
    AIEngine,
    AlarmPriority,
    ControllerMode,
    ControlObjective,
    ExecutionMode,
    IntegralType,
    PIDStructure,
    ProcessSpeed,
    TuningWriteMode,
)


def _double_spin(
    min_v: float = -99999.0,
    max_v: float = 99999.0,
    value: float = 0.0,
    decimals: int = 3,
    suffix: str = "",
) -> QDoubleSpinBox:
    sb = QDoubleSpinBox()
    sb.setRange(min_v, max_v)
    sb.setValue(value)
    sb.setDecimals(decimals)
    if suffix:
        sb.setSuffix(suffix)
    return sb


def _enum_combo(enum_cls: type, default: str | None = None) -> QComboBox:
    cb = QComboBox()
    for member in enum_cls:
        cb.addItem(member.value)
    if default is not None:
        idx = cb.findText(default)
        if idx >= 0:
            cb.setCurrentIndex(idx)
    return cb


def _scrollable(form: QFormLayout) -> QScrollArea:
    """Wrap a form layout in a scroll area for tabs with many fields."""
    inner = QWidget()
    inner.setLayout(form)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(inner)
    return scroll


class ControllerDialog(QDialog):
    """Modal dialog to create or edit a controller via the REST API.

    Parameters
    ----------
    parent:
        Optional parent widget.
    edit_data:
        If provided, the dialog opens in **edit mode**: the name field is
        read-only, the title shows the tag name, and all fields are populated
        from *edit_data* (same dict shape as ``get_controller_data()``).
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        edit_data: dict | None = None,
    ) -> None:
        super().__init__(parent)
        self._edit_mode = edit_data is not None
        self.setMinimumWidth(640)
        self.setMinimumHeight(580)

        root = QVBoxLayout(self)
        self._tabs = QTabWidget()
        root.addWidget(self._tabs)

        # --- Tab 1: General ---
        self._tabs.addTab(self._build_general_tab(), "General")

        # --- Tab 2: PID Tuning (DDC only) ---
        self._pid_tab = self._build_pid_tab()
        self._tabs.addTab(self._pid_tab, "PID Tuning")

        # --- Tab 3: Scaling & Limits (DDC only) ---
        self._scaling_tab = self._build_scaling_tab()
        self._tabs.addTab(self._scaling_tab, "Scaling & Limits")

        # --- Tab 4: Filters & IO (DDC only) ---
        self._filters_tab = self._build_filters_io_tab()
        self._tabs.addTab(self._filters_tab, "Filters & IO")

        # --- Tab 5: AI Configuration ---
        self._tabs.addTab(self._build_ai_tab(), "AI Configuration")

        # --- Tab 6: Alarms ---
        self._tabs.addTab(self._build_alarms_tab(), "Alarms")

        # --- Tab 7: OPC-UA Tags ---
        self._tabs.addTab(self._build_opcua_tab(), "OPC-UA Tags")

        # --- Tab 7: Shed & Safety (DDC only) ---
        self._shed_tab = self._build_shed_tab()
        self._tabs.addTab(self._shed_tab, "Shed & Safety")

        # Track DDC-only tab indices for show/hide
        self._ddc_tab_indices: list[int] = []
        for i in range(self._tabs.count()):
            widget = self._tabs.widget(i)
            if widget in (self._pid_tab, self._scaling_tab,
                          self._filters_tab, self._shed_tab):
                self._ddc_tab_indices.append(i)

        # Apply initial mode visibility (default is SUPERVISORY)
        self._on_execution_mode_changed(self._execution_mode.currentText())

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        for btn in buttons.buttons():
            btn.setIcon(QIcon())
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        # Apply edit mode
        if self._edit_mode and edit_data is not None:
            self.setWindowTitle(f"Edit Controller \u2014 {edit_data.get('name', '')}")
            self._name.setReadOnly(True)
            self._populate(edit_data)
        else:
            self.setWindowTitle("Add Controller")

    # ------------------------------------------------------------------ tabs

    def _build_general_tab(self) -> QWidget:
        form = QFormLayout()

        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. TIC-101")
        form.addRow("Name:", self._name)

        self._description = QLineEdit()
        self._description.setPlaceholderText("optional")
        form.addRow("Description:", self._description)

        self._execution_mode = _enum_combo(
            ExecutionMode, ExecutionMode.SUPERVISORY.value,
        )
        self._execution_mode.currentTextChanged.connect(self._on_execution_mode_changed)
        form.addRow("Execution Mode:", self._execution_mode)

        self._scan_rate = QComboBox()
        _SCAN_RATES = [
            ("0.1 s", 100), ("0.5 s", 500), ("1 s", 1000), ("2 s", 2000),
            ("5 s", 5000), ("10 s", 10000), ("15 s", 15000), ("20 s", 20000),
            ("30 s", 30000), ("60 s", 60000),
        ]
        for label, ms in _SCAN_RATES:
            self._scan_rate.addItem(label, ms)
        self._scan_rate.setCurrentIndex(2)  # default 1s
        form.addRow("Scan Rate:", self._scan_rate)

        self._process_speed = QComboBox()
        for member in ProcessSpeed:
            self._process_speed.addItem(member.label, member.value)
        idx = self._process_speed.findData(ProcessSpeed.MEDIUM.value)
        if idx >= 0:
            self._process_speed.setCurrentIndex(idx)
        form.addRow("Process Speed:", self._process_speed)

        self._pid_structure = _enum_combo(PIDStructure, PIDStructure.ISA.value)
        self._pid_structure_label = QLabel("PID Structure:")
        form.addRow(self._pid_structure_label, self._pid_structure)

        self._integral_type = _enum_combo(IntegralType, IntegralType.TIME_TI.value)
        self._integral_type_label = QLabel("Integral Type:")
        form.addRow(self._integral_type_label, self._integral_type)

        self._mode_normal = _enum_combo(ControllerMode, ControllerMode.AUTO.value)
        form.addRow("Normal Mode:", self._mode_normal)

        return _scrollable(form)

    def _build_pid_tab(self) -> QWidget:
        form = QFormLayout()

        self._gain = _double_spin(0.001, 999.0, 1.0, 3)
        form.addRow("Gain (Kp):", self._gain)

        self._reset = _double_spin(0.1, 9999.0, 10.0, 1, " s")
        form.addRow("Reset (Ti):", self._reset)

        self._rate = _double_spin(0.0, 9999.0, 0.0, 1, " s")
        form.addRow("Rate (Td):", self._rate)

        self._alpha = _double_spin(0.05, 1.0, 0.125, 3)
        form.addRow("Alpha (filter):", self._alpha)

        self._deadband = _double_spin(0.0, 9999.0, 0.0, 3)
        form.addRow("Deadband:", self._deadband)

        return _scrollable(form)

    def _build_scaling_tab(self) -> QWidget:
        form = QFormLayout()

        # PV Scale
        grp_pv = QGroupBox("PV Scale")
        pv_form = QFormLayout()
        self._pv_eu_min = _double_spin(value=0.0)
        pv_form.addRow("EU Min:", self._pv_eu_min)
        self._pv_eu_max = _double_spin(value=100.0)
        pv_form.addRow("EU Max:", self._pv_eu_max)
        self._pv_unit = QLineEdit()
        self._pv_unit.setPlaceholderText("e.g. degC")
        pv_form.addRow("Unit:", self._pv_unit)
        grp_pv.setLayout(pv_form)
        form.addRow(grp_pv)

        # OUT Scale
        grp_out = QGroupBox("Output Scale")
        out_form = QFormLayout()
        self._out_eu_min = _double_spin(value=0.0)
        out_form.addRow("EU Min:", self._out_eu_min)
        self._out_eu_max = _double_spin(value=100.0)
        out_form.addRow("EU Max:", self._out_eu_max)
        self._out_unit = QLineEdit()
        self._out_unit.setPlaceholderText("e.g. %")
        out_form.addRow("Unit:", self._out_unit)
        grp_out.setLayout(out_form)
        form.addRow(grp_out)

        # SP limits
        self._sp_hi = _double_spin(value=100.0)
        form.addRow("SP High Limit:", self._sp_hi)
        self._sp_lo = _double_spin(value=0.0)
        form.addRow("SP Low Limit:", self._sp_lo)

        # OUT limits
        self._out_hi = _double_spin(value=100.0)
        form.addRow("OUT High Limit:", self._out_hi)
        self._out_lo = _double_spin(value=0.0)
        form.addRow("OUT Low Limit:", self._out_lo)

        # ARW limits
        self._arw_hi = _double_spin(value=100.0)
        form.addRow("ARW High Limit:", self._arw_hi)
        self._arw_lo = _double_spin(value=0.0)
        form.addRow("ARW Low Limit:", self._arw_lo)

        # SP rate limits
        self._sp_rate_up = _double_spin(0.0, 99999.0, 0.0, 2, " /s")
        form.addRow("SP Rate Up:", self._sp_rate_up)
        self._sp_rate_dn = _double_spin(0.0, 99999.0, 0.0, 2, " /s")
        form.addRow("SP Rate Down:", self._sp_rate_dn)

        return _scrollable(form)

    def _build_filters_io_tab(self) -> QWidget:
        form = QFormLayout()

        self._pv_ftime = _double_spin(0.0, 9999.0, 0.0, 2, " s")
        form.addRow("PV Filter Time:", self._pv_ftime)

        self._sp_ftime = _double_spin(0.0, 9999.0, 0.0, 2, " s")
        form.addRow("SP Filter Time:", self._sp_ftime)

        self._low_cut = _double_spin(0.0, 9999.0, 0.0, 2)
        form.addRow("Low Cutoff:", self._low_cut)

        self._ff_enable = QCheckBox("Enable Feedforward")
        form.addRow(self._ff_enable)

        self._ff_gain = _double_spin(0.0, 999.0, 1.0, 3)
        form.addRow("FF Gain:", self._ff_gain)

        # IO Options
        grp_io = QGroupBox("IO Options")
        io_form = QFormLayout()
        self._io_low_cutoff = QCheckBox("Low Cutoff")
        io_form.addRow(self._io_low_cutoff)
        self._io_increase_to_close = QCheckBox("Increase to Close")
        io_form.addRow(self._io_increase_to_close)
        self._io_target_to_man = QCheckBox("Target to MAN if Fault")
        io_form.addRow(self._io_target_to_man)
        self._io_fault_state_value = QCheckBox("Fault State to Value")
        io_form.addRow(self._io_fault_state_value)
        grp_io.setLayout(io_form)
        form.addRow(grp_io)

        # Control Options
        grp_ctrl = QGroupBox("Control Options")
        ctrl_form = QFormLayout()
        self._ctrl_direct_acting = QCheckBox("Direct Acting")
        ctrl_form.addRow(self._ctrl_direct_acting)
        self._ctrl_track_enable = QCheckBox("Track Enable")
        ctrl_form.addRow(self._ctrl_track_enable)
        self._ctrl_track_in_manual = QCheckBox("Track in Manual")
        ctrl_form.addRow(self._ctrl_track_in_manual)
        self._ctrl_sp_pv_track_man = QCheckBox("SP/PV Track in MAN")
        ctrl_form.addRow(self._ctrl_sp_pv_track_man)
        self._ctrl_sp_pv_track_lo_iman = QCheckBox(
            "SP/PV Track in LO/IMAN"
        )
        ctrl_form.addRow(self._ctrl_sp_pv_track_lo_iman)
        grp_ctrl.setLayout(ctrl_form)
        form.addRow(grp_ctrl)

        return _scrollable(form)

    def _build_ai_tab(self) -> QWidget:
        form = QFormLayout()

        self._ai_engine = _enum_combo(AIEngine, AIEngine.NONE.value)
        form.addRow("AI Engine:", self._ai_engine)

        self._ai_objective = _enum_combo(
            ControlObjective, ControlObjective.DISTURBANCE_REJECTION.value
        )
        form.addRow("Objective:", self._ai_objective)

        self._ai_dead_time = _double_spin(0.0, 9999.0, 1.0, 2, " s")
        form.addRow("Dead Time (L):", self._ai_dead_time)

        self._ai_limit_min = _double_spin(0.001, 9999.0, 0.1, 3)
        form.addRow("Limit Min:", self._ai_limit_min)

        self._ai_limit_max = _double_spin(0.001, 9999.0, 100.0, 3)
        form.addRow("Limit Max:", self._ai_limit_max)

        return _scrollable(form)

    def _build_alarms_tab(self) -> QWidget:
        from PySide6.QtWidgets import QGridLayout

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        # Deadband at top
        db_row = QHBoxLayout()
        db_row.addWidget(QLabel("Deadband (%):"))
        self._alarm_deadband = _double_spin(0.0, 50.0, 1.0, 1, " %")
        self._alarm_deadband.setFixedWidth(120)
        db_row.addWidget(self._alarm_deadband)
        db_row.addStretch()
        layout.addLayout(db_row)

        # Grid with headers
        grid = QGridLayout()
        grid.setSpacing(4)
        grid.setContentsMargins(4, 4, 4, 4)
        headers = ["Alarm", "On", "Limit", "Priority", "Delay On (s)", "Delay Off (s)"]
        for col, header in enumerate(headers):
            lbl = QLabel(f"<b>{header}</b>")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(lbl, 0, col)

        alarm_types = [
            ("HIHI", "hihi"), ("HI", "hi"), ("LO", "lo"),
            ("LOLO", "lolo"), ("DV High", "dv_hi"), ("DV Low", "dv_lo"),
        ]

        self._alarm_fields: dict[
            str,
            tuple[QCheckBox, QLineEdit, QComboBox, QDoubleSpinBox, QDoubleSpinBox],
        ] = {}

        for row, (display, key) in enumerate(alarm_types, start=1):
            grid.addWidget(QLabel(display), row, 0)

            chk = QCheckBox()
            grid.addWidget(chk, row, 1, Qt.AlignmentFlag.AlignCenter)

            limit_edit = QLineEdit("0.0")
            limit_edit.setFixedWidth(80)
            limit_edit.setAlignment(Qt.AlignmentFlag.AlignRight)
            grid.addWidget(limit_edit, row, 2)

            combo = QComboBox()
            for p in AlarmPriority:
                combo.addItem(p.value)
            combo.setCurrentText("WARNING")
            grid.addWidget(combo, row, 3)

            delay_on = _double_spin(0.0, 9999.0, 0.0, 1, " s")
            delay_on.setFixedWidth(100)
            grid.addWidget(delay_on, row, 4)

            delay_off = _double_spin(0.0, 9999.0, 0.0, 1, " s")
            delay_off.setFixedWidth(100)
            grid.addWidget(delay_off, row, 5)

            self._alarm_fields[key] = (chk, limit_edit, combo, delay_on, delay_off)

        layout.addLayout(grid)
        layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        return scroll

    def _build_opcua_tab(self) -> QWidget:
        from PySide6.QtWidgets import QGridLayout
        grid = QGridLayout()
        grid.setSpacing(6)

        tag_fields = [
            ("PV", "ns=2;s=PV"), ("SP", "ns=2;s=SP"), ("CO", "ns=2;s=CO"),
            ("Integral", ""), ("BkCal In", ""), ("BkCal Out", ""),
            ("Kp", ""), ("Ti", ""), ("Td", ""), ("Mode", ""),
        ]
        attr_map = {
            "PV": "_tag_pv", "SP": "_tag_sp", "CO": "_tag_co",
            "Integral": "_tag_integral", "BkCal In": "_tag_bkcal_in",
            "BkCal Out": "_tag_bkcal_out", "Kp": "_tag_kp",
            "Ti": "_tag_ti", "Td": "_tag_td", "Mode": "_tag_mode",
        }

        for row_idx, (label, placeholder) in enumerate(tag_fields):
            lbl = QLabel(f"{label}:")
            grid.addWidget(lbl, row_idx, 0)

            line_edit = QLineEdit()
            line_edit.setPlaceholderText(placeholder)
            setattr(self, attr_map[label], line_edit)
            grid.addWidget(line_edit, row_idx, 1)

            browse_btn = QPushButton("Browse")
            browse_btn.setFixedWidth(60)
            browse_btn.setToolTip(f"Browse OPC-UA for {label}")
            browse_btn.clicked.connect(
                lambda _=False, le=line_edit: self._open_tag_browse(le),
            )
            grid.addWidget(browse_btn, row_idx, 2)

        container = QWidget()
        container.setLayout(grid)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        return scroll

    def _open_tag_browse(self, target_line_edit: QLineEdit) -> None:
        """Open the tag browse dialog and set result into the target field."""
        from smart_pid_hmi.widgets.tag_browse_dialog import TagBrowseDialog

        # Try to get browse/search functions from parent MainWindow's api_client
        browse_fn = None
        search_fn = None
        main_win = self.parent()
        if main_win and hasattr(main_win, "_api_client"):
            api = main_win._api_client  # noqa: SLF001
            if hasattr(api, "browse_opcua"):
                browse_fn = api.browse_opcua
            if hasattr(api, "search_opcua"):
                search_fn = api.search_opcua

        dlg = TagBrowseDialog(
            browse_fn=browse_fn, search_fn=search_fn, parent=self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_node_id:
            target_line_edit.setText(dlg.selected_node_id)

    def _build_shed_tab(self) -> QWidget:
        form = QFormLayout()

        self._shed_opt = _enum_combo(ControllerMode, ControllerMode.MAN.value)
        form.addRow("Shed Option:", self._shed_opt)

        self._shed_time = _double_spin(0.0, 9999.0, 10.0, 1, " s")
        form.addRow("Shed Time:", self._shed_time)

        self._tuning_write_mode = _enum_combo(
            TuningWriteMode, TuningWriteMode.APPROVAL_REQUIRED.value
        )
        form.addRow("Tuning Write Mode:", self._tuning_write_mode)

        self._max_tuning_pct = _double_spin(0.0, 100.0, 10.0, 1, " %")
        form.addRow("Max Tuning Change %:", self._max_tuning_pct)

        return _scrollable(form)

    # --------------------------------------------------------- mode toggle

    def _on_execution_mode_changed(self, mode_text: str) -> None:
        """Show/hide DDC-only tabs and fields based on execution mode."""
        is_ddc = mode_text == ExecutionMode.DDC.value

        # DDC-only tabs: remove or re-add
        # Strategy: store tabs, remove all DDC tabs, re-add if DDC
        # Simpler: use setTabVisible (Qt 5.15+/PySide6)
        for i in range(self._tabs.count()):
            widget = self._tabs.widget(i)
            if widget in (self._pid_tab, self._scaling_tab,
                          self._filters_tab, self._shed_tab):
                self._tabs.setTabVisible(i, is_ddc)

        # DDC-only fields in General tab
        self._pid_structure.setVisible(is_ddc)
        self._pid_structure_label.setVisible(is_ddc)
        self._integral_type.setVisible(is_ddc)
        self._integral_type_label.setVisible(is_ddc)

    # ------------------------------------------------------------ populate

    def _populate(self, data: dict) -> None:
        """Set all form fields from a data dict (same shape as get_controller_data)."""
        # General
        self._name.setText(data.get("name", ""))
        self._description.setText(data.get("description", ""))
        self._set_combo(self._execution_mode, data.get("execution_mode"))
        if "scan_rate_ms" in data:
            idx = self._scan_rate.findData(data["scan_rate_ms"])
            if idx >= 0:
                self._scan_rate.setCurrentIndex(idx)
        if "process_speed" in data:
            idx = self._process_speed.findData(data["process_speed"])
            if idx >= 0:
                self._process_speed.setCurrentIndex(idx)
        self._set_combo(self._pid_structure, data.get("pid_structure"))
        self._set_combo(self._integral_type, data.get("integral_type"))
        self._set_combo(self._mode_normal, data.get("mode_normal"))

        # PID Tuning
        pid = data.get("pid_params", {})
        if "gain" in pid:
            self._gain.setValue(pid["gain"])
        if "reset" in pid:
            self._reset.setValue(pid["reset"])
        if "rate" in pid:
            self._rate.setValue(pid["rate"])
        if "alpha" in pid:
            self._alpha.setValue(pid["alpha"])
        if "deadband" in pid:
            self._deadband.setValue(pid["deadband"])

        # PV Scale
        pv = data.get("pv_scale", {})
        if "eu_min" in pv:
            self._pv_eu_min.setValue(pv["eu_min"])
        if "eu_max" in pv:
            self._pv_eu_max.setValue(pv["eu_max"])
        self._pv_unit.setText(pv.get("unit", ""))

        # OUT Scale
        out = data.get("out_scale", {})
        if "eu_min" in out:
            self._out_eu_min.setValue(out["eu_min"])
        if "eu_max" in out:
            self._out_eu_max.setValue(out["eu_max"])
        self._out_unit.setText(out.get("unit", ""))

        # Limits
        for attr, key in [
            ("_sp_hi", "sp_hi_lim"),
            ("_sp_lo", "sp_lo_lim"),
            ("_out_hi", "out_hi_lim"),
            ("_out_lo", "out_lo_lim"),
            ("_arw_hi", "arw_hi_lim"),
            ("_arw_lo", "arw_lo_lim"),
            ("_sp_rate_up", "sp_rate_up"),
            ("_sp_rate_dn", "sp_rate_dn"),
        ]:
            if key in data:
                getattr(self, attr).setValue(data[key])

        # Filters
        for attr, key in [
            ("_pv_ftime", "pv_ftime"),
            ("_sp_ftime", "sp_ftime"),
            ("_low_cut", "low_cut"),
            ("_ff_gain", "ff_gain"),
        ]:
            if key in data:
                getattr(self, attr).setValue(data[key])
        if "ff_enable" in data:
            self._ff_enable.setChecked(data["ff_enable"])

        # IO Options
        io = data.get("io_opts", {})
        self._io_low_cutoff.setChecked(io.get("low_cutoff", False))
        self._io_increase_to_close.setChecked(io.get("increase_to_close", False))
        self._io_target_to_man.setChecked(io.get("target_to_man_if_fault", False))
        self._io_fault_state_value.setChecked(io.get("fault_state_to_value", False))

        # Control Options
        ctrl = data.get("control_opts", {})
        self._ctrl_direct_acting.setChecked(ctrl.get("direct_acting", False))
        self._ctrl_track_enable.setChecked(ctrl.get("track_enable", False))
        self._ctrl_track_in_manual.setChecked(ctrl.get("track_in_manual", False))
        self._ctrl_sp_pv_track_man.setChecked(ctrl.get("sp_pv_track_in_man", False))
        self._ctrl_sp_pv_track_lo_iman.setChecked(
            ctrl.get("sp_pv_track_in_lo_or_iman", False)
        )

        # AI Config
        ai = data.get("ai_config", {})
        self._set_combo(self._ai_engine, ai.get("engine"))
        self._set_combo(self._ai_objective, ai.get("objective"))
        if "dead_time_l" in ai:
            self._ai_dead_time.setValue(ai["dead_time_l"])
        if "limit_min" in ai:
            self._ai_limit_min.setValue(ai["limit_min"])
        if "limit_max" in ai:
            self._ai_limit_max.setValue(ai["limit_max"])

        # OPC-UA Tag Bindings
        tags = data.get("tag_bindings", {})
        tag_map = {
            "node_id_pv": self._tag_pv,
            "node_id_sp": self._tag_sp,
            "node_id_co": self._tag_co,
            "node_id_integral": self._tag_integral,
            "node_id_bkcal_in": self._tag_bkcal_in,
            "node_id_bkcal_out": self._tag_bkcal_out,
            "node_id_kp": self._tag_kp,
            "node_id_ti": self._tag_ti,
            "node_id_td": self._tag_td,
            "node_id_mode": self._tag_mode,
        }
        for key, widget in tag_map.items():
            widget.setText(tags.get(key, ""))

        # Alarms
        alarms = data.get("alarm_config", {})
        if "deadband_percent" in alarms:
            self._alarm_deadband.setValue(alarms["deadband_percent"])
        for key, (chk, limit_edit, combo, delay_on, delay_off) in self._alarm_fields.items():
            if f"{key}_enabled" in alarms:
                chk.setChecked(alarms[f"{key}_enabled"])
            if f"{key}_value" in alarms:
                limit_edit.setText(str(alarms[f"{key}_value"]))
            if f"{key}_priority" in alarms:
                self._set_combo(combo, alarms[f"{key}_priority"])
            if f"{key}_delay_on_s" in alarms:
                delay_on.setValue(float(alarms[f"{key}_delay_on_s"]))
            if f"{key}_delay_off_s" in alarms:
                delay_off.setValue(float(alarms[f"{key}_delay_off_s"]))

        # Shed & Safety
        self._set_combo(self._shed_opt, data.get("shed_opt"))
        if "shed_time_s" in data:
            self._shed_time.setValue(data["shed_time_s"])
        self._set_combo(self._tuning_write_mode, data.get("tuning_write_mode"))
        if "max_tuning_change_pct" in data:
            self._max_tuning_pct.setValue(data["max_tuning_change_pct"])

    @staticmethod
    def _set_combo(combo: QComboBox, value: str | None) -> None:
        """Set a combo box to the item matching *value* (no-op if not found)."""
        if value is None:
            return
        idx = combo.findText(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    # --------------------------------------------------------- data extraction

    def get_controller_data(self) -> dict:
        """Return form data as a dict matching Controller model field names."""
        return {
            # General
            "name": self._name.text().strip(),
            "description": self._description.text().strip(),
            "execution_mode": self._execution_mode.currentText(),
            "scan_rate_ms": self._scan_rate.currentData(),
            "process_speed": self._process_speed.currentData(),
            "pid_structure": self._pid_structure.currentText(),
            "integral_type": self._integral_type.currentText(),
            "mode_normal": self._mode_normal.currentText(),
            # PID Tuning
            "pid_params": {
                "gain": self._gain.value(),
                "reset": self._reset.value(),
                "rate": self._rate.value(),
                "alpha": self._alpha.value(),
                "deadband": self._deadband.value(),
            },
            # Scaling
            "pv_scale": {
                "eu_min": self._pv_eu_min.value(),
                "eu_max": self._pv_eu_max.value(),
                "unit": self._pv_unit.text().strip(),
            },
            "out_scale": {
                "eu_min": self._out_eu_min.value(),
                "eu_max": self._out_eu_max.value(),
                "unit": self._out_unit.text().strip(),
            },
            # Limits
            "sp_hi_lim": self._sp_hi.value(),
            "sp_lo_lim": self._sp_lo.value(),
            "out_hi_lim": self._out_hi.value(),
            "out_lo_lim": self._out_lo.value(),
            "arw_hi_lim": self._arw_hi.value(),
            "arw_lo_lim": self._arw_lo.value(),
            "sp_rate_up": self._sp_rate_up.value(),
            "sp_rate_dn": self._sp_rate_dn.value(),
            # Filters & IO
            "pv_ftime": self._pv_ftime.value(),
            "sp_ftime": self._sp_ftime.value(),
            "low_cut": self._low_cut.value(),
            "ff_enable": self._ff_enable.isChecked(),
            "ff_gain": self._ff_gain.value(),
            "io_opts": {
                "low_cutoff": self._io_low_cutoff.isChecked(),
                "increase_to_close": self._io_increase_to_close.isChecked(),
                "target_to_man_if_fault": self._io_target_to_man.isChecked(),
                "fault_state_to_value": self._io_fault_state_value.isChecked(),
            },
            "control_opts": {
                "direct_acting": self._ctrl_direct_acting.isChecked(),
                "track_enable": self._ctrl_track_enable.isChecked(),
                "track_in_manual": self._ctrl_track_in_manual.isChecked(),
                "sp_pv_track_in_man": self._ctrl_sp_pv_track_man.isChecked(),
                "sp_pv_track_in_lo_or_iman": (
                    self._ctrl_sp_pv_track_lo_iman.isChecked()
                ),
            },
            # AI
            "ai_config": {
                "engine": self._ai_engine.currentText(),
                "objective": self._ai_objective.currentText(),
                "dead_time_l": self._ai_dead_time.value(),
                "limit_min": self._ai_limit_min.value(),
                "limit_max": self._ai_limit_max.value(),
            },
            # OPC-UA Tags
            "tag_bindings": {
                "node_id_pv": self._tag_pv.text().strip(),
                "node_id_sp": self._tag_sp.text().strip(),
                "node_id_co": self._tag_co.text().strip(),
                "node_id_integral": self._tag_integral.text().strip(),
                "node_id_bkcal_in": self._tag_bkcal_in.text().strip(),
                "node_id_bkcal_out": self._tag_bkcal_out.text().strip(),
                "node_id_kp": self._tag_kp.text().strip(),
                "node_id_ti": self._tag_ti.text().strip(),
                "node_id_td": self._tag_td.text().strip(),
                "node_id_mode": self._tag_mode.text().strip(),
            },
            # Alarms
            "alarm_config": self._get_alarm_data(),
            # Shed & Safety
            "shed_opt": self._shed_opt.currentText(),
            "shed_time_s": self._shed_time.value(),
            "tuning_write_mode": self._tuning_write_mode.currentText(),
            "max_tuning_change_pct": self._max_tuning_pct.value(),
        }

    def _get_alarm_data(self) -> dict:
        """Collect alarm configuration from the Alarms tab."""
        result: dict[str, object] = {
            "deadband_percent": self._alarm_deadband.value(),
        }
        for key, (chk, limit_edit, combo, delay_on, delay_off) in self._alarm_fields.items():
            result[f"{key}_enabled"] = chk.isChecked()
            try:
                result[f"{key}_value"] = float(limit_edit.text())
            except ValueError:
                result[f"{key}_value"] = 0.0
            result[f"{key}_priority"] = combo.currentText()
            result[f"{key}_delay_on_s"] = delay_on.value()
            result[f"{key}_delay_off_s"] = delay_off.value()
        return result

    # Keep backward compat with callers using the old method name
    def get_data(self) -> dict:
        """Alias for get_controller_data (backward compatibility)."""
        return self.get_controller_data()

    def accept(self) -> None:
        if not self._edit_mode and not self._name.text().strip():
            self._name.setFocus()
            self._name.setStyleSheet("border: 1px solid red;")
            return
        super().accept()


# Backward compatibility alias
AddControllerDialog = ControllerDialog
