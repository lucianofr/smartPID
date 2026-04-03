"""Controller CRUD router."""
from __future__ import annotations

from dataclasses import replace
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_audit_repo,
    get_repo,
    require_admin,
    require_operator,
    require_supervisor,
)
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_domain.dtos.auth import UserClaims
from smart_pid_domain.enums import AuditAction
from smart_pid_domain.dtos.controllers import (
    ControllerCreate,
    ControllerResponse,
    ControllerUpdate,
)
from smart_pid_domain.exceptions import ControllerNotFoundError
from smart_pid_domain.models.controller import Controller, PIDParams

router = APIRouter()


def _to_response(c: Controller) -> ControllerResponse:
    """Convert domain Controller to API response DTO."""
    return ControllerResponse(
        id=c.id,
        name=c.name,
        description=c.description,
        mode=str(c.mode_normal),
        pv=0.0,
        sp=0.0,
        co=0.0,
        scan_rate_ms=c.scan_rate_ms,
        gain=c.pid_params.gain,
        reset=c.pid_params.reset,
        rate=c.pid_params.rate,
        sp_hi_lim=c.sp_hi_lim,
        sp_lo_lim=c.sp_lo_lim,
        out_hi_lim=c.out_hi_lim,
        out_lo_lim=c.out_lo_lim,
    )


@router.get("", response_model=list[ControllerResponse])
async def list_controllers(
    _user: Annotated[UserClaims, Depends(require_operator)],
    repo: Annotated[SQLiteRepository, Depends(get_repo)],
) -> list[ControllerResponse]:
    controllers = await repo.list_all()
    return [_to_response(c) for c in controllers]


@router.post("", response_model=ControllerResponse, status_code=status.HTTP_201_CREATED)
async def create_controller(
    body: ControllerCreate,
    user: Annotated[UserClaims, Depends(require_supervisor)],
    repo: Annotated[SQLiteRepository, Depends(get_repo)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> ControllerResponse:
    controller = Controller(
        id=0,
        name=body.name,
        description=body.description,
        scan_rate_ms=body.scan_rate_ms,
        pid_params=PIDParams(gain=body.gain, reset=body.reset, rate=body.rate),
        sp_hi_lim=body.sp_hi_lim,
        sp_lo_lim=body.sp_lo_lim,
        out_hi_lim=body.out_hi_lim,
        out_lo_lim=body.out_lo_lim,
    )
    saved = await repo.save(controller)
    await audit_repo.record(
        user.user_id, user.username, AuditAction.CREATE_CONTROLLER,
        f"controller:{saved.id}", f'{{"name": "{saved.name}"}}',
    )
    return _to_response(saved)


@router.get("/{controller_id}", response_model=ControllerResponse)
async def get_controller(
    controller_id: int,
    _user: Annotated[UserClaims, Depends(require_operator)],
    repo: Annotated[SQLiteRepository, Depends(get_repo)],
) -> ControllerResponse:
    try:
        controller = await repo.get(controller_id)
    except KeyError:
        raise ControllerNotFoundError(controller_id)
    return _to_response(controller)


@router.put("/{controller_id}", response_model=ControllerResponse)
async def update_controller(
    controller_id: int,
    body: ControllerUpdate,
    user: Annotated[UserClaims, Depends(require_supervisor)],
    repo: Annotated[SQLiteRepository, Depends(get_repo)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> ControllerResponse:
    try:
        controller = await repo.get(controller_id)
    except KeyError:
        raise ControllerNotFoundError(controller_id)

    updates: dict = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.description is not None:
        updates["description"] = body.description
    if body.scan_rate_ms is not None:
        updates["scan_rate_ms"] = body.scan_rate_ms
    if body.sp_hi_lim is not None:
        updates["sp_hi_lim"] = body.sp_hi_lim
    if body.sp_lo_lim is not None:
        updates["sp_lo_lim"] = body.sp_lo_lim
    if body.out_hi_lim is not None:
        updates["out_hi_lim"] = body.out_hi_lim
    if body.out_lo_lim is not None:
        updates["out_lo_lim"] = body.out_lo_lim

    pid_updates: dict = {}
    if body.gain is not None:
        pid_updates["gain"] = body.gain
    if body.reset is not None:
        pid_updates["reset"] = body.reset
    if body.rate is not None:
        pid_updates["rate"] = body.rate
    if pid_updates:
        updates["pid_params"] = replace(controller.pid_params, **pid_updates)

    if updates:
        controller = replace(controller, **updates)
        await repo.save(controller)

    await audit_repo.record(
        user.user_id, user.username, AuditAction.UPDATE_CONTROLLER,
        f"controller:{controller_id}", f'{{"fields": "{list(updates.keys())}"}}',
    )
    return _to_response(controller)


@router.delete("/{controller_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_controller(
    controller_id: int,
    user: Annotated[UserClaims, Depends(require_admin)],
    repo: Annotated[SQLiteRepository, Depends(get_repo)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> Response:
    try:
        await repo.delete(controller_id)
    except KeyError:
        raise ControllerNotFoundError(controller_id)
    await audit_repo.record(
        user.user_id, user.username, AuditAction.DELETE_CONTROLLER,
        f"controller:{controller_id}", None,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
