"""Frozen domain events for the ZeroMQ event bus."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from datetime import datetime

    from smart_pid.domain.models.controller import ConnectionState
    from smart_pid.domain.models.telemetry import TelemetryFrame


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
class SystemStateChanged:
    """Published by Loop Manager on connection state changes."""

    new_state: ConnectionState
    reason: str
    event_id: UUID = field(default_factory=uuid4)
