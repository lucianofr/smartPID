"""Alarm configuration and transition models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from smart_pid_domain.enums import AlarmPriority, AlarmType

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class AlarmConfig:
    """Alarm limits and priorities for a controller."""

    hihi_enabled: bool
    hihi_value: float
    hihi_priority: AlarmPriority
    hi_enabled: bool
    hi_value: float
    hi_priority: AlarmPriority
    lo_enabled: bool
    lo_value: float
    lo_priority: AlarmPriority
    lolo_enabled: bool
    lolo_value: float
    lolo_priority: AlarmPriority
    dv_hi_enabled: bool
    dv_hi_value: float
    dv_hi_priority: AlarmPriority
    dv_lo_enabled: bool
    dv_lo_value: float
    dv_lo_priority: AlarmPriority
    deadband_percent: float  # 0.0-50.0, % of alarm limit


@dataclass(frozen=True)
class AlarmTransition:
    """Represents a single alarm state change (trigger or clear)."""

    controller_id: int
    alarm_type: AlarmType
    priority: AlarmPriority
    transition: Literal["TRIGGERED", "CLEARED"]
    value: float
    limit: float
    timestamp: datetime
