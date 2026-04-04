"""Alarm-related DTOs for REST API."""
from __future__ import annotations

from pydantic import BaseModel


class AlarmResponse(BaseModel):
    id: int
    controller_id: int
    alarm_type: str
    priority: str
    value: float
    limit_value: float
    triggered_at: str
    cleared_at: str | None = None
    acknowledged: bool = False
    ack_by_user: str | None = None
    ack_at: str | None = None


class AlarmAckRequest(BaseModel):
    """No body needed — user comes from JWT."""
