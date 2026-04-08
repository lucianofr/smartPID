"""Tests for AlarmPanel page."""
from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import QApplication

from smart_pid_hmi.pages.alarm_panel import (
    CATEGORY_AI,
    CATEGORY_ALARM,
    CATEGORY_SYSTEM,
    AlarmPanel,
)
from smart_pid_hmi.themes.isa101 import ISA101Theme

app = QApplication.instance() or QApplication([])


def _make_alarm(
    controller_id: int = 1,
    alarm_type: str = "HI",
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
        d["id"] = alarm_id
    return d


def test_alarm_panel_creation():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme, api_client=MagicMock())
    assert panel is not None


def test_alarm_panel_add_active_alarm():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme, api_client=MagicMock())
    panel.on_alarm(1, _make_alarm(alarm_type="HIHI"))
    assert panel.active_table.rowCount() == 1


def test_alarm_panel_clear_removes_from_active():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme, api_client=MagicMock())
    panel.on_alarm(1, _make_alarm(alarm_type="HIHI"))
    panel.on_alarm(1, _make_alarm(
        alarm_type="HIHI", value=85.0, transition="CLEARED",
        timestamp="2026-04-03T12:01:00",
    ))
    # Cleared but not ACK'd — still in active table with CLEARED_UNACK status
    assert panel.active_table.rowCount() == 1


# --- Category column ---


def test_alarm_has_category_column():
    """Table should include a Category column."""
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme, api_client=MagicMock())
    panel.on_alarm(1, _make_alarm(alarm_type="HI"))
    # Category is column 1
    item = panel.active_table.item(0, 1)
    assert item is not None
    assert item.text() == CATEGORY_ALARM


def test_ai_event_has_category():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme, api_client=MagicMock())
    panel.on_ai_event(1, "Ki adjusted +5%")
    item = panel.active_table.item(0, 1)
    assert item is not None
    assert item.text() == CATEGORY_AI


# --- Multi-select filter tests ---


def _set_checked(combo, items_to_check):
    """Helper to check only specific items in a CheckableComboBox."""
    from PySide6.QtCore import Qt
    model = combo._model
    for row in range(model.rowCount()):
        item = model.item(row)
        if item.text() in items_to_check:
            item.setCheckState(Qt.CheckState.Checked)
        else:
            item.setCheckState(Qt.CheckState.Unchecked)


def test_filter_by_priority_multi_select():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme, api_client=MagicMock())
    panel._dt_from.setDateTime(QDateTime(2026, 1, 1, 0, 0, 0))
    panel._dt_to.setDateTime(QDateTime(2026, 12, 31, 23, 59, 0))

    panel.on_alarm(1, _make_alarm(priority="CRITICAL"))
    panel.on_alarm(2, _make_alarm(
        controller_id=2, alarm_type="LO", priority="WARNING",
        timestamp="2026-04-03T12:05:00",
    ))

    _set_checked(panel._priority_filter, ["CRITICAL"])
    filtered = panel.get_filtered_alarms()
    assert len(filtered) == 1
    assert filtered[0]["priority"] == "CRITICAL"


def test_filter_by_type_multi_select():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme, api_client=MagicMock())
    panel._dt_from.setDateTime(QDateTime(2026, 1, 1, 0, 0, 0))
    panel._dt_to.setDateTime(QDateTime(2026, 12, 31, 23, 59, 0))

    panel.on_alarm(1, _make_alarm(alarm_type="HIHI"))
    panel.on_alarm(2, _make_alarm(
        controller_id=2, alarm_type="LO", priority="WARNING",
        timestamp="2026-04-03T12:05:00",
    ))

    _set_checked(panel._level_filter, ["LO"])
    filtered = panel.get_filtered_alarms()
    assert len(filtered) == 1
    assert filtered[0]["alarm_type"] == "LO"


