"""Tests for ControllerDialog — create + edit mode, full 30+ field coverage."""
import pytest

from smart_pid_hmi.widgets.controller_dialog import ControllerDialog

# ---------------------------------------------------------------- fixtures

EDIT_DATA: dict = {
    "name": "TIC-101",
    "description": "Temperature loop",
    "execution_mode": "SUPERVISORY",
    "scan_rate_ms": 500,
    "pid_structure": "PARALLEL",
    "integral_type": "GAIN_KI",
    "mode_normal": "MAN",
    "pid_params": {
        "gain": 2.5,
        "reset": 5.0,
        "rate": 1.0,
        "alpha": 0.1,
        "deadband": 0.5,
    },
    "pv_scale": {"eu_min": -50.0, "eu_max": 200.0, "unit": "degC"},
    "out_scale": {"eu_min": 0.0, "eu_max": 100.0, "unit": "%"},
    "process_speed": "SLOW",
    "ai_config": {
        "engine": "FUZZY",
        "objective": "SP_TRACKING",
        "dead_time_l": 5.0,
        "limit_min": 0.5,
        "limit_max": 50.0,
    },
    "tag_bindings": {
        "node_id_pv": "ns=2;s=TIC101.PV",
        "node_id_sp": "ns=2;s=TIC101.SP",
        "node_id_co": "",
        "node_id_integral": "",
        "node_id_bkcal_in": "",
        "node_id_bkcal_out": "",
        "node_id_kp": "",
        "node_id_ti": "",
        "node_id_td": "",
        "node_id_mode": "",
    },
    "control_opts": {
        "direct_acting": True,
        "track_enable": False,
        "track_in_manual": False,
        "sp_pv_track_in_man": False,
        "sp_pv_track_in_lo_or_iman": False,
    },
    "io_opts": {
        "low_cutoff": False,
        "increase_to_close": True,
        "target_to_man_if_fault": False,
        "fault_state_to_value": False,
    },
    "sp_hi_lim": 200.0,
    "sp_lo_lim": -50.0,
    "out_hi_lim": 100.0,
    "out_lo_lim": 0.0,
    "arw_hi_lim": 110.0,
    "arw_lo_lim": -10.0,
    "sp_rate_up": 1.0,
    "sp_rate_dn": 1.0,
    "pv_ftime": 2.0,
    "sp_ftime": 0.5,
    "low_cut": 0.1,
    "ff_enable": True,
    "ff_gain": 0.8,
    "shed_opt": "AUTO",
    "shed_time_s": 30.0,
    "tuning_write_mode": "approval_required",
    "max_tuning_change_pct": 15.0,
}


@pytest.fixture
def dialog(qtbot):
    dlg = ControllerDialog()
    qtbot.addWidget(dlg)
    return dlg


@pytest.fixture
def edit_dialog(qtbot):
    dlg = ControllerDialog(edit_data=EDIT_DATA)
    qtbot.addWidget(dlg)
    return dlg


# ============================================================ Create mode
# (mirrors all tests from test_add_controller_dialog.py)


class TestDialogCreation:
    """Verify the dialog is created with all tabs and expected widgets."""

    def test_window_title(self, dialog):
        assert dialog.windowTitle() == "Add Controller"

    def test_has_seven_tabs(self, dialog):
        from PySide6.QtWidgets import QTabWidget

        tabs = dialog.findChild(QTabWidget)
        assert tabs is not None
        assert tabs.count() == 7

    def test_tab_labels(self, dialog):
        from PySide6.QtWidgets import QTabWidget

        tabs = dialog.findChild(QTabWidget)
        labels = [tabs.tabText(i) for i in range(tabs.count())]
        assert labels == [
            "General",
            "PID Tuning",
            "Scaling & Limits",
            "Filters & IO",
            "AI Configuration",
            "OPC-UA Tags",
            "Shed & Safety",
        ]


