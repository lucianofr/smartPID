"""Tests for AlarmState, AuditAction enums and AlarmConfig model."""
from __future__ import annotations

from datetime import UTC, datetime

from smart_pid_domain.enums import AlarmPriority, AlarmState, AlarmType, AuditAction
from smart_pid_domain.models.alarm_config import AlarmConfig, AlarmTransition


def test_alarm_state_values():
    assert AlarmState.UNACKNOWLEDGED == "UNACKNOWLEDGED"
    assert AlarmState.ACKNOWLEDGED == "ACKNOWLEDGED"
    assert AlarmState.CLEARED_UNACK == "CLEARED_UNACK"


def test_audit_action_values():
    assert AuditAction.LOGIN == "LOGIN"
    assert AuditAction.SP_CHANGE == "SP_CHANGE"
    assert AuditAction.ACK_ALARM == "ACK_ALARM"
    assert AuditAction.TUNE_PID == "TUNE_PID"


def test_alarm_config_creation():
    config = AlarmConfig(
        hihi_enabled=True, hihi_value=90.0, hihi_priority=AlarmPriority.CRITICAL,
        hi_enabled=True, hi_value=80.0, hi_priority=AlarmPriority.WARNING,
        lo_enabled=True, lo_value=20.0, lo_priority=AlarmPriority.WARNING,
        lolo_enabled=True, lolo_value=10.0, lolo_priority=AlarmPriority.CRITICAL,
        dv_hi_enabled=True, dv_hi_value=15.0, dv_hi_priority=AlarmPriority.ADVISORY,
        dv_lo_enabled=True, dv_lo_value=15.0, dv_lo_priority=AlarmPriority.ADVISORY,
        deadband_percent=2.0,
    )
    assert config.hihi_enabled is True
    assert config.deadband_percent == 2.0


def test_alarm_config_is_frozen():
    config = AlarmConfig(
        hihi_enabled=False, hihi_value=0, hihi_priority=AlarmPriority.LOG,
        hi_enabled=False, hi_value=0, hi_priority=AlarmPriority.LOG,
        lo_enabled=False, lo_value=0, lo_priority=AlarmPriority.LOG,
        lolo_enabled=False, lolo_value=0, lolo_priority=AlarmPriority.LOG,
        dv_hi_enabled=False, dv_hi_value=0, dv_hi_priority=AlarmPriority.LOG,
        dv_lo_enabled=False, dv_lo_value=0, dv_lo_priority=AlarmPriority.LOG,
        deadband_percent=0,
    )
    try:
        config.hihi_enabled = True  # type: ignore[misc]
        raise AssertionError("Should be frozen")
    except AttributeError:
        pass


def test_alarm_transition_creation():
    t = AlarmTransition(
        controller_id=1,
        alarm_type=AlarmType.HIHI,
        priority=AlarmPriority.CRITICAL,
        transition="TRIGGERED",
        value=95.0,
        limit=90.0,
        timestamp=datetime.now(tz=UTC),
    )
    assert t.transition == "TRIGGERED"
    assert t.controller_id == 1
