"""Frozen domain events for the ZeroMQ event bus."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from datetime import datetime

    from smart_pid_domain.enums import (
        AIEngine,
        AlarmPriority,
        AlarmType,
        ConnectionState,
        ControlObjective,
        InitSubStatus,
    )
    from smart_pid_domain.models.telemetry import TelemetryFrame


@dataclass(frozen=True)
class TelemetryReceived:
    """Published by I/O Worker when new telemetry is read."""

    controller_id: int
    frame: TelemetryFrame
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class ControlActionComputed:
    """Published by PID Worker after computing new output."""

    controller_id: int
    co: float
    integral_val: float
    delta_cv: float
    timestamp: datetime
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class AIActionComputed:
    """Published by AI Worker after computing a Ki adjustment."""

    controller_id: int
    gamma: float
    new_ki: float
    engine: AIEngine
    objective: ControlObjective
    reasoning: str
    timestamp: datetime
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class StatsUpdated:
    """Published by Stats Worker with latest performance metrics."""

    controller_id: int
    iae: float
    itae: float
    ise: float
    mse: float
    std_dev: float
    total_variation: float
    variability_sp: float
    variability_range: float
    timestamp: datetime
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class SystemStateChanged:
    """Published by Loop Manager on connection state changes."""

    new_state: ConnectionState
    reason: str
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class AlarmTriggered:
    """Published by AlarmWorker when an alarm activates."""

    controller_id: int
    alarm_type: AlarmType
    priority: AlarmPriority
    value: float
    limit: float
    timestamp: datetime
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class AlarmCleared:
    """Published by AlarmWorker when an alarm returns to normal."""

    controller_id: int
    alarm_type: AlarmType
    value: float
    timestamp: datetime
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class AlarmAcknowledged:
    """Published when a user acknowledges an alarm."""

    controller_id: int
    alarm_type: AlarmType
    user_id: int
    username: str
    timestamp: datetime
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class CascadeHandshakeChanged:
    """Published by PID Worker on cascade handshake state transitions."""

    controller_id: int
    old_sub_status: InitSubStatus
    new_sub_status: InitSubStatus
    trigger: str
    timestamp: datetime
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class TuningRecommended:
    """AI engine produced a tuning recommendation."""

    controller_id: int
    current_kp: float
    current_ti: float
    current_td: float
    recommended_kp: float
    recommended_ti: float
    recommended_td: float
    reason: str
    timestamp: float
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class TuningApplied:
    """Tuning parameters were written to the external DCS."""

    controller_id: int
    recommendation_id: UUID
    applied_kp: float
    applied_ti: float
    applied_td: float
    clamped: bool
    timestamp: float
    event_id: UUID = field(default_factory=uuid4)
