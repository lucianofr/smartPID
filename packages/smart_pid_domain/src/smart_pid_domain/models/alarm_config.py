"""Alarm configuration and transition models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from smart_pid_domain.enums import AlarmPriority, AlarmType

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class AlarmConfig:
    """Alarm limits, priorities and delays for a controller.

    Each alarm type has:
    - enabled: whether the alarm is active
    - value: the limit threshold
    - priority: CRITICAL / WARNING / ADVISORY / LOG
    - delay_on_s: time (s) PV must remain in alarm condition before triggering
    - delay_off_s: time (s) PV must remain normal before clearing
    """

    # -- HIHI --
    hihi_enabled: bool = False
    hihi_value: float = 0.0
    hihi_priority: AlarmPriority = AlarmPriority.CRITICAL
    hihi_delay_on_s: float = 0.0
    hihi_delay_off_s: float = 0.0
    # -- HI --
    hi_enabled: bool = False
    hi_value: float = 0.0
    hi_priority: AlarmPriority = AlarmPriority.WARNING
    hi_delay_on_s: float = 0.0
    hi_delay_off_s: float = 0.0
    # -- LO --
    lo_enabled: bool = False
    lo_value: float = 0.0
    lo_priority: AlarmPriority = AlarmPriority.WARNING
    lo_delay_on_s: float = 0.0
    lo_delay_off_s: float = 0.0
    # -- LOLO --
    lolo_enabled: bool = False
    lolo_value: float = 0.0
    lolo_priority: AlarmPriority = AlarmPriority.CRITICAL
    lolo_delay_on_s: float = 0.0
    lolo_delay_off_s: float = 0.0
    # -- Deviation High --
    dv_hi_enabled: bool = False
    dv_hi_value: float = 0.0
    dv_hi_priority: AlarmPriority = AlarmPriority.WARNING
    dv_hi_delay_on_s: float = 0.0
    dv_hi_delay_off_s: float = 0.0
    # -- Deviation Low --
    dv_lo_enabled: bool = False
    dv_lo_value: float = 0.0
    dv_lo_priority: AlarmPriority = AlarmPriority.WARNING
    dv_lo_delay_on_s: float = 0.0
    dv_lo_delay_off_s: float = 0.0
    # -- Shared --
    deadband_percent: float = 1.0  # 0.0-50.0, % of alarm limit


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
