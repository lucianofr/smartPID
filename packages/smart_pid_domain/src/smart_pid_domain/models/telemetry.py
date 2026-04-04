"""Telemetry and control action models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from smart_pid_domain.models.signal import FFSignal

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class TelemetryFrame:
    """Immutable snapshot of a controller's process values.

    All process signals carry value + quality status + timestamp (FF semantics).
    """

    controller_id: int
    pv: FFSignal
    sp: FFSignal
    co: FFSignal
    bkcal_in: FFSignal
    integral_val: float
    timestamp: datetime


@dataclass(frozen=True)
class ControlAction:
    """Output from PID computation to be written to the process."""

    controller_id: int
    co: FFSignal
    bkcal_out: FFSignal
    integral_val: float
    timestamp: datetime
