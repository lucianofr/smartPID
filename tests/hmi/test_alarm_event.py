"""Tests for AlarmEvent domain model."""
from datetime import datetime, timezone

from smart_pid_domain.enums import AlarmPriority, AlarmType
from smart_pid_domain.models.alarm import AlarmEvent


def test_alarm_event_creation():
    now = datetime.now(tz=timezone.utc)
    event = AlarmEvent(
        controller_id=1,
        controller_name="FIC-101",
        alarm_type=AlarmType.HIHI,
        priority=AlarmPriority.CRITICAL,
        value=95.3,
        limit=90.0,
        timestamp=now,
    )
    assert event.controller_id == 1
    assert event.controller_name == "FIC-101"
    assert event.alarm_type == AlarmType.HIHI
    assert event.priority == AlarmPriority.CRITICAL
    assert event.value == 95.3
    assert event.limit == 90.0
    assert event.timestamp == now


def test_alarm_event_is_frozen():
    now = datetime.now(tz=timezone.utc)
    event = AlarmEvent(
        controller_id=1,
        controller_name="FIC-101",
        alarm_type=AlarmType.HI,
        priority=AlarmPriority.WARNING,
        value=85.0,
        limit=80.0,
        timestamp=now,
    )
    try:
        event.value = 99.0  # type: ignore[misc]
        raise AssertionError("Should be frozen")
    except AttributeError:
        pass
