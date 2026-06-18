"""Command router — setpoint, mode, output, and optimizer changes."""
from __future__ import annotations

import json
from dataclasses import replace
from typing import Annotated

import msgpack  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, HTTPException
from starlette.requests import Request

from smart_pid_core.adapters.inbound.api.dependencies import (
    audit_and_broadcast,
    controller_label,
    get_audit_repo,
    get_event_bus,
    get_execution_mode,
    get_loop_manager,
    get_repo,
    get_system_event_worker,
    require_operator,
    require_supervisor,
)
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository  # noqa: TC001
from smart_pid_core.application.event_bus import EventBus  # noqa: TC001
from smart_pid_core.application.loop_manager import LoopManager
from smart_pid_core.application.workers.system_event_worker import (  # noqa: TC001
    SystemEventWorker,
)
from smart_pid_core.domain.services.tuning_guardrails import clamp_tuning_params
from smart_pid_domain.dtos.auth import UserClaims
from smart_pid_domain.dtos.commands import (
    CommandResponse,
    ModeCommand,
    OptimizationCommand,
    OutputCommand,
    SetpointCommand,
)
from smart_pid_domain.enums import AuditAction, ControllerMode

router = APIRouter()

_MONITOR_DETAIL = "Not available in monitor mode. PID is controlled by external DCS."


