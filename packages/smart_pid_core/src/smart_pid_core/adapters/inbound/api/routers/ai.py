"""AI optimization router — status, history, and start/stop/pause controls."""
from __future__ import annotations

import json
from typing import Annotated

import msgpack
from fastapi import APIRouter, Depends, HTTPException, Request, status

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_audit_repo,
    get_ai_workers,
    get_settings,
    get_user_repo,
    require_admin,
    require_user,
)
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository  # noqa: TC001
from smart_pid_core.application.event_bus import EventBus  # noqa: TC001
from smart_pid_core.application.workers.system_event_worker import (  # noqa: TC001
    SystemEventWorker,
)
from smart_pid_domain.dtos.ai import AIHistoryResponse, AIStatusResponse, AITuningLogEntry
from smart_pid_domain.dtos.auth import UserClaims  # noqa: TC001
from smart_pid_domain.enums import AuditAction

router = APIRouter()


@router.get("/{controller_id}/ai/status", response_model=AIStatusResponse)
async def get_ai_status(controller_id: int, _user: Annotated[UserClaims, Depends(require_user)], settings: Annotated[CoreSettings, Depends(get_settings)], ai_workers: Annotated[dict[int, AIWorker], Depends(get_ai_workers)], audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)]) -> AIStatusResponse:
    worker = ai_workers.get(controller_id)
    detail=f"No AI worker for controller {controller_id}",
        )


async def get_ai_status(controller_id: int, _user: Annotated[UserClaims, Depends(require_user)], settings: Annotated[CoreSettings, Depends(get_settings)], ai_workers: Annotated[dict[int, AIWorker], Depends(get_ai_workers)], audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)]) -> AIStatusResponse:
    worker = ai_workers.get(controller_id)
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> AIStatusResponse:
    worker = ai_workers.get(controller_id)
        objective=worker._ai_config.objective,
        speed=worker._controller.process_speed,
        current_ki=worker._ki_current,
        enabled=worker.is_enabled,
    )

async def get_ai_history(controller_id: int, _user: Annotated[UserClaims, Depends(require_user)], settings: Annotated[CoreSettings, Depends(get_settings)], ai_repo: Annotated[AIRepository, Depends(get_ai_repo)]) -> AIHistoryResponse:
    entries = await ai_repo.get_tuning_history(controller_id=controller_id, limit=50)


async def start_ai(
async def get_ai_history(controller_id: int, _user: Annotated[UserClaims, Depends(require_user)], settings: Annotated[CoreSettings, Depends(get_settings)], ai_repo: Annotated[AIRepository, Depends(get_ai_repo)]) -> AIHistoryResponse:
    entries = await ai_repo.get_tuning_history(controller_id=controller_id, limit=50)
    return AIHistoryResponse(
        controller_id=controller_id,
        entries=[AITuningLogEntry(**e) for e in entries],
    )
    _user: Annotated[UserClaims, Depends(require_user)],
    settings: Annotated[CoreSettings, Depends(get_settings)],
    ai_repo: Annotated[AIRepository, Depends(get_ai_repo)],
) -> AIHistoryResponse:
    entries = await ai_repo.get_tuning_history(controller_id=controller_id, limit=50)
    return AIHistoryResponse(
        controller_id=controller_id,
        entries=[AITuningLogEntry(**e) for e in entries],
    )
            msgpack.packb(cmd),
async def start_ai(
    _admin: Annotated[UserClaims, Depends(require_admin)],
    controller_id: int,
    settings: Annotated[CoreSettings, Depends(get_settings)],
    ai_workers: Annotated[dict[int, "AIWorker"], Depends(get_ai_workers)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
    request: Request,
    bus: Annotated[EventBus, Depends(get_event_bus)],
) -> dict:
    """Start AI optimization for a controller loop via ZMQ command."""
    settings: Annotated[CoreSettings, Depends(get_settings)],
    ai_workers: Annotated[dict[int, "AIWorker"], Depends(get_ai_workers)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
    request: Request,
    bus: Annotated[EventBus, Depends(get_event_bus)],
) -> dict:
    """Start AI optimization for a controller loop via ZMQ command."""
    request: Request,
) -> dict:
    """Stop AI optimization for a controller loop via ZMQ command."""
    user: Annotated[UserClaims, Depends(require_authenticated_admin)],
    bus: Annotated[EventBus, Depends(get_event_bus)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
    sew: Annotated[SystemEventWorker | None, Depends(get_system_event_worker)],
) -> dict:
    """Stop AI optimization for a controller loop via ZMQ command."""
    pub = bus.create_publisher()
    try:
        cmd = {"controller_id": controller_id, "action": "stop"}
async def stop_ai(
    _admin: Annotated[UserClaims, Depends(require_admin)],
    controller_id: int,
    settings: Annotated[CoreSettings, Depends(get_settings)],
    ai_workers: Annotated[dict[int, "AIWorker"], Depends(get_ai_workers)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
    request: Request,
) -> dict:
    """Stop AI optimization for a controller loop via ZMQ command."""
    controller_id: int,
    settings: Annotated[CoreSettings, Depends(get_settings)],
    ai_workers: Annotated[dict[int, "AIWorker"], Depends(get_ai_workers)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
    request: Request,
) -> dict:
    """Stop AI optimization for a controller loop via ZMQ command."""
    """Pause AI optimization for a controller loop via ZMQ command."""
async def pause_ai(
    controller_id: int,
    request: Request,
    user: Annotated[UserClaims, Depends(require_authenticated_admin)],
    bus: Annotated[EventBus, Depends(get_event_bus)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
    sew: Annotated[SystemEventWorker | None, Depends(get_system_event_worker)],
async def pause_ai(
    _admin: Annotated[UserClaims, Depends(require_admin)],
    controller_id: int,
    settings: Annotated[CoreSettings, Depends(get_settings)],
    ai_workers: Annotated[dict[int, "AIWorker"], Depends(get_ai_workers)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
    request: Request,
) -> dict:
    """Pause AI optimization for a controller loop via ZMQ command."""
    """Pause AI optimization for a controller loop via ZMQ command."""
        f"controller:{controller_id}", json.dumps({"action": "pause"}),
        message=(
            f"{user.username} paused AI optimizer on controller "
            f"{controller_label(request, controller_id)}"
        ),
    )
    return {"ok": True, "controller_id": controller_id, "detail": "AI pause command sent"}
