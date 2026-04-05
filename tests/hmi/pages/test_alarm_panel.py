"""Tests for AlarmPanel page."""
from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import QApplication

from smart_pid_hmi.pages.alarm_panel import _AI_LOG_MAX_LINES, AlarmPanel
from smart_pid_hmi.themes.isa101 import ISA101Theme

app = QApplication.instance() or QApplication([])


def _make_alarm(
    controller_id: int = 1,
    alarm_type: str = "HI_HI",
    priority: str = "CRITICAL",
    value: float = 95.0,
    limit: float = 90.0,
    transition: str = "TRIGGERED",
    timestamp: str = "2026-04-03T12:00:00",
    alarm_id: int | None = None,
) -> dict:
    d: dict = {
        "controller_id": controller_id,
        "alarm_type": alarm_type,
        "priority": priority,
        "value": value,
        "limit": limit,
        "transition": transition,
        "timestamp": timestamp,
    }
    if alarm_id is not None:
        d["alarm_id"] = alarm_id
    return d


def test_alarm_panel_creation():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme)
    assert panel is not None


def test_alarm_panel_add_active_alarm():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme)
    panel.on_alarm(1, _make_alarm(alarm_type="HIHI"))
    assert panel.active_table.rowCount() == 1


def test_alarm_panel_clear_removes_from_active():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme)
    panel.on_alarm(1, _make_alarm(alarm_type="HIHI"))
    panel.on_alarm(1, _make_alarm(
        alarm_type="HIHI", value=85.0, transition="CLEARED",
        timestamp="2026-04-03T12:01:00",
    ))
    # Cleared but not ACK'd — still in active table with CLEARED_UNACK status
    assert panel.active_table.rowCount() == 1


# --- Gap #42: Filter tests ---


def test_filter_by_priority():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme)
    # Widen date range to cover test timestamps
    panel._dt_from.setDateTime(QDateTime(2026, 1, 1, 0, 0, 0))
    panel._dt_to.setDateTime(QDateTime(2026, 12, 31, 23, 59, 0))

    panel.on_alarm(1, _make_alarm(priority="CRITICAL"))
    panel.on_alarm(2, _make_alarm(
        controller_id=2, alarm_type="LO", priority="LOW",
        timestamp="2026-04-03T12:05:00",
    ))

    # Filter to CRITICAL only
    panel._priority_filter.setCurrentText("CRITICAL")
    filtered = panel.get_filtered_alarms()
    assert len(filtered) == 1
    assert filtered[0]["priority"] == "CRITICAL"


def test_filter_by_type():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme)
    panel._dt_from.setDateTime(QDateTime(2026, 1, 1, 0, 0, 0))
    panel._dt_to.setDateTime(QDateTime(2026, 12, 31, 23, 59, 0))

    panel.on_alarm(1, _make_alarm(alarm_type="HI_HI"))
    panel.on_alarm(2, _make_alarm(
        controller_id=2, alarm_type="LO", priority="LOW",
        timestamp="2026-04-03T12:05:00",
    ))

    panel._type_filter.setCurrentText("LO")
    filtered = panel.get_filtered_alarms()
    assert len(filtered) == 1
    assert filtered[0]["alarm_type"] == "LO"


def test_filter_by_date_range():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme)
    panel._dt_from.setDateTime(QDateTime(2026, 1, 1, 0, 0, 0))
    panel._dt_to.setDateTime(QDateTime(2026, 12, 31, 23, 59, 0))

    panel.on_alarm(1, _make_alarm(timestamp="2026-04-03T12:00:00"))
    panel.on_alarm(2, _make_alarm(
        controller_id=2, alarm_type="LO", priority="LOW",
        timestamp="2026-06-15T08:00:00",
    ))

    # Narrow range to April only
    panel._dt_from.setDateTime(QDateTime(2026, 4, 1, 0, 0, 0))
    panel._dt_to.setDateTime(QDateTime(2026, 4, 30, 23, 59, 0))
    filtered = panel.get_filtered_alarms()
    assert len(filtered) == 1
    assert filtered[0]["controller_id"] == 1


