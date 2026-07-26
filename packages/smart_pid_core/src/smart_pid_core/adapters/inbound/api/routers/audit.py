"""Audit trail router — any authenticated user can read."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_audit_repo,
    require_user,
)
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository
from smart_pid_domain.dtos.auth import UserClaims

router = APIRouter()


@router.get("")
async def get_audit_history(
    _user: Annotated[UserClaims, Depends(require_user)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
    start: str = Query(...),
    end: str = Query(...),
    user_id: int | None = None,
    action: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    from datetime import datetime

    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)
    return await audit_repo.get_history(
        start=start_dt,
        end=end_dt,
        user_id=user_id,
        action=action,
        limit=limit,
        offset=offset,
    )
