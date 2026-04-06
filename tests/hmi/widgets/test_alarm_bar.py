"""Tests for AlarmBarWidget — footer alarm strip."""
import pytest

from smart_pid_hmi.themes.isa101 import ISA101Theme
from smart_pid_hmi.widgets.alarm_bar import AlarmBarWidget


@pytest.fixture
def theme():
    return ISA101Theme()


def test_creation(qtbot, theme):
    bar = AlarmBarWidget(theme=theme)
    qtbot.addWidget(bar)
    assert bar.alarm_count == 0


def test_add_alarm(qtbot, theme):
    bar = AlarmBarWidget(theme=theme)
    qtbot.addWidget(bar)
    alarm = {
        "controller_name": "FIC-101",
        "alarm_type": "HIHI",
        "priority": "CRITICAL",
        "value": 95.3,
        "timestamp": "2026-04-03T10:00:00",
    }
    bar.on_alarm(1, alarm)
    assert bar.alarm_count == 1


def test_max_alarms(qtbot, theme):
    bar = AlarmBarWidget(theme=theme)
    qtbot.addWidget(bar)
    for i in range(15):
        alarm = {
            "controller_name": f"TAG-{i}",
            "alarm_type": "HI",
            "priority": "WARNING",
            "value": float(i),
            "timestamp": f"2026-04-03T10:{i:02d}:00",
        }
        bar.on_alarm(i, alarm)
    assert bar.alarm_count == 5


def test_newest_alarm_is_first(qtbot, theme):
    bar = AlarmBarWidget(theme=theme)
    qtbot.addWidget(bar)
    for i in range(3):
        alarm = {
            "controller_name": f"TAG-{i}",
            "alarm_type": "HI",
            "priority": "WARNING",
            "value": float(i),
            "timestamp": f"2026-04-03T10:{i:02d}:00",
        }
        bar.on_alarm(i, alarm)
    # Newest (TAG-2) should be at index 0
    assert bar._alarms[0]["controller_name"] == "TAG-2"
