"""Standalone virtual-plant twin — the simulator as its own process.

Wraps :class:`SimulatorAdapter` in a thin FastAPI control RPC so the daemon
can run the simulator over the network (OPC-UA for telemetry/control, this
REST surface for everything else) instead of embedding simulator dynamics
in-process. Entry point: ``smart-pid-sim`` (see ``main()``).

Trust boundary: this service has NO authentication. It is meant to bind to
loopback or a private Docker network only (``main()`` binds ``0.0.0.0`` so a
sibling container can reach it, but the REST port must stay unpublished to
the host — see deployment compose). Anything that can reach
``simulator_rest_port`` has full control of the twin.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter
from smart_pid_core.config import CoreSettings
from smart_pid_domain.dtos.commands import CommandResponse
from smart_pid_domain.dtos.simulator import (
    AutoDisturbanceRequest,
    AutoSPRequest,
    OPCUAServerStatus,
    SimulatorDisturbanceRequest,
    SimulatorLoopCreateRequest,
    SimulatorParametersRequest,
    SimulatorPIDParamsRequest,
    SimulatorPIDSPRequest,
    SimulatorPIDStatusResponse,
    SimulatorPresetRequest,
    SimulatorStatusResponse,
)

logger = logging.getLogger(__name__)


# ---- Request bodies with no matching existing DTO -------------------------
# The daemon-side SimulatorPIDModeRequest carries the display literal
# "MAN"/"AUTO" and translates it before calling SimulatorAdapter.set_pid_mode;
# the RPC client already has that int by the time it reaches the twin, so
# reusing the literal-carrying DTO here would force a second, pointless
# translation back. Same story for the two bodies below: nothing upstream of
# the twin models this exact shape.
class _PIDModeBody(BaseModel):
    controller_id: int
    mode: int


class _PIDOutputBody(BaseModel):
    controller_id: int
    co: float


class _LoadConfigBody(BaseModel):
    cfg: dict


def _not_registered(controller_id: int) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail=f"Controller {controller_id} is not registered in the simulator",
    )


def _require_controller(adapter: SimulatorAdapter, controller_id: int) -> None:
    if not adapter.has_controller(controller_id):
        raise _not_registered(controller_id)


def get_adapter(request: Request) -> SimulatorAdapter:
    return request.app.state.adapter


Adapter = Annotated[SimulatorAdapter, Depends(get_adapter)]


def _build_adapter(settings: CoreSettings) -> SimulatorAdapter:
    adapter = SimulatorAdapter(settings=settings)
    adapter.start_opcua()
    adapter.start()  # seeds the default loop (id=0) when _controllers is empty
    return adapter


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    # main() pre-seeds app.state.settings so the port it already told uvicorn
    # to bind and the settings the adapter runs on are the same CoreSettings
    # instance; a bare `uvicorn.run(app)` or a test harness that never called
    # main() falls back to building one from the environment here.
    settings: CoreSettings = getattr(app.state, "settings", None) or CoreSettings()  # type: ignore[call-arg]
    app.state.settings = settings
    app.state.adapter = _build_adapter(settings)
    logger.info(
        "simulator_service_started rest_port=%d opcua_port=%d opcua_endpoint=%s",
        settings.simulator_rest_port,
        settings.simulator_port,
        app.state.adapter.opcua_endpoint,
    )
    try:
        yield
    finally:
        app.state.adapter.stop()
        app.state.adapter.stop_opcua()


app = FastAPI(title="SmartPID Simulator Twin", lifespan=_lifespan)


@app.exception_handler(ValueError)
async def _value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/start", response_model=CommandResponse)
async def start_simulator(adapter: Adapter) -> CommandResponse:
    adapter.start()
    return CommandResponse(ok=True)


@app.post("/stop", response_model=CommandResponse)
async def stop_simulator(adapter: Adapter) -> CommandResponse:
    adapter.stop()
    return CommandResponse(ok=True)


@app.get("/status", response_model=SimulatorStatusResponse)
async def get_status(adapter: Adapter) -> SimulatorStatusResponse:
    return SimulatorStatusResponse(
        enabled=True, running=adapter.is_running, controllers=adapter.get_status(),
    )


@app.get("/controllers")
async def list_controllers(adapter: Adapter) -> dict:
    return {"controller_ids": list(adapter.get_status().keys())}


@app.post("/controllers")
async def create_controller(body: SimulatorLoopCreateRequest, adapter: Adapter) -> dict:
    if body.controller_id is None:
        raise HTTPException(
            status_code=422,
            detail="controller_id is required for POST /controllers; use POST /loops to auto-allocate one",
        )
    adapter.register_controller(body.controller_id, pv_min=body.pv_min, pv_max=body.pv_max)
    return {"ok": True, "controller_id": body.controller_id}


@app.delete("/controllers/{controller_id}")
async def delete_controller(controller_id: int, adapter: Adapter) -> dict:
    return {"removed": adapter.unregister_controller(controller_id)}


@app.post("/loops")
async def create_loop(body: SimulatorLoopCreateRequest, adapter: Adapter) -> dict:
    cid = adapter.create_loop(
        controller_id=body.controller_id, pv_min=body.pv_min, pv_max=body.pv_max,
    )
    return {"controller_id": cid}


@app.get("/opcua", response_model=OPCUAServerStatus)
async def get_opcua_status(adapter: Adapter) -> OPCUAServerStatus:
    return OPCUAServerStatus(
        running=adapter.opcua_running, port=adapter.opcua_port, endpoint=adapter.opcua_endpoint,
    )


@app.post("/opcua/start", response_model=CommandResponse)
async def start_opcua(adapter: Adapter) -> CommandResponse:
    adapter.start_opcua()
    return CommandResponse(ok=True)


@app.post("/opcua/stop", response_model=CommandResponse)
async def stop_opcua(adapter: Adapter) -> CommandResponse:
    adapter.stop_opcua()
    return CommandResponse(ok=True)


@app.post("/preset", response_model=CommandResponse)
async def set_preset(body: SimulatorPresetRequest, adapter: Adapter) -> CommandResponse:
    _require_controller(adapter, body.controller_id)
    adapter.set_preset(body.controller_id, body.preset)
    return CommandResponse(ok=True, controller_id=body.controller_id)


@app.put("/parameters", response_model=CommandResponse)
async def set_parameters(body: SimulatorParametersRequest, adapter: Adapter) -> CommandResponse:
    _require_controller(adapter, body.controller_id)
    adapter.set_parameters(body.controller_id, body.gain, body.tau1, body.tau2, body.dead_time)
    return CommandResponse(ok=True, controller_id=body.controller_id)


@app.post("/disturbance", response_model=CommandResponse)
async def inject_disturbance(
    body: SimulatorDisturbanceRequest, adapter: Adapter,
) -> CommandResponse:
    _require_controller(adapter, body.controller_id)
    if body.type == "step":
        adapter.inject_step(body.controller_id, body.amplitude)
    else:
        adapter.inject_noise(body.controller_id, body.amplitude)
    return CommandResponse(ok=True, controller_id=body.controller_id)


@app.delete("/disturbance/{controller_id}", response_model=CommandResponse)
async def clear_disturbance(controller_id: int, adapter: Adapter) -> CommandResponse:
    _require_controller(adapter, controller_id)
    adapter.clear_disturbance(controller_id)
    return CommandResponse(ok=True, controller_id=controller_id)


@app.post("/pid/params", response_model=CommandResponse)
async def set_pid_params(body: SimulatorPIDParamsRequest, adapter: Adapter) -> CommandResponse:
    _require_controller(adapter, body.controller_id)
    adapter.set_pid_params(body.controller_id, body.kp, body.ti, body.td)
    return CommandResponse(ok=True, controller_id=body.controller_id)


@app.post("/pid/sp", response_model=CommandResponse)
async def set_pid_sp(body: SimulatorPIDSPRequest, adapter: Adapter) -> CommandResponse:
    _require_controller(adapter, body.controller_id)
    adapter.set_pid_sp(body.controller_id, body.sp)
    return CommandResponse(ok=True, controller_id=body.controller_id)


@app.post("/pid/mode", response_model=CommandResponse)
async def set_pid_mode(body: _PIDModeBody, adapter: Adapter) -> CommandResponse:
    _require_controller(adapter, body.controller_id)
    adapter.set_pid_mode(body.controller_id, body.mode)
    return CommandResponse(ok=True, controller_id=body.controller_id)


@app.post("/pid/output", response_model=CommandResponse)
async def write_output(body: _PIDOutputBody, adapter: Adapter) -> CommandResponse:
    _require_controller(adapter, body.controller_id)
    adapter.write_output(body.controller_id, body.co)
    return CommandResponse(ok=True, controller_id=body.controller_id)


@app.get("/pid/status/{controller_id}", response_model=SimulatorPIDStatusResponse)
async def get_pid_status(controller_id: int, adapter: Adapter) -> SimulatorPIDStatusResponse:
    _require_controller(adapter, controller_id)
    return SimulatorPIDStatusResponse(**adapter.get_pid_status(controller_id))


@app.post("/auto-sp/{controller_id}", response_model=CommandResponse)
async def set_auto_sp(
    controller_id: int, body: AutoSPRequest, adapter: Adapter,
) -> CommandResponse:
    _require_controller(adapter, controller_id)
    adapter.set_auto_sp(controller_id, body)
    return CommandResponse(ok=True, controller_id=controller_id)


@app.post("/auto-disturbance/{controller_id}", response_model=CommandResponse)
async def set_auto_disturbance(
    controller_id: int, body: AutoDisturbanceRequest, adapter: Adapter,
) -> CommandResponse:
    _require_controller(adapter, controller_id)
    adapter.set_auto_disturbance(controller_id, body)
    return CommandResponse(ok=True, controller_id=controller_id)


@app.post("/load-config")
async def load_config(body: _LoadConfigBody, adapter: Adapter) -> dict:
    adapter.load_sim_config(body.cfg)
    return {"ok": True}


@app.get("/config/{controller_id}")
async def get_config(controller_id: int, adapter: Adapter) -> dict:
    _require_controller(adapter, controller_id)
    return adapter.get_config_dict(controller_id)


@app.post("/consume-dirty")
async def consume_dirty(adapter: Adapter) -> dict:
    return {"controller_ids": adapter.consume_dirty_cids()}


@app.get("/node-ids/{controller_id}")
async def get_node_ids(controller_id: int, adapter: Adapter) -> dict:
    _require_controller(adapter, controller_id)
    return adapter.opcua_node_ids(controller_id)


def main() -> None:
    """Entry point for the ``smart-pid-sim`` console script."""
    logging.basicConfig(level=logging.INFO)
    settings = CoreSettings()  # type: ignore[call-arg]
    app.state.settings = settings
    uvicorn.run(app, host="0.0.0.0", port=settings.simulator_rest_port)  # noqa: S104


if __name__ == "__main__":
    main()
