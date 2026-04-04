"""Command router — setpoint, mode, and output changes."""
from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_audit_repo,
    get_loop_manager,
    require_operator,
)
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository
from smart_pid_core.application.loop_manager import LoopManager
from smart_pid_domain.dtos.auth import UserClaims
from smart_pid_domain.dtos.commands import (
    CommandResponse,
    ModeCommand,
    OutputCommand,
    SetpointCommand,
)
from smart_pid_domain.enums import AuditAction

router = APIRouter()


@router.post("/setpoint", response_model=CommandResponse)
async def set_setpoint(
    body: SetpointCommand,
    user: Annotated[UserClaims, Depends(require_operator)],
    lm: Annotated[LoopManager, Depends(get_loop_manager)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> CommandResponse:
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
) -> CommandResponse:
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
) -> CommandResponse:
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
