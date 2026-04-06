"""AI optimization router — status, history, and start/stop/pause controls."""
from __future__ import annotations

import json
from typing import Annotated

import msgpack
from fastapi import APIRouter, Depends, HTTPException, status

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_ai_repo,
    get_ai_workers,
    get_audit_repo,
    get_event_bus,
    require_operator,
)
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository  # noqa: TC001
from smart_pid_core.application.event_bus import EventBus  # noqa: TC001
from smart_pid_domain.dtos.ai import AIHistoryResponse, AIStatusResponse, AITuningLogEntry
from smart_pid_domain.dtos.auth import UserClaims  # noqa: TC001
from smart_pid_domain.enums import AuditAction

router = APIRouter()


@router.get("/{controller_id}/ai/status", response_model=AIStatusResponse)
async def get_ai_status(
    controller_id: int,
    _user: Annotated[UserClaims, Depends(require_operator)],
    ai_workers: Annotated[dict, Depends(get_ai_workers)],
) -> AIStatusResponse:
    worker = ai_workers.get(controller_id)
    if worker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No AI worker for controller {controller_id}",
        )
    return AIStatusResponse(
        controller_id=controller_id,
        engine=worker._ai_config.engine,
        objective=worker._ai_config.objective,
        speed=worker._controller.process_speed,
        current_ki=worker._ki_current,
    )


@router.get("/{controller_id}/ai/history", response_model=AIHistoryResponse)
async def get_ai_history(
    controller_id: int,
    _user: Annotated[UserClaims, Depends(require_operator)],
    ai_repo: Annotated[object, Depends(get_ai_repo)],
) -> AIHistoryResponse:
    entries = await ai_repo.get_tuning_history(controller_id=controller_id, limit=50)
    return AIHistoryResponse(
        controller_id=controller_id,
        entries=[AITuningLogEntry(**e) for e in entries],
    )


@router.post("/{controller_id}/ai/start")
async def start_ai(
    controller_id: int,
    user: Annotated[UserClaims, Depends(require_operator)],
    bus: Annotated[EventBus, Depends(get_event_bus)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> dict:
    """Start AI optimization for a controller loop via ZMQ command."""
    pub = bus.create_publisher()
    try:
        cmd = {"controller_id": controller_id, "action": "start"}
        pub.send(
            f"CMD.AI.{controller_id}".encode(),
            msgpack.packb(cmd),
        )
    finally:
        pub.close()
    await audit_repo.record(
        user.user_id, user.username, AuditAction.CONFIG_AI,
        f"controller:{controller_id}", json.dumps({"action": "start"}),
    )
    return {"ok": True, "controller_id": controller_id, "detail": "AI start command sent"}


@router.post("/{controller_id}/ai/stop")
async def stop_ai(
    controller_id: int,
    user: Annotated[UserClaims, Depends(require_operator)],
    bus: Annotated[EventBus, Depends(get_event_bus)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> dict:
    """Stop AI optimization for a controller loop via ZMQ command."""
    pub = bus.create_publisher()
    try:
        cmd = {"controller_id": controller_id, "action": "stop"}
        pub.send(
            f"CMD.AI.{controller_id}".encode(),
            msgpack.packb(cmd),
        )
    finally:
        pub.close()
    await audit_repo.record(
        user.user_id, user.username, AuditAction.CONFIG_AI,
        f"controller:{controller_id}", json.dumps({"action": "stop"}),
    )
    return {"ok": True, "controller_id": controller_id, "detail": "AI stop command sent"}


@router.post("/{controller_id}/ai/pause")
async def pause_ai(
    controller_id: int,
    user: Annotated[UserClaims, Depends(require_operator)],
    bus: Annotated[EventBus, Depends(get_event_bus)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> dict:
    """Pause AI optimization for a controller loop via ZMQ command."""
    pub = bus.create_publisher()
    try:
        cmd = {"controller_id": controller_id, "action": "pause"}
        pub.send(
            f"CMD.AI.{controller_id}".encode(),
            msgpack.packb(cmd),
        )
    finally:
        pub.close()
    await audit_repo.record(
        user.user_id, user.username, AuditAction.CONFIG_AI,
        f"controller:{controller_id}", json.dumps({"action": "pause"}),
    )
    return {"ok": True, "controller_id": controller_id, "detail": "AI pause command sent"}