class TestDefaults:
    """Verify sensible defaults match domain model defaults."""

    def test_default_scan_rate(self, dialog):
        assert dialog._scan_rate.value() == 1000

    def test_default_gain(self, dialog):
        assert dialog._gain.value() == 1.0

    def test_default_reset(self, dialog):
        assert dialog._reset.value() == 10.0

    def test_default_rate(self, dialog):
        assert dialog._rate.value() == 0.0

    def test_default_alpha(self, dialog):
        assert dialog._alpha.value() == pytest.approx(0.125, abs=0.01)

    def test_default_sp_limits(self, dialog):
        assert dialog._sp_lo.value() == 0.0
        assert dialog._sp_hi.value() == 100.0

    def test_default_out_limits(self, dialog):
        assert dialog._out_lo.value() == 0.0
        assert dialog._out_hi.value() == 100.0

    def test_default_arw_limits(self, dialog):
        assert dialog._arw_lo.value() == 0.0
        assert dialog._arw_hi.value() == 100.0

    def test_default_execution_mode(self, dialog):
        assert dialog._execution_mode.currentText() == "SUPERVISORY"

    def test_default_pid_structure(self, dialog):
        assert dialog._pid_structure.currentText() == "ISA"

    def test_default_ai_engine(self, dialog):
        assert dialog._ai_engine.currentText() == "NONE"

    def test_default_shed_time(self, dialog):
        assert dialog._shed_time.value() == 10.0

    def test_default_max_tuning_pct(self, dialog):
        assert dialog._max_tuning_pct.value() == 10.0


class TestGetControllerData:
    """Verify get_controller_data returns dict with all expected keys."""

    def test_returns_all_top_level_keys(self, dialog):
        data = dialog.get_controller_data()
        expected_keys = {
            "name", "description", "execution_mode", "scan_rate_ms",
            "pid_structure", "integral_type", "mode_normal",
            "pid_params", "pv_scale", "out_scale",
            "sp_hi_lim", "sp_lo_lim", "out_hi_lim", "out_lo_lim",
            "arw_hi_lim", "arw_lo_lim", "sp_rate_up", "sp_rate_dn",
            "pv_ftime", "sp_ftime", "low_cut",
            "ff_enable", "ff_gain",
            "io_opts", "control_opts",
            "ai_config", "tag_bindings",
            "shed_opt", "shed_time_s",
            "tuning_write_mode", "max_tuning_change_pct",
        }
        assert set(data.keys()) == expected_keys

    def test_pid_params_sub_keys(self, dialog):
        data = dialog.get_controller_data()
        assert set(data["pid_params"].keys()) == {
            "gain", "reset", "rate", "alpha", "deadband",
        }

    def test_ai_config_sub_keys(self, dialog):
        data = dialog.get_controller_data()
        assert set(data["ai_config"].keys()) == {
            "engine", "objective",
            "dead_time_l", "limit_min", "limit_max",
        }

    def test_tag_bindings_sub_keys(self, dialog):
        data = dialog.get_controller_data()
        assert set(data["tag_bindings"].keys()) == {
            "node_id_pv", "node_id_sp", "node_id_co",
            "node_id_integral", "node_id_bkcal_in", "node_id_bkcal_out",
            "node_id_kp", "node_id_ti", "node_id_td", "node_id_mode",
        }

    def test_io_opts_sub_keys(self, dialog):
        data = dialog.get_controller_data()
        assert set(data["io_opts"].keys()) == {
            "low_cutoff", "increase_to_close",
            "target_to_man_if_fault", "fault_state_to_value",
        }

    def test_control_opts_sub_keys(self, dialog):
        data = dialog.get_controller_data()
        assert set(data["control_opts"].keys()) == {
            "direct_acting", "track_enable", "track_in_manual",
            "sp_pv_track_in_man", "sp_pv_track_in_lo_or_iman",
        }

    def test_pv_scale_sub_keys(self, dialog):
        data = dialog.get_controller_data()
        assert set(data["pv_scale"].keys()) == {"eu_min", "eu_max", "unit"}

    def test_out_scale_sub_keys(self, dialog):
        data = dialog.get_controller_data()
        assert set(data["out_scale"].keys()) == {"eu_min", "eu_max", "unit"}

    def test_total_field_count_at_least_30(self, dialog):
        """Count all leaf values (not sub-dicts) to confirm 30+ fields."""
        data = dialog.get_controller_data()
        count = 0
        for v in data.values():
            if isinstance(v, dict):
                count += len(v)
            else:
                count += 1
        assert count >= 30

    def test_get_data_is_alias(self, dialog):
        """get_data() should return the same result as get_controller_data()."""
        assert dialog.get_data() == dialog.get_controller_data()


