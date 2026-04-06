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


class CommandResponse(BaseModel):
    ok: bool
    controller_id: int | None = None
    detail: str | None = None
