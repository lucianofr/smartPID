"""Alarm event model."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from smart_pid_domain.enums import AlarmPriority, AlarmType

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class AlarmEvent:
    """Immutable alarm event snapshot."""

    controller_id: int
    controller_name: str
    alarm_type: AlarmType
    priority: AlarmPriority
    value: float
    limit: float
    timestamp: datetime
