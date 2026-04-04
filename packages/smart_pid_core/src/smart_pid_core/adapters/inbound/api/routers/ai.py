"""AI optimization router."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_ai_repo,
    get_ai_workers,
    require_operator,
)
from smart_pid_domain.dtos.ai import AIHistoryResponse, AIStatusResponse, AITuningLogEntry
from smart_pid_domain.dtos.auth import UserClaims  # noqa: TC001

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
        speed=worker._ai_config.process_speed,
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
