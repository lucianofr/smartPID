"""Alarm-related DTOs for REST API."""
from __future__ import annotations

from pydantic import BaseModel

from smart_pid_domain.enums import AlarmPriority, AlarmType  # noqa: TC001


class AlarmResponse(BaseModel):
    id: int
    controller_id: int
    alarm_type: AlarmType
    priority: AlarmPriority
    value: float
    limit_value: float
    triggered_at: str
    cleared_at: str | None = None
    acknowledged: bool = False
    ack_by_user: str | None = None
    ack_at: str | None = None


class AlarmAckRequest(BaseModel):
    """No body needed — user comes from JWT."""


class AlarmThreshold(BaseModel):
    """A single alarm threshold configuration."""
    alarm_type: AlarmType
    priority: AlarmPriority = AlarmPriority.WARNING
    limit: float = 0.0
    enabled: bool = True
    deadband: float = 0.0


class AlarmConfigResponse(BaseModel):
    """Full alarm configuration for a controller."""
    controller_id: int
    thresholds: list[AlarmThreshold]


class AlarmConfigUpdate(BaseModel):
    """Update request for alarm thresholds."""
    thresholds: list[AlarmThreshold]
