"""Command DTOs for setpoint, mode, and output changes."""
from __future__ import annotations

from pydantic import BaseModel

from smart_pid_domain.enums import ControllerMode


class SetpointCommand(BaseModel):
    controller_id: int
    value: float


class ModeCommand(BaseModel):
    controller_id: int
    mode: ControllerMode


class OutputCommand(BaseModel):
    controller_id: int
    value: float


class OptimizationCommand(BaseModel):
    """Enable/disable the online tuning optimizer (ENABLE_OPTIMIZER) for a loop."""

    controller_id: int
    enabled: bool


class CommandResponse(BaseModel):
    ok: bool
    controller_id: int | None = None
    detail: str | None = None
    # Present on optimization toggle responses; reports the resulting state.
    enabled: bool | None = None
