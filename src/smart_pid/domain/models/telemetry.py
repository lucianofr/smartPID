"""Telemetry and control action models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from smart_pid.domain.models.controller import SignalStatus

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class TelemetryFrame:
    """Immutable snapshot of a controller's process values."""

    controller_id: int
    pv: float
    sp: float
    co: float
    integral_val: float
    timestamp: datetime
    status: SignalStatus = SignalStatus.GOOD


@dataclass(frozen=True)
class ControlAction:
    """Output from PID computation to be written to the process."""

    controller_id: int
    co: float
    integral_val: float
    timestamp: datetime
