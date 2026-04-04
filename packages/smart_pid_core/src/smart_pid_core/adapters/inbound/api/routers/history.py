"""History query router."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from smart_pid_core.adapters.inbound.api.dependencies import get_historian, require_operator
from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_domain.dtos.auth import UserClaims
from smart_pid_domain.dtos.history import HistoryResponse, TelemetryFrameDTO

router = APIRouter()


@router.get("/{controller_id}", response_model=HistoryResponse)
async def query_history(
    controller_id: int,
    _user: Annotated[UserClaims, Depends(require_operator)],
    historian: Annotated[SQLiteHistorian, Depends(get_historian)],
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=10000),
) -> HistoryResponse:
    now = datetime.now(tz=UTC)
    if start is None:
        start = now - timedelta(hours=1)
    if end is None:
        end = now

    frames = await historian.query(controller_id, start, end)
    frames = frames[:limit]

    frame_dtos = [
        TelemetryFrameDTO(
            timestamp=f.timestamp,
            pv=f.pv.value,
            sp=f.sp.value,
            co=f.co.value,
            mode="AUTO",
            status="GOOD" if f.pv.status.is_good else "BAD",
        )
        for f in frames
    ]

    return HistoryResponse(
        controller_id=controller_id,
        frames=frame_dtos,
        count=len(frame_dtos),
    )
