"""Simulator control router."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_current_user,
    get_simulator_adapter,
)
from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter
from smart_pid_domain.dtos.auth import UserClaims
from smart_pid_domain.dtos.commands import CommandResponse
from smart_pid_domain.dtos.simulator import (
    SimulatorDisturbanceRequest,
    SimulatorParametersRequest,
    SimulatorPresetRequest,
    SimulatorStatusResponse,
)

router = APIRouter()


@router.get("/status", response_model=SimulatorStatusResponse)
async def get_status(
    _user: Annotated[UserClaims, Depends(get_current_user)],
    adapter: Annotated[SimulatorAdapter, Depends(get_simulator_adapter)],
) -> SimulatorStatusResponse:
    return SimulatorStatusResponse(enabled=True, controllers=adapter.get_status())


@router.post("/preset", response_model=CommandResponse)
async def set_preset(
    body: SimulatorPresetRequest,
    _user: Annotated[UserClaims, Depends(get_current_user)],
    adapter: Annotated[SimulatorAdapter, Depends(get_simulator_adapter)],
) -> CommandResponse:
    adapter.set_preset(body.controller_id, body.preset)
    return CommandResponse(ok=True, controller_id=body.controller_id, detail="Preset applied")


@router.put("/parameters", response_model=CommandResponse)
async def set_parameters(
    body: SimulatorParametersRequest,
    _user: Annotated[UserClaims, Depends(get_current_user)],
    adapter: Annotated[SimulatorAdapter, Depends(get_simulator_adapter)],
) -> CommandResponse:
    adapter.set_parameters(body.controller_id, body.gain, body.tau1, body.tau2, body.dead_time)
    return CommandResponse(ok=True, controller_id=body.controller_id, detail="Parameters updated")


@router.post("/disturbance", response_model=CommandResponse)
async def inject_disturbance(
    body: SimulatorDisturbanceRequest,
    _user: Annotated[UserClaims, Depends(get_current_user)],
    adapter: Annotated[SimulatorAdapter, Depends(get_simulator_adapter)],
) -> CommandResponse:
    if body.type == "step":
        adapter.inject_step(body.controller_id, body.amplitude)
    else:
        adapter.inject_noise(body.controller_id, body.amplitude)
    return CommandResponse(
        ok=True, controller_id=body.controller_id, detail=f"{body.type} disturbance injected"
    )


@router.delete("/disturbance/{controller_id}", response_model=CommandResponse)
async def clear_disturbance(
    controller_id: int,
    _user: Annotated[UserClaims, Depends(get_current_user)],
    adapter: Annotated[SimulatorAdapter, Depends(get_simulator_adapter)],
) -> CommandResponse:
    adapter.clear_disturbance(controller_id)
    return CommandResponse(ok=True, controller_id=controller_id, detail="Disturbances cleared")
