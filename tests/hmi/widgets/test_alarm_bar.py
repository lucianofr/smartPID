"""Tests for AlarmBar QTableWidget grid redesign."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QTableWidget

from smart_pid_hmi.themes.isa101 import ISA101Theme
from smart_pid_hmi.widgets.alarm_bar import AlarmBarWidget

app = QApplication.instance() or QApplication([])


@pytest.fixture
def theme():
    return ISA101Theme()


@pytest.fixture
def bar(theme):
    return AlarmBarWidget(theme=theme)


def test_alarm_bar_creation(bar):
    assert bar is not None
    assert bar.alarm_count == 0
    assert hasattr(bar, "ack_requested")
    assert hasattr(bar, "ack_all_requested")


def test_alarm_bar_has_table(bar):
    """AlarmBar must use QTableWidget (not pills)."""
    assert hasattr(bar, "_table")
    assert isinstance(bar._table, QTableWidget)


def test_alarm_bar_columns(bar):
    """Table must have 6 columns: Priority, Level, Loop, Description, DateTime, ACK."""
    assert bar._table.columnCount() == 6


def test_alarm_bar_triggered_adds_row(bar):
    bar.on_alarm({
        "controller_id": 1,
        "controller_name": "TIC-101",
        "controller_description": "Temp Reactor A",
        "alarm_type": "HIHI",
        "priority": "CRITICAL",
        "transition": "TRIGGERED",
        "value": 95.0,
        "limit": 90.0,
        "timestamp": "2026-04-07T12:00:00",
    })
    assert bar._table.rowCount() == 1
    assert bar.alarm_count == 1


def test_alarm_bar_cleared_removes_row(bar):
    bar.on_alarm({
        "controller_id": 1, "controller_name": "TIC-101",
        "controller_description": "Temp Reactor A", "alarm_type": "HIHI",
        "priority": "CRITICAL", "transition": "TRIGGERED",
        "value": 95.0, "limit": 90.0, "timestamp": "2026-04-07T12:00:00",
    })
    bar.on_alarm({
        "controller_id": 1, "controller_name": "TIC-101",
        "controller_description": "Temp Reactor A", "alarm_type": "HIHI",
        "priority": "CRITICAL", "transition": "CLEARED",
        "value": 85.0, "limit": 90.0, "timestamp": "2026-04-07T12:05:00",
    })
    assert bar._table.rowCount() == 0


def test_alarm_bar_log_priority_hidden(bar):
    """Priority LOG should NOT appear in AlarmBar grid."""
    bar.on_alarm({
        "controller_id": 1, "controller_name": "TIC-101",
        "controller_description": "", "alarm_type": "HI",
        "priority": "LOG", "transition": "TRIGGERED",
        "value": 81.0, "limit": 80.0, "timestamp": "2026-04-07T12:00:00",
    })
    assert bar._table.rowCount() == 0


def test_alarm_bar_on_alarm_acked(bar):
    """on_alarm_acked should mark specific alarm as acked."""
    bar.on_alarm({
        "controller_id": 1, "controller_name": "TIC-101",
        "controller_description": "", "alarm_type": "HI",
        "priority": "WARNING", "transition": "TRIGGERED",
        "value": 85.0, "limit": 80.0, "timestamp": "2026-04-07T12:00:00",
    })
    bar.on_alarm_acked(1, "HI")
    assert bar._table.rowCount() == 1
    key = (1, "HI")
    assert bar._active[key]["acked"] is True


def test_alarm_bar_on_all_alarms_acked(bar):
    """on_all_alarms_acked should mark all as acked."""
    bar.on_alarm({
        "controller_id": 1, "controller_name": "TIC-101",
        "controller_description": "", "alarm_type": "HI",
        "priority": "WARNING", "transition": "TRIGGERED",
        "value": 85.0, "limit": 80.0, "timestamp": "2026-04-07T12:00:00",
    })
    bar.on_alarm({
        "controller_id": 2, "controller_name": "FIC-203",
        "controller_description": "", "alarm_type": "HIHI",
        "priority": "CRITICAL", "transition": "TRIGGERED",
        "value": 96.0, "limit": 95.0, "timestamp": "2026-04-07T12:01:00",
    })
    bar.on_all_alarms_acked()
    for info in bar._active.values():
        assert info["acked"] is True


def test_alarm_bar_counters(bar):
    """Counter label must show CRITICAL: N | WARNING: N for unacked alarms."""
    bar.on_alarm({
        "controller_id": 1, "controller_name": "TIC-101",
        "controller_description": "", "alarm_type": "HIHI",
        "priority": "CRITICAL", "transition": "TRIGGERED",
        "value": 95.0, "limit": 90.0, "timestamp": "2026-04-07T12:00:00",
    })
    bar.on_alarm({
        "controller_id": 2, "controller_name": "FIC-203",
        "controller_description": "", "alarm_type": "HI",
        "priority": "WARNING", "transition": "TRIGGERED",
        "value": 82.0, "limit": 80.0, "timestamp": "2026-04-07T12:01:00",
    })
    text = bar._counter_label.text()
    assert "CRITICAL: 1" in text
    assert "WARNING: 1" in text


def test_alarm_bar_sorted_by_priority_then_time(bar):
    """CRITICAL alarms should appear before WARNING."""
    bar.on_alarm({
        "controller_id": 1, "controller_name": "TIC-101",
        "controller_description": "", "alarm_type": "HI",
        "priority": "WARNING", "transition": "TRIGGERED",
        "value": 82.0, "limit": 80.0, "timestamp": "2026-04-07T12:00:00",
    })
    bar.on_alarm({
        "controller_id": 2, "controller_name": "FIC-203",
        "controller_description": "", "alarm_type": "HIHI",
        "priority": "CRITICAL", "transition": "TRIGGERED",
        "value": 96.0, "limit": 95.0, "timestamp": "2026-04-07T12:01:00",
    })
    assert bar._table.item(0, 0).text() == "CRITICAL"
