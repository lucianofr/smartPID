"""Tests for TrendChartWidget."""
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
    # No crash = pass
