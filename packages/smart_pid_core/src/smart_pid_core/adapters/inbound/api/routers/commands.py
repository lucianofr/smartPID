"""Command router — setpoint, mode, and output changes."""
from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from starlette.requests import Request

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_audit_repo,
    get_execution_mode,
    get_loop_manager,
    require_operator,
    require_supervisor,
)
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository
from smart_pid_core.application.loop_manager import LoopManager
from smart_pid_core.domain.services.tuning_guardrails import clamp_tuning_params
from smart_pid_domain.dtos.auth import UserClaims
from smart_pid_domain.dtos.commands import (
    CommandResponse,
    ModeCommand,
    OutputCommand,
    SetpointCommand,
)
from smart_pid_domain.enums import AuditAction

router = APIRouter()

_MONITOR_DETAIL = "Not available in monitor mode. PID is controlled by external DCS."


@router.post("/setpoint", response_model=CommandResponse)
async def set_setpoint(
    body: SetpointCommand,
    user: Annotated[UserClaims, Depends(require_operator)],
    lm: Annotated[LoopManager, Depends(get_loop_manager)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
    execution_mode: Annotated[str, Depends(get_execution_mode)],
) -> CommandResponse:
    if execution_mode == "monitor":
        raise HTTPException(status_code=409, detail=_MONITOR_DETAIL)
    lm.set_setpoint(body.controller_id, body.value)
    await audit_repo.record(
        user.user_id, user.username, AuditAction.SP_CHANGE,
        f"controller:{body.controller_id}", json.dumps({"value": body.value}),
    )
    return CommandResponse(
        ok=True,
        controller_id=body.controller_id,
        detail=f"SP set to {body.value}",
    )


@router.post("/mode", response_model=CommandResponse)
async def set_mode(
    body: ModeCommand,
    user: Annotated[UserClaims, Depends(require_operator)],
    lm: Annotated[LoopManager, Depends(get_loop_manager)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
    execution_mode: Annotated[str, Depends(get_execution_mode)],
) -> CommandResponse:
    if execution_mode == "monitor":
        raise HTTPException(status_code=409, detail=_MONITOR_DETAIL)
    lm.set_mode(body.controller_id, body.mode)
    await audit_repo.record(
        user.user_id, user.username, AuditAction.MODE_CHANGE,
        f"controller:{body.controller_id}", json.dumps({"mode": body.mode}),
    )
    return CommandResponse(
        ok=True,
        controller_id=body.controller_id,
        detail=f"Mode set to {body.mode}",
    )


@router.post("/output", response_model=CommandResponse)
async def set_output(
    body: OutputCommand,
    user: Annotated[UserClaims, Depends(require_operator)],
    lm: Annotated[LoopManager, Depends(get_loop_manager)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
    execution_mode: Annotated[str, Depends(get_execution_mode)],
) -> CommandResponse:
    if execution_mode == "monitor":
        raise HTTPException(status_code=409, detail=_MONITOR_DETAIL)
    lm.set_output(body.controller_id, body.value)
    await audit_repo.record(
        user.user_id, user.username, AuditAction.OUTPUT_CHANGE,
        f"controller:{body.controller_id}", json.dumps({"value": body.value}),
    )
    return CommandResponse(
        ok=True,
        controller_id=body.controller_id,
        detail=f"Output set to {body.value}",
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
        ext_mode = opcua.read_external_mode(controller_id)
        if ext_mode is not None and ext_mode.lower() != "auto":
            raise HTTPException(
                status_code=409,
                detail=f"External PID is in {ext_mode} mode — tuning write-back requires Auto",
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

    # Audit
    await audit_repo.record(
        user.user_id,
        user.username,
        AuditAction.TUNE_PID,
        f"controller:{controller_id}",
        f"Applied tuning: Kp={kp:.4f}, Ti={ti:.4f}, Td={td:.4f}",
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
