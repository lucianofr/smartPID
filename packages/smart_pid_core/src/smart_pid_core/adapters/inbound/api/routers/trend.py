"""Trend buffer router — the in-memory last-hour ring behind every trend chart.

Companion of ``/history/{controller_id}``: that route replays the SQLite
historian (7-day retention, exports, multitrend replay); this one reads the
live ring (``TrendBuffer``) so a chart can paint the operator's chosen window
instantly and then keep appending realtime frames. Same ``HistoryResponse``
wire shape, so the client treats both identically.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_trend_buffer,
    require_user,
)
from smart_pid_core.application.trend_buffer import RETENTION_S, TrendBuffer
from smart_pid_domain.dtos.auth import UserClaims
from smart_pid_domain.dtos.history import HistoryResponse, TelemetryFrameDTO

router = APIRouter()


@router.get("/{controller_id}", response_model=HistoryResponse)
async def query_trend(
    controller_id: int,
    _user: Annotated[UserClaims, Depends(require_user)],
    buffer: Annotated[TrendBuffer, Depends(get_trend_buffer)],
    seconds: Annotated[
        int, Query(ge=1, le=int(RETENTION_S), description="Window length; capped at the 1 h ring")
    ] = int(RETENTION_S),
) -> HistoryResponse:
    samples = buffer.query(controller_id, float(seconds))
    frame_dtos = [
        TelemetryFrameDTO(
            timestamp=datetime.fromtimestamp(s.ts, tz=UTC),
            pv=s.pv,
            sp=s.sp,
            co=s.co,
            mode="AUTO",
            status="GOOD",
        )
        for s in samples
    ]
    return HistoryResponse(
        controller_id=controller_id,
        frames=frame_dtos,
        count=len(frame_dtos),
    )
