"""Command router — setpoint, mode, and output changes."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_current_user,
    get_loop_manager,
)
from smart_pid_core.application.loop_manager import LoopManager
from smart_pid_domain.dtos.auth import UserClaims
from smart_pid_domain.dtos.commands import (
    CommandResponse,
    ModeCommand,
    OutputCommand,
    SetpointCommand,
)

router = APIRouter()


@router.post("/setpoint", response_model=CommandResponse)
async def set_setpoint(
    body: SetpointCommand,
    _user: Annotated[UserClaims, Depends(get_current_user)],
    lm: Annotated[LoopManager, Depends(get_loop_manager)],
) -> CommandResponse:
    lm.set_setpoint(body.controller_id, body.value)
    return CommandResponse(
        ok=True,
        controller_id=body.controller_id,
        detail=f"SP set to {body.value}",
    )


@router.post("/mode", response_model=CommandResponse)
async def set_mode(
    body: ModeCommand,
    _user: Annotated[UserClaims, Depends(get_current_user)],
    lm: Annotated[LoopManager, Depends(get_loop_manager)],
) -> CommandResponse:
    lm.set_mode(body.controller_id, body.mode)
    return CommandResponse(
        ok=True,
        controller_id=body.controller_id,
        detail=f"Mode set to {body.mode}",
    )


@router.post("/output", response_model=CommandResponse)
async def set_output(
    body: OutputCommand,
    _user: Annotated[UserClaims, Depends(get_current_user)],
    lm: Annotated[LoopManager, Depends(get_loop_manager)],
) -> CommandResponse:
    lm.set_output(body.controller_id, body.value)
    return CommandResponse(
        ok=True,
        controller_id=body.controller_id,
        detail=f"Output set to {body.value}",
    )
