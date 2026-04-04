"""Tests for AlarmPanel page."""
from __future__ import annotations

from PySide6.QtWidgets import QApplication

from smart_pid_hmi.pages.alarm_panel import AlarmPanel
from smart_pid_hmi.themes.isa101 import ISA101Theme

app = QApplication.instance() or QApplication([])


def test_alarm_panel_creation():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme)
    assert panel is not None


def test_alarm_panel_add_active_alarm():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme)
    panel.on_alarm(1, {
        "controller_id": 1, "alarm_type": "HIHI", "priority": "CRITICAL",
        "value": 95.0, "limit": 90.0, "transition": "TRIGGERED",
        "timestamp": "2026-04-03T12:00:00",
    })
    assert panel.active_table.rowCount() == 1


def test_alarm_panel_clear_removes_from_active():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme)
    panel.on_alarm(1, {
        "controller_id": 1, "alarm_type": "HIHI", "priority": "CRITICAL",
        "value": 95.0, "limit": 90.0, "transition": "TRIGGERED",
        "timestamp": "2026-04-03T12:00:00",
    })
    panel.on_alarm(1, {
        "controller_id": 1, "alarm_type": "HIHI", "priority": "CRITICAL",
        "value": 85.0, "limit": 90.0, "transition": "CLEARED",
        "timestamp": "2026-04-03T12:01:00",
    })
    # Cleared but not ACK'd — still in active table with CLEARED_UNACK status
    assert panel.active_table.rowCount() == 1
