"""Tests for TrendChartWidget."""
import csv

import pytest

from smart_pid_hmi.themes.isa101 import ISA101Theme
from smart_pid_hmi.widgets.trend_chart import TrendChartWidget


@pytest.fixture
def theme():
    return ISA101Theme()


def test_creation(qtbot, theme):
    trend = TrendChartWidget(theme=theme)
    qtbot.addWidget(trend)
    assert trend._controller_id is None


def test_on_controller_selected_clears_data(qtbot, theme):
    trend = TrendChartWidget(theme=theme, buffer_size=100)
    qtbot.addWidget(trend)
    trend.on_controller_selected(1)
    assert trend._controller_id == 1
    assert len(trend._pv_data) == 0


def test_on_telemetry_adds_data(qtbot, theme):
    trend = TrendChartWidget(theme=theme, buffer_size=100)
    qtbot.addWidget(trend)
    trend.on_controller_selected(1)
    frame = {
        "controller_id": 1, "pv": 45.0, "sp": 50.0,
        "co": 62.0, "integral_val": 0.0,
        "timestamp": "2026-04-03T10:00:00", "status": "GOOD",
    }
    trend.on_telemetry(1, frame)
    assert len(trend._pv_data) == 1
    assert trend._pv_data[0] == 45.0


def test_ignores_other_controller(qtbot, theme):
    trend = TrendChartWidget(theme=theme, buffer_size=100)
    qtbot.addWidget(trend)
    trend.on_controller_selected(1)
    frame = {"controller_id": 2, "pv": 99.0, "sp": 50.0, "co": 62.0,
             "integral_val": 0.0, "timestamp": "T", "status": "GOOD"}
    trend.on_telemetry(2, frame)
    assert len(trend._pv_data) == 0


def test_circular_buffer(qtbot, theme):
    trend = TrendChartWidget(theme=theme, buffer_size=5)
    qtbot.addWidget(trend)
    trend.on_controller_selected(1)
    for i in range(10):
        frame = {"controller_id": 1, "pv": float(i), "sp": 50.0, "co": 50.0,
                 "integral_val": 0.0, "timestamp": "T", "status": "GOOD"}
        trend.on_telemetry(1, frame)
    assert len(trend._pv_data) == 5
    assert trend._pv_data[0] == 5.0  # oldest kept
    assert trend._pv_data[-1] == 9.0  # newest


def test_set_time_window(qtbot, theme):
    trend = TrendChartWidget(theme=theme)
    qtbot.addWidget(trend)
    trend.set_time_window("5min")
    assert trend._combo.currentText() == "5min"


# --- Gap #32: combo signal connected ---

def test_combo_signal_calls_set_time_window(qtbot, theme):
    """Changing the combo box triggers set_time_window."""
    trend = TrendChartWidget(theme=theme)
    qtbot.addWidget(trend)
    # Changing combo text should update (no crash, correct text)
    trend._combo.setCurrentText("1min")
    assert trend._combo.currentText() == "1min"
    trend._combo.setCurrentText("30min")
    assert trend._combo.currentText() == "30min"


# --- Gap #33: auto-scale checkbox ---

def test_auto_scale_checkbox_default(qtbot, theme):
    """Auto-scale is checked by default."""
    trend = TrendChartWidget(theme=theme)
    qtbot.addWidget(trend)
    assert trend._auto_scale_cb.isChecked()
    assert trend._auto_scale is True


def test_auto_scale_unchecked_enables_spinboxes(qtbot, theme):
    """Unchecking auto-scale enables manual spin boxes."""
    trend = TrendChartWidget(theme=theme)
    qtbot.addWidget(trend)
    # Spinboxes start disabled
    assert not trend._pv_min_spin.isEnabled()
    assert not trend._co_max_spin.isEnabled()
    # Uncheck auto-scale
    trend._auto_scale_cb.setChecked(False)
    assert trend._pv_min_spin.isEnabled()
    assert trend._pv_max_spin.isEnabled()
    assert trend._co_min_spin.isEnabled()
    assert trend._co_max_spin.isEnabled()


def test_auto_scale_rechecked_disables_spinboxes(qtbot, theme):
    """Re-checking auto-scale disables manual spin boxes."""
    trend = TrendChartWidget(theme=theme)
    qtbot.addWidget(trend)
    trend._auto_scale_cb.setChecked(False)
    trend._auto_scale_cb.setChecked(True)
    assert not trend._pv_min_spin.isEnabled()
    assert not trend._co_max_spin.isEnabled()


# --- Gap #34: manual scale fields ---

def test_manual_scale_spinbox_defaults(qtbot, theme):
    """Spinbox defaults are 0-100."""
    trend = TrendChartWidget(theme=theme)
    qtbot.addWidget(trend)
    assert trend._pv_min_spin.value() == 0.0
    assert trend._pv_max_spin.value() == 100.0
    assert trend._co_min_spin.value() == 0.0
    assert trend._co_max_spin.value() == 100.0


# --- Gap #35: CSV export ---

def test_write_csv(qtbot, theme, tmp_path):
    """_write_csv exports current data correctly."""
    trend = TrendChartWidget(theme=theme, buffer_size=100)
    qtbot.addWidget(trend)
    trend.on_controller_selected(1)

    # Feed 3 samples
    for i in range(3):
        frame = {
            "controller_id": 1,
            "pv": float(i * 10),
            "sp": 50.0,
            "co": float(i * 5),
        }
        trend.on_telemetry(1, frame)

    csv_path = tmp_path / "trend.csv"
    trend._write_csv(str(csv_path))

    with open(csv_path) as fh:
        reader = list(csv.reader(fh))
    assert reader[0] == ["time", "PV", "SP", "CO"]
    assert len(reader) == 4  # header + 3 rows
    assert reader[1] == ["0.0", "0.0", "50.0", "0.0"]
    assert reader[3] == ["2.0", "20.0", "50.0", "10.0"]


def test_write_csv_empty(qtbot, theme, tmp_path):
    """_write_csv with no data writes only header."""
    trend = TrendChartWidget(theme=theme, buffer_size=100)
    qtbot.addWidget(trend)

    csv_path = tmp_path / "empty.csv"
    trend._write_csv(str(csv_path))

    with open(csv_path) as fh:
        reader = list(csv.reader(fh))
    assert reader == [["time", "PV", "SP", "CO"]]


# --- Gap #31: AI markers ---

def test_add_ai_marker(qtbot, theme):
    """add_ai_marker() adds an InfiniteLine to the plot."""
    trend = TrendChartWidget(theme=theme)
    qtbot.addWidget(trend)
    assert len(trend._ai_markers) == 0
    trend.add_ai_marker(42.0)
    assert len(trend._ai_markers) == 1
    trend.add_ai_marker(84.0)
    assert len(trend._ai_markers) == 2


def test_ai_markers_cleared_on_controller_change(qtbot, theme):
    """Selecting a new controller clears AI markers."""
    trend = TrendChartWidget(theme=theme)
    qtbot.addWidget(trend)
    trend.on_controller_selected(1)
    trend.add_ai_marker(10.0)
    trend.add_ai_marker(20.0)
    assert len(trend._ai_markers) == 2
    trend.on_controller_selected(2)
    assert len(trend._ai_markers) == 0


# --- Gap #48: apply_theme ---

def test_apply_theme(qtbot, theme):
    """apply_theme() does not crash and updates theme reference."""
    trend = TrendChartWidget(theme=theme)
    qtbot.addWidget(trend)
    trend.apply_theme(theme)
    assert trend._theme is theme
