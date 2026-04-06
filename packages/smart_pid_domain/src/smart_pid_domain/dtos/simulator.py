"""Simulator request/response DTOs."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from smart_pid_domain.enums import ProcessPresetName  # noqa: TC001 - pydantic needs runtime


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


class AutoSPRequest(BaseModel):
    enabled: bool
    sp_min_pct: float = Field(ge=0.0, le=100.0, default=30.0)
    sp_max_pct: float = Field(ge=0.0, le=100.0, default=70.0)


class AutoDisturbanceRequest(BaseModel):
    enabled: bool
    max_amplitude_pct: float = Field(ge=0.0, le=100.0, default=10.0)


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
    # PID internal state
    pid_enabled: bool = False
    pid_kp: float = 1.0
    pid_ti: float = 10.0
    pid_td: float = 0.0
    pid_mode: int = 0  # 0=MAN, 1=AUTO
    pid_cv: float = 0.0
    auto_sp: AutoSPRequest | None = None
    auto_disturbance: AutoDisturbanceRequest | None = None
    # Live computed values (updated each tick)
    pv: float = 0.0
    sp: float = 50.0
    co: float = 0.0
    error: float = 0.0
    process_input: float = 0.0
    process_output: float = 0.0
    disturbance_output: float = 0.0


class SimulatorStatusResponse(BaseModel):
    enabled: bool
    controllers: dict[int, ControllerSimStatus]


class SimulatorPIDEnableRequest(BaseModel):
    controller_id: int
    enabled: bool


class SimulatorPIDParamsRequest(BaseModel):
    controller_id: int
    kp: float
    ti: float
    td: float


class SimulatorPIDModeRequest(BaseModel):
    controller_id: int
    mode: Literal["MAN", "AUTO"]


class SimulatorPIDSPRequest(BaseModel):
    controller_id: int
    sp: float = Field(ge=0.0, le=100.0)


class SimulatorPIDStatusResponse(BaseModel):
    enabled: bool
    kp: float
    ti: float
    td: float
    mode: int  # 0=MAN, 1=AUTO
    cv: float


class OPCUAServerStatus(BaseModel):
    running: bool
    port: int
    endpoint: str
