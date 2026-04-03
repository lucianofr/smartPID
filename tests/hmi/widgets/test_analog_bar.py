"""Tests for AnalogBarWidget."""
import pytest

from smart_pid_hmi.themes.isa101 import ISA101Theme
from smart_pid_hmi.widgets.analog_bar import AnalogBarWidget


@pytest.fixture
def theme():
    return ISA101Theme()


def test_creation(qtbot, theme):
    bar = AnalogBarWidget(label="PV", unit="°C", min_val=0.0, max_val=100.0, theme=theme)
    qtbot.addWidget(bar)
    assert bar.value == 0.0
    assert bar.label == "PV"


def test_set_value(qtbot, theme):
    bar = AnalogBarWidget(label="PV", unit="°C", min_val=0.0, max_val=100.0, theme=theme)
    qtbot.addWidget(bar)
    bar.set_value(45.3)
    assert bar.value == 45.3


def test_clamp_value(qtbot, theme):
    bar = AnalogBarWidget(label="PV", unit="°C", min_val=0.0, max_val=100.0, theme=theme)
    qtbot.addWidget(bar)
    bar.set_value(150.0)
    assert bar.value == 100.0
    bar.set_value(-10.0)
    assert bar.value == 0.0


def test_set_sp_marker(qtbot, theme):
    bar = AnalogBarWidget(label="PV", unit="°C", min_val=0.0, max_val=100.0, theme=theme)
    qtbot.addWidget(bar)
    bar.set_sp_marker(50.0)
    assert bar.sp_marker == 50.0


def test_alarm_state_changes_fill(qtbot, theme):
    bar = AnalogBarWidget(label="PV", unit="°C", min_val=0.0, max_val=100.0, theme=theme)
    qtbot.addWidget(bar)
    bar.set_alarm_state("CRITICAL")
    assert bar.alarm_state == "CRITICAL"
    bar.set_alarm_state(None)
    assert bar.alarm_state is None


def test_renders_without_crash(qtbot, theme):
    bar = AnalogBarWidget(label="CO", unit="%", min_val=0.0, max_val=100.0, theme=theme)
    qtbot.addWidget(bar)
    bar.set_value(62.5)
    bar.show()
    bar.repaint()
    # No crash = pass