def test_filter_all_returns_everything():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme)
    panel._dt_from.setDateTime(QDateTime(2026, 1, 1, 0, 0, 0))
    panel._dt_to.setDateTime(QDateTime(2026, 12, 31, 23, 59, 0))

    panel.on_alarm(1, _make_alarm())
    panel.on_alarm(2, _make_alarm(
        controller_id=2, alarm_type="LO", priority="LOW",
        timestamp="2026-04-03T13:00:00",
    ))

    panel._priority_filter.setCurrentText("All")
    panel._type_filter.setCurrentText("All")
    filtered = panel.get_filtered_alarms()
    assert len(filtered) == 2


def test_apply_filters_rebuilds_table():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme)
    panel._dt_from.setDateTime(QDateTime(2026, 1, 1, 0, 0, 0))
    panel._dt_to.setDateTime(QDateTime(2026, 12, 31, 23, 59, 0))

    panel.on_alarm(1, _make_alarm(priority="CRITICAL"))
    panel.on_alarm(2, _make_alarm(
        controller_id=2, alarm_type="LO", priority="LOW",
        timestamp="2026-04-03T13:00:00",
    ))
    assert panel.active_table.rowCount() == 2

    panel._priority_filter.setCurrentText("LOW")
    panel._apply_filters()
    assert panel.active_table.rowCount() == 1


# --- Gap #43: AI Log Box tests ---


def test_ai_log_append():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme)
    panel.append_ai_log("Ki adjusted +5% via fuzzy")
    assert "Ki adjusted" in panel.ai_log_widget.toPlainText()


def test_ai_log_max_lines():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme)
    for i in range(_AI_LOG_MAX_LINES + 50):
        panel.append_ai_log(f"line {i}")
    # QPlainTextEdit.maximumBlockCount limits to _AI_LOG_MAX_LINES
    assert panel.ai_log_widget.blockCount() <= _AI_LOG_MAX_LINES


def test_ai_log_readonly():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme)
    assert panel.ai_log_widget.isReadOnly()


def test_ai_log_dark_style():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme)
    style = panel.ai_log_widget.styleSheet()
    # AI log uses theme-aware colors (bg_card + accent)
    assert theme.bg_card.lower() in style.lower()


# --- Gap #45: Load History tests ---


def test_load_history_calls_api():
    theme = ISA101Theme()
    mock_api = MagicMock()
    mock_api.get_alarm_history.return_value = [
        {
            "controller_id": 1,
            "alarm_type": "HI",
            "priority": "HIGH",
            "value": 88.0,
            "limit": 85.0,
            "timestamp": "2026-04-02T10:00:00",
            "status": "ACKNOWLEDGED",
        },
    ]
    panel = AlarmPanel(theme=theme, api_client=mock_api)
    panel._dt_from.setDateTime(QDateTime(2026, 4, 1, 0, 0, 0))
    panel._dt_to.setDateTime(QDateTime(2026, 4, 30, 23, 59, 0))

    panel._load_history()
    mock_api.get_alarm_history.assert_called_once()
    assert panel.active_table.rowCount() == 1


def test_load_history_no_api_client():
    """Load History does nothing when no API client is provided."""
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme, api_client=None)
    panel._load_history()  # should not raise
    assert panel.active_table.rowCount() == 0


def test_load_history_api_error_handled():
    """API errors are silently caught, table stays empty."""
    theme = ISA101Theme()
    mock_api = MagicMock()
    mock_api.get_alarm_history.side_effect = RuntimeError("connection lost")
    panel = AlarmPanel(theme=theme, api_client=mock_api)
    panel._load_history()  # should not raise
    assert panel.active_table.rowCount() == 0
