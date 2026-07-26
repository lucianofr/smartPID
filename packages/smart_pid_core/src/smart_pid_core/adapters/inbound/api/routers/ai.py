"""AI optimization router — status, history, and start/stop/pause controls."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Annotated

import msgpack
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from smart_pid_core.adapters.inbound.api.auth import create_access_token  # noqa: TC001
from smart_pid_core.adapters.inbound.api.dependencies import (
    controller_label,
    get_audit_repo,
    get_ai_workers,
    get_current_user,
    get_settings,
    get_user_repo,
    require_admin,
    require_user,
)
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository  # noqa: TC001
from smart_pid_core.adapters.outbound.ai_repo import AIRepository  # noqa: TC001
from smart_pid_core.adapters.outbound.user_repo import User  # noqa: TC001
from smart_pid_core.application.event_bus import EventBus  # noqa: TC001
from smart_pid_core.application.loop_manager import LoopManager  # noqa: TC001
from smart_pid_core.application.workers.system_event_worker import (  # noqa: TC001
    SystemEventWorker,
)
from smart_pid_core.config import CoreSettings
from smart_pid_domain.dtos.ai import AIHistoryResponse, AIStatusResponse, AITuningLogEntry
from smart_pid_domain.dtos.auth import UserClaims  # noqa: TC001
from smart_pid_domain.enums import AuditAction

router = APIRouter()


async def _get_ai_worker(
    controller_id: int,
    settings: Annotated[CoreSettings, Depends(get_settings)],
    ai_workers: Annotated[dict[int, "AIWorker"], Depends(get_ai_workers)],
) -> "AIWorker":
    """Retrieve AI worker for controller, or raise 404."""
    worker = ai_workers.get(controller_id)
    if worker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No AI worker for controller {controller_id}",
        )
    return worker


@router.get("/{controller_id}/ai/status", response_model=AIStatusResponse)
async def get_ai_status(
    controller_id: int,
    user: Annotated[UserClaims, Depends(require_user)],
    settings: Annotated[CoreSettings, Depends(get_settings)],
    ai_workers: Annotated[dict[int, "AIWorker"], Depends(get_ai_workers)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> AIStatusResponse:
    """Return AI status for controller."""
    worker = ai_workers.get(controller_id)
    if worker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No AI worker for controller {controller_id}",
        )
    return AIStatusResponse(
        controller_id=controller_id,
        objective=worker._ai_config.objective,
        speed=worker._controller.process_speed,
        current_ki=worker._ki_current,
        enabled=worker.is_enabled,
    )


@router.get("/{controller_id}/ai/history", response_model=AIHistoryResponse)
async def get_ai_history(
    controller_id: int,
    user: Annotated[UserClaims, Depends(require_user)],
    settings: Annotated[CoreSettings, Depends(get_settings)],
    ai_repo: Annotated[AIRepository, Depends(get_ai_repo)],
) -> AIHistoryResponse:
    """Return AI history for controller optimization."""
    entries = await ai_repo.get_tuning_history(controller_id=controller_id, limit=50)
    return AIHistoryResponse(
        controller_id=controller_id,
        entries=[AITuningLogEntry(**e) for e in entries],
    )


@router.post("/{controller_id}/ai/start")
async def start_ai(
    _admin: Annotated[UserClaims, Depends(require_admin)],
    controller_id: int,
    settings: Annotated[CoreSettings, Depends(get_settings)],
    ai_workers: Annotated[dict[int, "AIWorker"], Depends(get_ai_workers)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
    request: Request,
    bus: Annotated[EventBus, Depends(get_event_bus)],
) -> dict:
    """Start AI optimization for a controller loop."""
    worker = ai_workers.get(controller_id)
    if worker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No AI worker for controller {controller_id}",
        )
    await audit_repo.record(
        _admin.user_id,
        _admin.username,
        AuditAction.START_AI_OPTIMIZATION,
        f"controller:{controller_id}",
        json.dumps({"action": "start"}),
    )
    pub = bus.create_publisher()
    cmd = {"controller_id": controller_id, "action": "start"}
    await pub.send(f"CMD.AI.{controller_id}".encode(), msgpack.packb(cmd))
    pub.close()
    return {"ok": True, "controller_id": controller_id, "detail": "AI start command sent"}


@router.post("/{controller_id}/ai/stop")
async def stop_ai(
    _admin: Annotated[UserClaims, Depends(require_admin)],
    controller_id: int,
    settings: Annotated[CoreSettings, Depends(get_settings)],
    ai_workers: Annotated[dict[int, "AIWorker"], Depends(get_ai_workers)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
    request: Request,
) -> dict:
    """Stop AI optimization for a controller loop."""
    worker = ai_workers.get(controller_id)
    if worker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No AI worker for controller {controller_id}",
        )
    await audit_repo.record(
        _admin.user_id,
        _admin.username,
        AuditAction.STOP_AI_OPTIMIZATION,
        f"controller:{controller_id}",
        json.dumps({"action": "stop"}),
    )
    pub = bus.create_publisher()
    cmd = {"controller_id": controller_id, "action": "stop"}
    await pub.send(f"CMD.AI.{controller_id}".encode(), msgpack.packb(cmd))
    pub.close()
    return {"ok": True, "controller_id": controller_id, "detail": "AI stop command sent"}


@router.post("/{controller_id}/ai/pause")
async def pause_ai(
    _admin: Annotated[UserClaims, Depends(require_admin)],
    controller_id: int,
    settings: Annotated[CoreSettings, Depends(get_settings)],
    ai_workers: Annotated[dict[int, "AIWorker"], Depends(get_ai_workers)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
    request: Request,
) -> dict:
    """Pause AI optimization for a controller loop."""
    worker = ai_workers.get(controller_id)
    if worker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No AI worker for controller {controller_id}",
        )
    await audit_repo.record(
        _admin.user_id,
        _admin.username,
        AuditAction.PAUSE_AI_OPTIMIZATION,
        f"controller:{controller_id}",
        json.dumps({"action": "pause"}),
    )
    pub = bus.create_publisher()
    cmd = {"controller_id": controller_id, "action": "pause"}
    await pub.send(f"CMD.AI.{controller_id}".encode(), msgpack.packb(cmd))
    pub.close()
    return {"ok": True, "controller_id": controller_id, "detail": "AI pause command sent"}