def test_filter_by_category():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme, api_client=MagicMock())
    panel._dt_from.setDateTime(QDateTime(2026, 1, 1, 0, 0, 0))
    panel._dt_to.setDateTime(QDateTime(2026, 12, 31, 23, 59, 0))

    panel.on_alarm(1, _make_alarm(alarm_type="HI"))
    panel.on_ai_event(1, "Ki adjusted")

    # Filter to AI Log only
    _set_checked(panel._category_filter, [CATEGORY_AI])
    filtered = panel.get_filtered_alarms()
    assert len(filtered) == 1
    assert filtered[0]["_category"] == CATEGORY_AI


def test_ai_log_bypasses_priority_level_filters():
    """AI Log events should appear even when priority/level filters are restrictive."""
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme, api_client=MagicMock())
    panel._dt_from.setDateTime(QDateTime(2026, 1, 1, 0, 0, 0))
    panel._dt_to.setDateTime(QDateTime(2026, 12, 31, 23, 59, 0))

    panel.on_ai_event(1, "Ki adjusted")
    # Set priority filter to CRITICAL only — AI logs should still appear
    _set_checked(panel._priority_filter, ["CRITICAL"])
    _set_checked(panel._level_filter, ["HI"])
    filtered = panel.get_filtered_alarms()
    assert len(filtered) == 1


def test_filter_by_date_range():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme, api_client=MagicMock())
    panel._dt_from.setDateTime(QDateTime(2026, 1, 1, 0, 0, 0))
    panel._dt_to.setDateTime(QDateTime(2026, 12, 31, 23, 59, 0))

    panel.on_alarm(1, _make_alarm(timestamp="2026-04-03T12:00:00"))
    panel.on_alarm(2, _make_alarm(
        controller_id=2, alarm_type="LO", priority="WARNING",
        timestamp="2026-06-15T08:00:00",
    ))

    panel._dt_from.setDateTime(QDateTime(2026, 4, 1, 0, 0, 0))
    panel._dt_to.setDateTime(QDateTime(2026, 4, 30, 23, 59, 0))
    filtered = panel.get_filtered_alarms()
    assert len(filtered) == 1
    assert filtered[0]["controller_id"] == 1


def test_filter_all_checked_returns_everything():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme, api_client=MagicMock())
    panel._dt_from.setDateTime(QDateTime(2026, 1, 1, 0, 0, 0))
    panel._dt_to.setDateTime(QDateTime(2026, 12, 31, 23, 59, 0))

    panel.on_alarm(1, _make_alarm())
    panel.on_alarm(2, _make_alarm(
        controller_id=2, alarm_type="LO", priority="WARNING",
        timestamp="2026-04-03T13:00:00",
    ))

    # All checked by default
    filtered = panel.get_filtered_alarms()
    assert len(filtered) == 2


def test_apply_filters_rebuilds_table():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme, api_client=MagicMock())
    panel._dt_from.setDateTime(QDateTime(2026, 1, 1, 0, 0, 0))
    panel._dt_to.setDateTime(QDateTime(2026, 12, 31, 23, 59, 0))

    panel.on_alarm(1, _make_alarm(priority="CRITICAL"))
    panel.on_alarm(2, _make_alarm(
        controller_id=2, alarm_type="LO", priority="WARNING",
        timestamp="2026-04-03T13:00:00",
    ))
    assert panel.active_table.rowCount() == 2

    _set_checked(panel._priority_filter, ["WARNING"])
    panel._apply_filters()
    assert panel.active_table.rowCount() == 1


# --- AI event tests ---


def test_ai_event_appears_in_table():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme, api_client=MagicMock())
    panel.on_ai_event(1, "Ki adjusted +5% via fuzzy")
    assert panel.active_table.rowCount() == 1
    # Category column (col 1) should be AI Log
    assert panel.active_table.item(0, 1).text() == CATEGORY_AI
    # Type column (col 2) should be "—" (not applicable for AI logs)
    assert panel.active_table.item(0, 2).text() == "\u2014"
    # Priority column (col 3) should be "—" (not applicable for AI logs)
    assert panel.active_table.item(0, 3).text() == "\u2014"


def test_ai_events_max_limit():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme, api_client=MagicMock())
    for i in range(550):
        panel.on_ai_event(1, f"action {i}")
    # Internal list trimmed to 500
    assert len(panel._ai_events) == 500


