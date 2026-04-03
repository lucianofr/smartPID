"""Simulator request/response DTOs."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from smart_pid_domain.enums import ProcessPresetName


class SimulatorPresetRequest(BaseModel):
    controller_id: int
    preset: ProcessPresetName


class SimulatorParametersRequest(BaseModel):
    controller_id: int
    gain: float
    tau1: float
    tau2: float | None = None
    dead_time: float


class SimulatorDisturbanceRequest(BaseModel):
    controller_id: int
    type: Literal["step", "noise"]
    amplitude: float


class ControllerSimStatus(BaseModel):
    preset: str
    gain: float
    tau1: float
    tau2: float | None
    dead_time: float
    step_active: bool
    step_amplitude: float
    noise_active: bool
    noise_amplitude: float


class SimulatorStatusResponse(BaseModel):
    enabled: bool
    controllers: dict[int, ControllerSimStatus]