class TestEditing:
    """Verify that editing fields is reflected in get_controller_data."""

    def test_name_is_captured(self, dialog):
        dialog._name.setText("FIC-200")
        data = dialog.get_controller_data()
        assert data["name"] == "FIC-200"

    def test_scan_rate_change(self, dialog):
        dialog._scan_rate.setValue(500)
        assert dialog.get_controller_data()["scan_rate_ms"] == 500

    def test_checkbox_ff_enable(self, dialog):
        dialog._ff_enable.setChecked(True)
        assert dialog.get_controller_data()["ff_enable"] is True

    def test_checkbox_direct_acting(self, dialog):
        dialog._ctrl_direct_acting.setChecked(True)
        data = dialog.get_controller_data()
        assert data["control_opts"]["direct_acting"] is True

    def test_opcua_tag_captured(self, dialog):
        dialog._tag_pv.setText("ns=2;s=MYLOOP.PV")
        data = dialog.get_controller_data()
        assert data["tag_bindings"]["node_id_pv"] == "ns=2;s=MYLOOP.PV"


class TestValidation:
    """Verify basic validation behavior."""

    def test_accept_blocked_without_name(self, dialog):
        dialog._name.setText("")
        dialog.accept()
        assert dialog.isVisible() or not dialog.result()

    def test_accept_allowed_with_name(self, dialog, qtbot):
        dialog._name.setText("TIC-101")
        dialog.accept()
        assert dialog.result() == 1


# ============================================================ Edit mode