def test_system_event_appears_in_table():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme, api_client=MagicMock())
    panel.on_system_event("User admin logged in")
    assert panel.active_table.rowCount() == 1
    assert panel.active_table.item(0, 1).text() == CATEGORY_SYSTEM


# --- Load History tests ---


def test_load_history_calls_api():
    theme = ISA101Theme()
    mock_api = MagicMock()
    mock_api.get_alarm_history.return_value = [
        {
            "controller_id": 1,
            "alarm_type": "HI",
            "priority": "WARNING",
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


# --- Bug #3 / #4 fixes ---


def test_alarm_panel_requires_api_client():
    """AlarmPanel must raise TypeError if api_client is not provided."""
    import inspect

    sig = inspect.signature(AlarmPanel.__init__)
    param = sig.parameters.get("api_client")
    assert param is not None
    assert param.default is inspect.Parameter.empty, \
        "api_client must be a required parameter (no None default)"


def test_alarm_panel_ack_uses_id_field():
    """ACK should use 'id' field from alarm data, not 'alarm_id' (Bug #4)."""
    from PySide6.QtCore import Qt

    theme = ISA101Theme()
    mock_api = MagicMock()
    panel = AlarmPanel(theme=theme, api_client=mock_api)

    panel.on_alarm(1, {
        "alarm_type": "HI",
        "priority": "WARNING",
        "transition": "TRIGGERED",
        "value": 85.0,
        "limit": 80.0,
        "timestamp": "2026-04-07T12:00:00",
        "id": 42,
    })

    item = panel.active_table.item(0, 0)
    assert item is not None
    stored_id = item.data(Qt.ItemDataRole.UserRole)
    assert stored_id == 42


def test_alarm_panel_on_all_acked():
    """on_all_acked() should mark all alarms as ACKNOWLEDGED."""
    theme = ISA101Theme()
    mock_api = MagicMock()
    panel = AlarmPanel(theme=theme, api_client=mock_api)
    panel.on_alarm(1, {
        "alarm_type": "HI", "priority": "WARNING",
        "transition": "TRIGGERED", "value": 85.0, "limit": 80.0,
        "timestamp": "2026-04-07T12:00:00",
    })
    panel.on_all_acked()
    for _key, alarm in panel._active_alarms.items():
        assert alarm["status"] == "ACKNOWLEDGED"


def test_alarm_panel_on_alarm_acked():
    """on_alarm_acked() should mark specific alarm as ACKNOWLEDGED."""
    theme = ISA101Theme()
    mock_api = MagicMock()
    panel = AlarmPanel(theme=theme, api_client=mock_api)
    panel.on_alarm(1, {
        "alarm_type": "HI", "priority": "WARNING",
        "transition": "TRIGGERED", "value": 85.0, "limit": 80.0,
        "timestamp": "2026-04-07T12:00:00",
        "id": 42,
    })
    panel.on_alarm_acked(42)
    alarm = panel._active_alarms[(1, "HI")]
    assert alarm["status"] == "ACKNOWLEDGED"


# --- Live mode tests ---


def test_alarm_panel_has_live_checkbox():
    theme = ISA101Theme()
    mock_api = MagicMock()
    panel = AlarmPanel(theme=theme, api_client=mock_api)
    assert hasattr(panel, "_live_checkbox")


def test_alarm_panel_live_disables_history_controls():
    theme = ISA101Theme()
    mock_api = MagicMock()
    panel = AlarmPanel(theme=theme, api_client=mock_api)
    panel._live_checkbox.setChecked(True)
    assert not panel._dt_from.isEnabled()
    assert not panel._dt_to.isEnabled()
    assert not panel._load_history_btn.isEnabled()


def test_alarm_panel_live_enables_history_on_uncheck():
    theme = ISA101Theme()
    mock_api = MagicMock()
    panel = AlarmPanel(theme=theme, api_client=mock_api)
    panel._live_checkbox.setChecked(True)
    panel._live_checkbox.setChecked(False)
    assert panel._dt_from.isEnabled()
    assert panel._dt_to.isEnabled()
    assert panel._load_history_btn.isEnabled()
