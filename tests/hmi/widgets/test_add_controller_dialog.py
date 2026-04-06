"""Tests for AddControllerDialog — full 30+ field coverage."""
import pytest

from smart_pid_hmi.widgets.add_controller_dialog import AddControllerDialog


@pytest.fixture
def dialog(qtbot):
    dlg = AddControllerDialog()
    qtbot.addWidget(dlg)
    return dlg


class TestDialogCreation:
    """Verify the dialog is created with all tabs and expected widgets."""

    def test_window_title(self, dialog):
        assert dialog.windowTitle() == "Add Controller"

    def test_has_seven_tabs(self, dialog):
        tabs = dialog.findChild(__import__("PySide6.QtWidgets", fromlist=["QTabWidget"]).QTabWidget)
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
            "engine", "objective", "process_speed",
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
        # Dialog should still be visible (accept was blocked)
        assert dialog.isVisible() or not dialog.result()

    def test_accept_allowed_with_name(self, dialog, qtbot):
        dialog._name.setText("TIC-101")
        dialog.accept()
        # result() == 1 means QDialog.Accepted
        assert dialog.result() == 1