class TestEditMode:
    """Verify edit-mode behavior: title, read-only name, populated fields."""

    # --- Title ---

    def test_edit_title(self, edit_dialog):
        assert "Edit Controller" in edit_dialog.windowTitle()
        assert "TIC-101" in edit_dialog.windowTitle()

    def test_create_mode_title(self, dialog):
        assert dialog.windowTitle() == "Add Controller"

    # --- Name field ---

    def test_name_readonly(self, edit_dialog):
        assert edit_dialog._name.isReadOnly()

    def test_create_mode_name_editable(self, dialog):
        assert not dialog._name.isReadOnly()

    # --- General tab populated ---

    def test_populated_name(self, edit_dialog):
        assert edit_dialog._name.text() == "TIC-101"

    def test_populated_description(self, edit_dialog):
        assert edit_dialog._description.text() == "Temperature loop"

    def test_populated_execution_mode(self, edit_dialog):
        assert edit_dialog._execution_mode.currentText() == "SUPERVISORY"

    def test_populated_scan_rate(self, edit_dialog):
        assert edit_dialog._scan_rate.value() == 500

    def test_populated_pid_structure(self, edit_dialog):
        assert edit_dialog._pid_structure.currentText() == "PARALLEL"

    def test_populated_integral_type(self, edit_dialog):
        assert edit_dialog._integral_type.currentText() == "GAIN_KI"

    def test_populated_mode_normal(self, edit_dialog):
        assert edit_dialog._mode_normal.currentText() == "MAN"

    # --- PID params ---

    def test_populated_gain(self, edit_dialog):
        assert edit_dialog._gain.value() == pytest.approx(2.5)

    def test_populated_reset(self, edit_dialog):
        assert edit_dialog._reset.value() == pytest.approx(5.0)

    def test_populated_rate(self, edit_dialog):
        assert edit_dialog._rate.value() == pytest.approx(1.0)

    def test_populated_alpha(self, edit_dialog):
        assert edit_dialog._alpha.value() == pytest.approx(0.1)

    def test_populated_deadband(self, edit_dialog):
        assert edit_dialog._deadband.value() == pytest.approx(0.5)

    # --- PV / OUT scale ---

    def test_populated_pv_scale(self, edit_dialog):
        assert edit_dialog._pv_eu_min.value() == pytest.approx(-50.0)
        assert edit_dialog._pv_eu_max.value() == pytest.approx(200.0)
        assert edit_dialog._pv_unit.text() == "degC"

    def test_populated_out_scale(self, edit_dialog):
        assert edit_dialog._out_eu_min.value() == pytest.approx(0.0)
        assert edit_dialog._out_eu_max.value() == pytest.approx(100.0)
        assert edit_dialog._out_unit.text() == "%"

    # --- Limits ---

    def test_populated_sp_limits(self, edit_dialog):
        assert edit_dialog._sp_hi.value() == pytest.approx(200.0)
        assert edit_dialog._sp_lo.value() == pytest.approx(-50.0)

    def test_populated_out_limits(self, edit_dialog):
        assert edit_dialog._out_hi.value() == pytest.approx(100.0)
        assert edit_dialog._out_lo.value() == pytest.approx(0.0)

    def test_populated_arw_limits(self, edit_dialog):
        assert edit_dialog._arw_hi.value() == pytest.approx(110.0)
        assert edit_dialog._arw_lo.value() == pytest.approx(-10.0)

    def test_populated_sp_rate(self, edit_dialog):
        assert edit_dialog._sp_rate_up.value() == pytest.approx(1.0)
        assert edit_dialog._sp_rate_dn.value() == pytest.approx(1.0)

    # --- Filters ---

    def test_populated_pv_ftime(self, edit_dialog):
        assert edit_dialog._pv_ftime.value() == pytest.approx(2.0)

    def test_populated_sp_ftime(self, edit_dialog):
        assert edit_dialog._sp_ftime.value() == pytest.approx(0.5)

    def test_populated_low_cut(self, edit_dialog):
        assert edit_dialog._low_cut.value() == pytest.approx(0.1)

    def test_populated_ff(self, edit_dialog):
        assert edit_dialog._ff_enable.isChecked() is True
        assert edit_dialog._ff_gain.value() == pytest.approx(0.8)

    # --- IO Options ---

    def test_populated_io_opts(self, edit_dialog):
        assert edit_dialog._io_low_cutoff.isChecked() is False
        assert edit_dialog._io_increase_to_close.isChecked() is True
        assert edit_dialog._io_target_to_man.isChecked() is False
        assert edit_dialog._io_fault_state_value.isChecked() is False

    # --- Control Options ---

    def test_populated_control_opts(self, edit_dialog):
        assert edit_dialog._ctrl_direct_acting.isChecked() is True
        assert edit_dialog._ctrl_track_enable.isChecked() is False
        assert edit_dialog._ctrl_track_in_manual.isChecked() is False
        assert edit_dialog._ctrl_sp_pv_track_man.isChecked() is False
        assert edit_dialog._ctrl_sp_pv_track_lo_iman.isChecked() is False

    # --- AI Config ---

    def test_populated_ai_config(self, edit_dialog):
        assert edit_dialog._ai_engine.currentText() == "FUZZY"
        assert edit_dialog._ai_objective.currentText() == "SP_TRACKING"
        assert edit_dialog._ai_speed.currentText() == "SLOW"
        assert edit_dialog._ai_dead_time.value() == pytest.approx(5.0)
        assert edit_dialog._ai_limit_min.value() == pytest.approx(0.5)
        assert edit_dialog._ai_limit_max.value() == pytest.approx(50.0)

    # --- Tag Bindings ---

    def test_populated_tag_bindings(self, edit_dialog):
        assert edit_dialog._tag_pv.text() == "ns=2;s=TIC101.PV"
        assert edit_dialog._tag_sp.text() == "ns=2;s=TIC101.SP"
        assert edit_dialog._tag_co.text() == ""

    # --- Shed & Safety ---

    def test_populated_shed(self, edit_dialog):
        assert edit_dialog._shed_opt.currentText() == "AUTO"
        assert edit_dialog._shed_time.value() == pytest.approx(30.0)
        assert edit_dialog._tuning_write_mode.currentText() == "approval_required"
        assert edit_dialog._max_tuning_pct.value() == pytest.approx(15.0)

    # --- Round trip ---

    def test_round_trip(self, edit_dialog):
        """get_controller_data() should return the same values we populated."""
        data = edit_dialog.get_controller_data()
        assert data["name"] == "TIC-101"
        assert data["description"] == "Temperature loop"
        assert data["execution_mode"] == "SUPERVISORY"
        assert data["scan_rate_ms"] == 500
        assert data["pid_structure"] == "PARALLEL"
        assert data["integral_type"] == "GAIN_KI"
        assert data["mode_normal"] == "MAN"
        assert data["pid_params"]["gain"] == pytest.approx(2.5)
        assert data["pid_params"]["reset"] == pytest.approx(5.0)
        assert data["pv_scale"]["eu_min"] == pytest.approx(-50.0)
        assert data["pv_scale"]["unit"] == "degC"
        assert data["ai_config"]["engine"] == "FUZZY"
        assert data["tag_bindings"]["node_id_pv"] == "ns=2;s=TIC101.PV"
        assert data["control_opts"]["direct_acting"] is True
        assert data["io_opts"]["increase_to_close"] is True
        assert data["shed_opt"] == "AUTO"
        assert data["tuning_write_mode"] == "approval_required"
        assert data["ff_enable"] is True
        assert data["arw_hi_lim"] == pytest.approx(110.0)

    # --- Validation in edit mode ---

    def test_accept_allowed_in_edit_mode_without_name_change(self, edit_dialog):
        """In edit mode, accept() should succeed even though name is read-only."""
        edit_dialog.accept()
        assert edit_dialog.result() == 1
