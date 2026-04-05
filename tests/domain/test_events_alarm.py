"""Tests for alarm domain events."""
from __future__ import annotations

from datetime import UTC, datetime

from smart_pid_domain.enums import AlarmPriority, AlarmType
from smart_pid_domain.events import AlarmAcknowledged, AlarmCleared, AlarmTriggered


def test_alarm_triggered_creation():
    e = AlarmTriggered(
        controller_id=1,
        alarm_type=AlarmType.HIHI,
        priority=AlarmPriority.CRITICAL,
        value=95.0,
        limit=90.0,
        timestamp=datetime.now(tz=UTC),
    )
    assert e.controller_id == 1
    assert e.alarm_type == AlarmType.HIHI
    assert e.event_id is not None


def test_alarm_cleared_creation():
    e = AlarmCleared(
        controller_id=1,
        alarm_type=AlarmType.HIHI,
        value=85.0,
        timestamp=datetime.now(tz=UTC),
    )
    assert e.controller_id == 1
    assert e.event_id is not None


def test_alarm_acknowledged_creation():
    e = AlarmAcknowledged(
        controller_id=1,
        alarm_type=AlarmType.HIHI,
        user_id=2,
        username="operator1",
        timestamp=datetime.now(tz=UTC),
    )
    assert e.username == "operator1"
    assert e.event_id is not None


def test_alarm_events_are_frozen():
    e = AlarmTriggered(
        controller_id=1, alarm_type=AlarmType.HI,
        priority=AlarmPriority.WARNING, value=85.0,
        limit=80.0, timestamp=datetime.now(tz=UTC),
    )
    try:
        e.value = 99.0  # type: ignore[misc]
        raise AssertionError("Should be frozen")
    except AttributeError:
        pass
