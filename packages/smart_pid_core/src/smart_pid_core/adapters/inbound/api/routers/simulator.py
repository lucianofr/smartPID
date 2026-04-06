"""Simulator control router."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_simulator_adapter,
    require_supervisor,
)
from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter  # noqa: TC001
from smart_pid_domain.dtos.auth import UserClaims  # noqa: TC001
from smart_pid_domain.dtos.commands import CommandResponse
from smart_pid_domain.dtos.simulator import (
    AutoDisturbanceRequest,
    AutoSPRequest,
    ControllerSimStatus,
    SimulatorDisturbanceRequest,
    SimulatorParametersRequest,
    SimulatorPIDEnableRequest,
    SimulatorPIDModeRequest,
    SimulatorPIDParamsRequest,
    SimulatorPIDSPRequest,
    SimulatorPIDStatusResponse,
    SimulatorPresetRequest,
    SimulatorStatusResponse,
)

router = APIRouter()


@router.post("/start", response_model=CommandResponse)
async def start_simulator(
    _user: Annotated[UserClaims, Depends(require_supervisor)],
    adapter: Annotated[SimulatorAdapter, Depends(get_simulator_adapter)],
) -> CommandResponse:
    adapter.start()
    return CommandResponse(ok=True, detail="Simulator started")


@router.post("/stop", response_model=CommandResponse)
async def stop_simulator(
    _user: Annotated[UserClaims, Depends(require_supervisor)],
    adapter: Annotated[SimulatorAdapter, Depends(get_simulator_adapter)],
) -> CommandResponse:
    adapter.stop()
    return CommandResponse(ok=True, detail="Simulator stopped")


@router.get("/status", response_model=SimulatorStatusResponse)
async def get_status(
    _user: Annotated[UserClaims, Depends(require_supervisor)],
    adapter: Annotated[SimulatorAdapter, Depends(get_simulator_adapter)],
) -> SimulatorStatusResponse:
    return SimulatorStatusResponse(enabled=True, controllers=adapter.get_status())


@router.post("/preset", response_model=CommandResponse)
async def set_preset(
    body: SimulatorPresetRequest,
    _user: Annotated[UserClaims, Depends(require_supervisor)],
    adapter: Annotated[SimulatorAdapter, Depends(get_simulator_adapter)],
) -> CommandResponse:
    adapter.set_preset(body.controller_id, body.preset)
    return CommandResponse(ok=True, controller_id=body.controller_id, detail="Preset applied")


@router.put("/parameters", response_model=CommandResponse)
async def set_parameters(
    body: SimulatorParametersRequest,
    _user: Annotated[UserClaims, Depends(require_supervisor)],
    adapter: Annotated[SimulatorAdapter, Depends(get_simulator_adapter)],
) -> CommandResponse:
    adapter.set_parameters(body.controller_id, body.gain, body.tau1, body.tau2, body.dead_time)
    return CommandResponse(ok=True, controller_id=body.controller_id, detail="Parameters updated")


@router.post("/disturbance", response_model=CommandResponse)
async def inject_disturbance(
    body: SimulatorDisturbanceRequest,
    _user: Annotated[UserClaims, Depends(require_supervisor)],
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
    _user: Annotated[UserClaims, Depends(require_supervisor)],
    adapter: Annotated[SimulatorAdapter, Depends(get_simulator_adapter)],
) -> CommandResponse:
    try:
        adapter.clear_disturbance(controller_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Controller not found in simulator") from exc
    return CommandResponse(ok=True, controller_id=controller_id, detail="Disturbances cleared")


@router.post("/{controller_id}/pid/enable", response_model=CommandResponse)
async def enable_pid(
    controller_id: int,
    body: SimulatorPIDEnableRequest,
    _user: Annotated[UserClaims, Depends(require_supervisor)],
    adapter: Annotated[SimulatorAdapter, Depends(get_simulator_adapter)],
) -> CommandResponse:
    try:
        adapter.enable_pid(controller_id, body.enabled)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Controller not found in simulator") from exc
    state = "enabled" if body.enabled else "disabled"
    return CommandResponse(ok=True, controller_id=controller_id, detail=f"PID {state}")


@router.post("/{controller_id}/pid/params", response_model=CommandResponse)
async def set_pid_params(
    controller_id: int,
    body: SimulatorPIDParamsRequest,
    _user: Annotated[UserClaims, Depends(require_supervisor)],
    adapter: Annotated[SimulatorAdapter, Depends(get_simulator_adapter)],
) -> CommandResponse:
    try:
        adapter.set_pid_params(controller_id, body.kp, body.ti, body.td)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Controller not found in simulator") from exc
    return CommandResponse(ok=True, controller_id=controller_id, detail="PID params updated")


@router.post("/{controller_id}/pid/sp", response_model=CommandResponse)
async def set_pid_sp(
    controller_id: int,
    body: SimulatorPIDSPRequest,
    _user: Annotated[UserClaims, Depends(require_supervisor)],
    adapter: Annotated[SimulatorAdapter, Depends(get_simulator_adapter)],
) -> CommandResponse:
    try:
        adapter.set_pid_sp(controller_id, body.sp)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Controller not found in simulator") from exc
    return CommandResponse(ok=True, controller_id=controller_id, detail=f"PID SP={body.sp}")


@router.post("/{controller_id}/pid/mode", response_model=CommandResponse)
async def set_pid_mode(
    controller_id: int,
    body: SimulatorPIDModeRequest,
    _user: Annotated[UserClaims, Depends(require_supervisor)],
    adapter: Annotated[SimulatorAdapter, Depends(get_simulator_adapter)],
) -> CommandResponse:
    try:
        mode_int = 1 if body.mode == "AUTO" else 0
        adapter.set_pid_mode(controller_id, mode_int)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Controller not found in simulator") from exc
    return CommandResponse(ok=True, controller_id=controller_id, detail=f"PID mode={body.mode}")


@router.get("/{controller_id}/pid/status", response_model=SimulatorPIDStatusResponse)
async def get_pid_status(
    controller_id: int,
    _user: Annotated[UserClaims, Depends(require_supervisor)],
    adapter: Annotated[SimulatorAdapter, Depends(get_simulator_adapter)],
) -> SimulatorPIDStatusResponse:
    try:
        status = adapter.get_pid_status(controller_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Controller not found in simulator") from exc
    return SimulatorPIDStatusResponse(**status)


@router.put("/{controller_id}/auto-sp", response_model=ControllerSimStatus)
async def set_auto_sp(
    controller_id: int,
    body: AutoSPRequest,
    _user: Annotated[UserClaims, Depends(require_supervisor)],
    adapter: Annotated[SimulatorAdapter, Depends(get_simulator_adapter)],
) -> ControllerSimStatus:
    try:
        adapter.set_auto_sp(controller_id, body)
        return adapter.get_controller_status(controller_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Controller not found in simulator") from exc


@router.put("/{controller_id}/auto-disturbance", response_model=ControllerSimStatus)
async def set_auto_disturbance(
    controller_id: int,
    body: AutoDisturbanceRequest,
    _user: Annotated[UserClaims, Depends(require_supervisor)],
    adapter: Annotated[SimulatorAdapter, Depends(get_simulator_adapter)],
) -> ControllerSimStatus:
    try:
        adapter.set_auto_disturbance(controller_id, body)
        return adapter.get_controller_status(controller_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail="Controller not found in simulator"
        ) from exc
