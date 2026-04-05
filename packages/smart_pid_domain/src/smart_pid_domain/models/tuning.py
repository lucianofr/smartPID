"""Domain models for PID tuning read-back and recommendations."""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from smart_pid_domain.enums import TuningRecStatus


@dataclass(frozen=True)
class PIDParamsRead:
    """Snapshot of PID tuning parameters read from external DCS."""

    kp: float | None
    ti: float | None
    td: float | None
    timestamp: float


@dataclass(frozen=True)
class TuningRecommendation:
    """AI-generated tuning recommendation awaiting approval or auto-applied."""

    id: UUID
    controller_id: int
    current_kp: float
    current_ti: float
    current_td: float
    recommended_kp: float
    recommended_ti: float
    recommended_td: float
    reason: str
    timestamp: float
    status: TuningRecStatus = field(default=TuningRecStatus.PENDING)