@router.post("/setpoint", response_model=CommandResponse)
async def set_setpoint(
    body: SetpointCommand,
    request: Request,
    user: Annotated[UserClaims, Depends(require_operator)],
    lm: Annotated[LoopManager, Depends(get_loop_manager)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
    sew: Annotated[SystemEventWorker | None, Depends(get_system_event_worker)],
    execution_mode: Annotated[str, Depends(get_execution_mode)],
) -> CommandResponse:
    if execution_mode == "monitor":
        opcua = getattr(request.app.state, "opcua_adapter", None)
        if opcua is None or not opcua.is_connected:
            raise HTTPException(status_code=409, detail=_MONITOR_DETAIL)
        opcua.write_parameter(body.controller_id, "sp", body.value)
    else:
        lm.set_setpoint(body.controller_id, body.value)
    await audit_and_broadcast(
        audit_repo, sew,
        user.user_id, user.username, AuditAction.SP_CHANGE,
        f"controller:{body.controller_id}", json.dumps({"value": body.value}),
        message=(
            f"{user.username} changed SP of controller "
            f"{controller_label(request, body.controller_id)} to {body.value}"
        ),
    )
    return CommandResponse(
        ok=True,
        controller_id=body.controller_id,
        detail=f"SP set to {body.value}",
    )


@router.post("/mode", response_model=CommandResponse)
async def set_mode(
    body: ModeCommand,
    request: Request,
    user: Annotated[UserClaims, Depends(require_operator)],
    lm: Annotated[LoopManager, Depends(get_loop_manager)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
    sew: Annotated[SystemEventWorker | None, Depends(get_system_event_worker)],
    execution_mode: Annotated[str, Depends(get_execution_mode)],
) -> CommandResponse:
    if execution_mode == "monitor":
        opcua = getattr(request.app.state, "opcua_adapter", None)
        if opcua is None or not opcua.is_connected:
            raise HTTPException(status_code=409, detail=_MONITOR_DETAIL)
        success = opcua.write_target_mode(body.controller_id, ControllerMode(body.mode))
        if not success:
            raise HTTPException(
                status_code=502, detail="Failed to write mode to DCS",
            )
    else:
        lm.set_mode(body.controller_id, body.mode)
    await audit_and_broadcast(
        audit_repo, sew,
        user.user_id, user.username, AuditAction.MODE_CHANGE,
        f"controller:{body.controller_id}", json.dumps({"mode": body.mode}),
        message=(
            f"{user.username} changed mode of controller "
            f"{controller_label(request, body.controller_id)} to {body.mode}"
        ),
    )
    return CommandResponse(
        ok=True,
        controller_id=body.controller_id,
        detail=f"Mode set to {body.mode}",
    )


@router.post("/output", response_model=CommandResponse)
async def set_output(
    body: OutputCommand,
    request: Request,
    user: Annotated[UserClaims, Depends(require_operator)],
    lm: Annotated[LoopManager, Depends(get_loop_manager)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
    sew: Annotated[SystemEventWorker | None, Depends(get_system_event_worker)],
    execution_mode: Annotated[str, Depends(get_execution_mode)],
) -> CommandResponse:
    if execution_mode == "monitor":
        opcua = getattr(request.app.state, "opcua_adapter", None)
        if opcua is None or not opcua.is_connected:
            raise HTTPException(status_code=409, detail=_MONITOR_DETAIL)
        opcua.write_parameter(body.controller_id, "co", body.value)
    else:
        lm.set_output(body.controller_id, body.value)
    await audit_and_broadcast(
        audit_repo, sew,
        user.user_id, user.username, AuditAction.OUTPUT_CHANGE,
        f"controller:{body.controller_id}", json.dumps({"value": body.value}),
        message=(
            f"{user.username} set CO of controller "
            f"{controller_label(request, body.controller_id)} to {body.value}"
        ),
    )
    return CommandResponse(
        ok=True,
        controller_id=body.controller_id,
        detail=f"Output set to {body.value}",
    )


@router.post("/optimization", response_model=CommandResponse)
async def set_optimization(
    body: OptimizationCommand,
    request: Request,
    user: Annotated[UserClaims, Depends(require_operator)],
    repo: Annotated[SQLiteRepository, Depends(get_repo)],
    lm: Annotated[LoopManager, Depends(get_loop_manager)],
    bus: Annotated[EventBus, Depends(get_event_bus)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
    sew: Annotated[SystemEventWorker | None, Depends(get_system_event_worker)],
) -> CommandResponse:
    """Enable/disable the online tuning optimizer (ENABLE_OPTIMIZER) for a loop.

    Persists the per-loop flag and notifies the running AI worker so the change
    takes effect immediately. When disabled, SmartPID keeps monitoring and
    publishing telemetry/stats but does NOT compute or write tuning back.
    """
    try:
        controller = await repo.get(body.controller_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Controller {body.controller_id} not found",
        ) from exc

    # Persist the new state.
    updated = replace(controller, optimization_enabled=body.enabled)
    await repo.save(updated)

    # Keep the in-memory loop context in sync (best-effort: a loop may not be
    # registered yet, e.g. before the daemon started it).
    ctx = lm.get_context(body.controller_id)
    if ctx is not None:
        ctx.controller = replace(ctx.controller, optimization_enabled=body.enabled)
        if ctx.ai_worker is not None:
            ctx.ai_worker.set_enabled(body.enabled)

    # Notify the live AI worker via the existing command channel so it reacts
    # without a restart.
    pub = bus.create_publisher()
    try:
        cmd = {
            "controller_id": body.controller_id,
            "action": "start" if body.enabled else "stop",
        }
        pub.send(
            f"CMD.AI.{body.controller_id}".encode(),
            msgpack.packb(cmd),
        )
    finally:
        pub.close()

    state = "enabled" if body.enabled else "disabled"
    await audit_and_broadcast(
        audit_repo, sew,
        user.user_id, user.username, AuditAction.CONFIG_AI,
        f"controller:{body.controller_id}",
        json.dumps({"optimization_enabled": body.enabled}),
        message=(
            f"{user.username} {state} optimizer on controller "
            f"{controller_label(request, body.controller_id)}"
        ),
    )
    return CommandResponse(
        ok=True,
        controller_id=body.controller_id,
        enabled=body.enabled,
        detail=f"Optimization {state}",
    )


@router.post("/tuning", response_model=CommandResponse)
async def write_tuning(
    request: Request,
    body: dict,
    user: Annotated[UserClaims, Depends(require_operator)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
    sew: Annotated[SystemEventWorker | None, Depends(get_system_event_worker)],
) -> CommandResponse:
    """Write Kp/Ti/Td directly to OPC-UA."""
    controller_id = body.get("controller_id", 0)
    kp = body.get("kp")
    ti = body.get("ti")
    td = body.get("td")
    opcua = getattr(request.app.state, "opcua_adapter", None)
    if opcua is None or not opcua.is_connected:
        raise HTTPException(status_code=409, detail="OPC-UA not connected")
    opcua.write_pid_params(controller_id, kp, ti, td)
    _parts = [
        f"{name}={val:.4f}"
        for name, val in (("Kp", kp), ("Ti", ti), ("Td", td))
        if val is not None
    ]
    _parts_str = ", ".join(_parts) or "no change"
    await audit_and_broadcast(
        audit_repo, sew,
        user.user_id, user.username, AuditAction.TUNE_PID,
        f"controller:{controller_id}",
        json.dumps({"kp": kp, "ti": ti, "td": td}),
        message=(
            f"{user.username} tuned controller "
            f"{controller_label(request, controller_id)}: {_parts_str}"
        ),
    )
    return CommandResponse(
        ok=True, controller_id=controller_id,
        detail=f"Tuning written: Kp={kp}, Ti={ti}, Td={td}",
    )


@router.get("/tuning-recommendations/{controller_id}")
async def get_tuning_recommendation(
    controller_id: int,
    request: Request,
    user: Annotated[UserClaims, Depends(require_operator)],
) -> dict:
    """Return the current tuning recommendation for a controller."""
    from smart_pid_domain.dtos.ai import TuningRecommendationResponse

    recs: dict = getattr(request.app.state, "tuning_recommendations", {})
    rec = recs.get(controller_id)
    if rec is None:
        raise HTTPException(
            status_code=404,
            detail=f"No tuning recommendation for controller {controller_id}",
        )
    return TuningRecommendationResponse(
        controller_id=rec.controller_id,
        current_kp=rec.current_kp,
        current_ti=rec.current_ti,
        current_td=rec.current_td,
        recommended_kp=rec.recommended_kp,
        recommended_ti=rec.recommended_ti,
        recommended_td=rec.recommended_td,
        reason=rec.reason,
        timestamp=rec.timestamp,
        status=rec.status,
        source=getattr(rec, "source", None),
    ).model_dump()


@router.post("/apply-tuning/{controller_id}")
async def apply_tuning(
    controller_id: int,
    request: Request,
    user: Annotated[UserClaims, Depends(require_supervisor)],
    lm: Annotated[LoopManager, Depends(get_loop_manager)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
    sew: Annotated[SystemEventWorker | None, Depends(get_system_event_worker)],
) -> dict:
    """Apply a pending tuning recommendation to the DCS via OPC-UA."""
    # Get pending recommendation
    recs: dict = getattr(request.app.state, "tuning_recommendations", {})
    rec = recs.get(controller_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="No pending tuning recommendation")

    # Check external PID mode
    opcua = getattr(request.app.state, "opcua_adapter", None)
    if opcua is not None:
        ext_mode = opcua.read_actual_mode(controller_id)
        if ext_mode is not None and ext_mode != ControllerMode.AUTO:
            raise HTTPException(
                status_code=409,
                detail=f"External PID is in {ext_mode.value} mode"
                " — tuning write-back requires Auto",
            )

    # Apply guardrails
    ctrl = lm.get_controller(controller_id)
    kp, ti, td = clamp_tuning_params(
        current_kp=rec.current_kp,
        current_ti=rec.current_ti,
        current_td=rec.current_td,
        rec_kp=rec.recommended_kp,
        rec_ti=rec.recommended_ti,
        rec_td=rec.recommended_td,
        max_pct=ctrl.max_tuning_change_pct,
    )

    # Write to DCS
    if opcua is not None:
        opcua.write_pid_params(controller_id, kp, ti, td)

    # Clear recommendation
    recs.pop(controller_id, None)

    # Audit + broadcast
    await audit_and_broadcast(
        audit_repo, sew,
        user.user_id, user.username, AuditAction.TUNE_PID,
        f"controller:{controller_id}",
        f"Applied tuning: Kp={kp:.4f}, Ti={ti:.4f}, Td={td:.4f}",
        message=(
            f"{user.username} applied tuning to controller "
            f"{controller_label(request, controller_id)}: "
            f"Kp={kp:.4f}, Ti={ti:.4f}, Td={td:.4f}"
        ),
    )

    return {
        "controller_id": controller_id,
        "applied_kp": kp,
        "applied_ti": ti,
        "applied_td": td,
        "clamped": (
            kp != rec.recommended_kp
            or ti != rec.recommended_ti
            or td != rec.recommended_td
        ),
    }
