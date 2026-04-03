"""Performance statistics router."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_stats_workers,
    require_operator,
)
from smart_pid_domain.dtos.ai import StatsResponse
from smart_pid_domain.dtos.auth import UserClaims  # noqa: TC001

router = APIRouter()


@router.get("/{controller_id}/stats", response_model=StatsResponse)
async def get_stats(
    controller_id: int,
    _user: Annotated[UserClaims, Depends(require_operator)],
    stats_workers: Annotated[dict, Depends(get_stats_workers)],
) -> StatsResponse:
    worker = stats_workers.get(controller_id)
    if worker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No stats worker for controller {controller_id}",
        )
    data = worker.get_current_stats()
    return StatsResponse(**data)
