"""Simulator control router."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_repo,
    get_simulator_client,
    require_admin,
    require_user,
)
from smart_pid_core.adapters.inbound.sim_persistence import persist_sim_config
from smart_pid_core.adapters.outbound.simulator_client import (
    SimulatorClient,
    bind_opcua_client,
)
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository  # noqa: TC001
from smart_pid_domain.dtos.auth import UserClaims  # noqa: TC001
from smart_pid_domain.dtos.commands import CommandResponse
from smart_pid_domain.dtos.simulator import (
    AutoDisturbanceRequest,
    AutoSPRequest,
    ControllerSimStatus,
    OPCUAServerStatus,
    SimulatorDisturbanceRequest,
    SimulatorLoopCreateRequest,
    SimulatorParametersRequest,
    SimulatorPIDModeRequest,
    SimulatorPIDParamsRequest,
    SimulatorPIDSPRequest,
    SimulatorPIDStatusResponse,
    SimulatorPresetRequest,
    SimulatorStatusResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _not_registered(controller_id: int) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail=f"Controller {controller_id} is not registered in the simulator",
    )


@asynccontextmanager
async def _sim_controller(client: SimulatorClient, controller_id: int) -> AsyncIterator[None]:
    """Scope a simulator operation to a controller the simulator actually has.

    Pre-checks membership (one ``GET /controllers`` round trip) so an unknown
    id is a 404 on *every* route instead of a per-route obligation. The
    ``except`` guards the race window after that check: SimulatorClient
    itself already turns any twin 404 into ``HTTPException(404, ...)`` (see
    ``SimulatorClient._request``), so this just normalizes the detail text to
    match the pre-check's message instead of whatever the twin worded it.

    404 rather than a domain ``ControllerNotFoundError``: the controller may
    well exist in the project database and merely be absent *here*, so this
    is an API-boundary fact about the simulator, not a domain fact about
    the controller.
    """
    if not await client.has_controller(controller_id):
        raise _not_registered(controller_id)
    try:
        yield
    except HTTPException as exc:
        if exc.status_code == 404:
            raise _not_registered(controller_id) from exc
        raise


@router.post("/start", response_model=CommandResponse)
async def start_simulator(
    _user: Annotated[UserClaims, Depends(require_admin)],
    client: Annotated[SimulatorClient, Depends(get_simulator_client)],
    repo: Annotated[SQLiteRepository, Depends(get_repo)],
) -> CommandResponse:
    # Sync project controllers (if any) so they are available in simulator
    controllers = await repo.list_all()
    for ctrl in controllers:
        await client.register_controller(
            ctrl.id,
            pv_min=ctrl.pv_scale.eu_min,
            pv_max=ctrl.pv_scale.eu_max,
        )
    # start() creates a default controller (id=0) if none registered (twin-side)
    await client.start()
    return CommandResponse(ok=True, detail="Simulator started")


@router.post("/stop", response_model=CommandResponse)
async def stop_simulator(
    _user: Annotated[UserClaims, Depends(require_admin)],
    client: Annotated[SimulatorClient, Depends(get_simulator_client)],
) -> CommandResponse:
    await client.stop()
    return CommandResponse(ok=True, detail="Simulator stopped")


@router.get("/status", response_model=SimulatorStatusResponse)
async def get_status(
    _user: Annotated[UserClaims, Depends(require_admin)],
    client: Annotated[SimulatorClient, Depends(get_simulator_client)],
) -> SimulatorStatusResponse:
    return SimulatorStatusResponse(
        enabled=True, running=await client.is_running(), controllers=await client.get_status(),
    )


# --- Loop lifecycle -------------------------------------------------------
# The simulator is an independent module: its loops are created and removed
# here, NOT as a side effect of project-controller CRUD. Deleting a malha
# leaves its twin running, and a twin can exist with no malha at all, which
# is what makes the simulator usable for tuning experiments on its own.


@router.post("/loops", response_model=ControllerSimStatus)
async def create_simulator_loop(
    body: SimulatorLoopCreateRequest,
    _user: Annotated[UserClaims, Depends(require_admin)],
    client: Annotated[SimulatorClient, Depends(get_simulator_client)],
    request: Request,
) -> ControllerSimStatus:
    cid = await client.create_loop(
        controller_id=body.controller_id,
        pv_min=body.pv_min,
        pv_max=body.pv_max,
    )
    # Point the OPC-UA client at the twin's freshly-minted nodes for this loop,
    # otherwise every telemetry read raises KeyError until the daemon restarts
    # (same rule run_daemon and POST /controllers apply — see bind_opcua_client).
    adapter = getattr(request.app.state, "opcua_adapter", None)
    if adapter is not None:
        try:
            await bind_opcua_client(adapter, client, [cid])
        except Exception:
            logger.exception("opcua_registration_sync_failed controller_id=%d", cid)
    return await client.get_controller_status(cid)


@router.delete("/loops/{controller_id}", status_code=204)
async def delete_simulator_loop(
    controller_id: int,
    _user: Annotated[UserClaims, Depends(require_admin)],
    client: Annotated[SimulatorClient, Depends(get_simulator_client)],
) -> Response:
    if not await client.unregister_controller(controller_id):
        raise _not_registered(controller_id)
    return Response(status_code=204)


@router.get("/opcua/status", response_model=OPCUAServerStatus)
async def get_opcua_status(
    _user: Annotated[UserClaims, Depends(require_admin)],
    client: Annotated[SimulatorClient, Depends(get_simulator_client)],
) -> OPCUAServerStatus:
    return OPCUAServerStatus(
        running=await client.opcua_running(),
        port=await client.opcua_port(),
        endpoint=await client.opcua_endpoint(),
    )


@router.post("/opcua/start", response_model=CommandResponse)
async def start_opcua_server(
    _user: Annotated[UserClaims, Depends(require_admin)],
    client: Annotated[SimulatorClient, Depends(get_simulator_client)],
) -> CommandResponse:
    await client.start_opcua()
    return CommandResponse(ok=True, detail="OPC-UA server started")


@router.post("/opcua/stop", response_model=CommandResponse)
async def stop_opcua_server(
    _user: Annotated[UserClaims, Depends(require_admin)],
    client: Annotated[SimulatorClient, Depends(get_simulator_client)],
) -> CommandResponse:
    await client.stop_opcua()
    return CommandResponse(ok=True, detail="OPC-UA server stopped")


@router.post("/preset", response_model=CommandResponse)
async def set_preset(
    body: SimulatorPresetRequest,
    _user: Annotated[UserClaims, Depends(require_admin)],
    client: Annotated[SimulatorClient, Depends(get_simulator_client)],
    repo: Annotated[SQLiteRepository, Depends(get_repo)],
) -> CommandResponse:
    async with _sim_controller(client, body.controller_id):
        await client.set_preset(body.controller_id, body.preset)
    await persist_sim_config(client, repo, body.controller_id)
    return CommandResponse(ok=True, controller_id=body.controller_id, detail="Preset applied")


@router.put("/parameters", response_model=CommandResponse)
async def set_parameters(
    body: SimulatorParametersRequest,
    _user: Annotated[UserClaims, Depends(require_admin)],
    client: Annotated[SimulatorClient, Depends(get_simulator_client)],
    repo: Annotated[SQLiteRepository, Depends(get_repo)],
) -> CommandResponse:
    async with _sim_controller(client, body.controller_id):
        await client.set_parameters(
            body.controller_id, body.gain, body.tau1, body.tau2, body.dead_time,
        )
    await persist_sim_config(client, repo, body.controller_id)
    return CommandResponse(ok=True, controller_id=body.controller_id, detail="Parameters updated")


@router.post("/disturbance", response_model=CommandResponse)
async def inject_disturbance(
    body: SimulatorDisturbanceRequest,
    _user: Annotated[UserClaims, Depends(require_admin)],
    client: Annotated[SimulatorClient, Depends(get_simulator_client)],
) -> CommandResponse:
    async with _sim_controller(client, body.controller_id):
        if body.type == "step":
            await client.inject_step(body.controller_id, body.amplitude)
        else:
            await client.inject_noise(body.controller_id, body.amplitude)
    return CommandResponse(
        ok=True, controller_id=body.controller_id, detail=f"{body.type} disturbance injected"
    )


@router.delete("/disturbance/{controller_id}", response_model=CommandResponse)
async def clear_disturbance(
    controller_id: int,
    _user: Annotated[UserClaims, Depends(require_admin)],
    client: Annotated[SimulatorClient, Depends(get_simulator_client)],
) -> CommandResponse:
    async with _sim_controller(client, controller_id):
        await client.clear_disturbance(controller_id)
    return CommandResponse(ok=True, controller_id=controller_id, detail="Disturbances cleared")


@router.post("/{controller_id}/pid/params", response_model=CommandResponse)
async def set_pid_params(
    controller_id: int,
    body: SimulatorPIDParamsRequest,
    _user: Annotated[UserClaims, Depends(require_admin)],
    client: Annotated[SimulatorClient, Depends(get_simulator_client)],
    repo: Annotated[SQLiteRepository, Depends(get_repo)],
) -> CommandResponse:
    async with _sim_controller(client, controller_id):
        await client.set_pid_params(controller_id, body.kp, body.ti, body.td)
    await persist_sim_config(client, repo, controller_id)
    return CommandResponse(ok=True, controller_id=controller_id, detail="PID params updated")


@router.post("/{controller_id}/pid/sp", response_model=CommandResponse)
async def set_pid_sp(
    controller_id: int,
    body: SimulatorPIDSPRequest,
    _user: Annotated[UserClaims, Depends(require_user)],
    client: Annotated[SimulatorClient, Depends(get_simulator_client)],
    repo: Annotated[SQLiteRepository, Depends(get_repo)],
) -> CommandResponse:
    async with _sim_controller(client, controller_id):
        await client.set_pid_sp(controller_id, body.sp)
    await persist_sim_config(client, repo, controller_id)
    return CommandResponse(ok=True, controller_id=controller_id, detail=f"PID SP={body.sp}")


@router.post("/{controller_id}/co", response_model=CommandResponse)
async def set_co(
    controller_id: int,
    body: SimulatorPIDSPRequest,  # reuse — same shape (float 0-100)
    _user: Annotated[UserClaims, Depends(require_user)],
    client: Annotated[SimulatorClient, Depends(get_simulator_client)],
    repo: Annotated[SQLiteRepository, Depends(get_repo)],
) -> CommandResponse:
    async with _sim_controller(client, controller_id):
        await client.write_output(controller_id, body.sp)
    await persist_sim_config(client, repo, controller_id)
    return CommandResponse(ok=True, controller_id=controller_id, detail=f"CO={body.sp}")


@router.post("/{controller_id}/pid/mode", response_model=CommandResponse)
async def set_pid_mode(
    controller_id: int,
    body: SimulatorPIDModeRequest,
    _user: Annotated[UserClaims, Depends(require_user)],
    client: Annotated[SimulatorClient, Depends(get_simulator_client)],
    repo: Annotated[SQLiteRepository, Depends(get_repo)],
) -> CommandResponse:
    mode_int = 1 if body.mode == "AUTO" else 0
    async with _sim_controller(client, controller_id):
        await client.set_pid_mode(controller_id, mode_int)
    await persist_sim_config(client, repo, controller_id)
    return CommandResponse(ok=True, controller_id=controller_id, detail=f"PID mode={body.mode}")


@router.get("/{controller_id}/pid/status", response_model=SimulatorPIDStatusResponse)
async def get_pid_status(
    controller_id: int,
    _user: Annotated[UserClaims, Depends(require_admin)],
    client: Annotated[SimulatorClient, Depends(get_simulator_client)],
) -> SimulatorPIDStatusResponse:
    async with _sim_controller(client, controller_id):
        status = await client.get_pid_status(controller_id)
    return SimulatorPIDStatusResponse(**status)


@router.put("/{controller_id}/auto-sp", response_model=ControllerSimStatus)
async def set_auto_sp(
    controller_id: int,
    body: AutoSPRequest,
    _user: Annotated[UserClaims, Depends(require_admin)],
    client: Annotated[SimulatorClient, Depends(get_simulator_client)],
    repo: Annotated[SQLiteRepository, Depends(get_repo)],
) -> ControllerSimStatus:
    async with _sim_controller(client, controller_id):
        await client.set_auto_sp(controller_id, body)
        await persist_sim_config(client, repo, controller_id)
        return await client.get_controller_status(controller_id)


@router.put("/{controller_id}/auto-disturbance", response_model=ControllerSimStatus)
async def set_auto_disturbance(
    controller_id: int,
    body: AutoDisturbanceRequest,
    _user: Annotated[UserClaims, Depends(require_admin)],
    client: Annotated[SimulatorClient, Depends(get_simulator_client)],
    repo: Annotated[SQLiteRepository, Depends(get_repo)],
) -> ControllerSimStatus:
    async with _sim_controller(client, controller_id):
        await client.set_auto_disturbance(controller_id, body)
        await persist_sim_config(client, repo, controller_id)
        return await client.get_controller_status(controller_id)
