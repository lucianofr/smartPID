"""Alarm router — active alarms, history, ACK."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_ai_repo,
    get_alarm_repo,
    get_audit_repo,
    require_operator,
)
from smart_pid_core.adapters.outbound.ai_repo import AIRepository  # noqa: TC001
from smart_pid_core.adapters.outbound.alarm_repo import AlarmRepository  # noqa: TC001
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository  # noqa: TC001
from smart_pid_domain.dtos.auth import UserClaims  # noqa: TC001
from smart_pid_domain.enums import AuditAction

router = APIRouter()


@router.get("/active")
async def get_active_alarms(
    _user: Annotated[UserClaims, Depends(require_operator)],
    alarm_repo: Annotated[AlarmRepository, Depends(get_alarm_repo)],
    controller_id: int | None = None,
    priority: str | None = None,
) -> list[dict]:
    return await alarm_repo.get_active(controller_id=controller_id, priority=priority)


@router.get("/history")
async def get_alarm_history(
    _user: Annotated[UserClaims, Depends(require_operator)],
    alarm_repo: Annotated[AlarmRepository, Depends(get_alarm_repo)],
    start: str = Query(...),
    end: str = Query(...),
    controller_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    from datetime import datetime as dt

    start_dt = dt.fromisoformat(start)
    end_dt = dt.fromisoformat(end)
    return await alarm_repo.get_history(
        start=start_dt,
        end=end_dt,
        controller_id=controller_id,
        limit=limit,
        offset=offset,
    )


@router.get("/ai-history")
async def get_ai_log_history(
    _user: Annotated[UserClaims, Depends(require_operator)],
    ai_repo: Annotated[AIRepository, Depends(get_ai_repo)],
    start: str = Query(...),
    end: str = Query(...),
    controller_id: int | None = None,
) -> list[dict]:
    from datetime import datetime as dt

    start_dt = dt.fromisoformat(start)
    end_dt = dt.fromisoformat(end)
    return await ai_repo.get_tuning_history_range(
        start=start_dt, end=end_dt, controller_id=controller_id,
    )


@router.post("/{alarm_id}/ack")
async def ack_alarm(
    alarm_id: int,
    user: Annotated[UserClaims, Depends(require_operator)],
    alarm_repo: Annotated[AlarmRepository, Depends(get_alarm_repo)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> dict:
    now = datetime.now(tz=UTC)
    result = await alarm_repo.acknowledge(alarm_id, user.username, now)
    await audit_repo.record(
        user.user_id,
        user.username,
        AuditAction.ACK_ALARM,
        f"alarm:{alarm_id}",
        None,
    )
    return {"status": "acknowledged", **result}


@router.post("/ack-all")
async def ack_all_alarms(
    user: Annotated[UserClaims, Depends(require_operator)],
    alarm_repo: Annotated[AlarmRepository, Depends(get_alarm_repo)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> dict:
    now = datetime.now(tz=UTC)
    result = await alarm_repo.acknowledge_all(user.username, now)
    await audit_repo.record(
        user.user_id,
        user.username,
        AuditAction.ACK_ALARM_ALL,
        None,
        f'{{"count": {result["acknowledged_count"]}}}',
    )
    return {"status": "acknowledged", **result}
