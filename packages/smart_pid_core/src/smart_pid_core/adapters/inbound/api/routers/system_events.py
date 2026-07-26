"""System events router — read-only history endpoint."""
from __future__ import annotations

from datetime import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_system_event_repo,
    require_user,
)
from smart_pid_core.adapters.outbound.system_event_repo import SystemEventRepository  # noqa: TC001
from smart_pid_domain.dtos.auth import UserClaims  # noqa: TC001

router = APIRouter()


@router.get("")
async def get_system_events(
    _user: Annotated[UserClaims, Depends(require_user)],
    repo: Annotated[SystemEventRepository, Depends(get_system_event_repo)],
    start: str = Query(...),
    end: str = Query(...),
    source: str | None = None,
    severity: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    start_dt = dt.fromisoformat(start)
    end_dt = dt.fromisoformat(end)
    return await repo.get_history(
        start=start_dt,
        end=end_dt,
        source=source,
        severity=severity,
        limit=limit,
        offset=offset,
    )
