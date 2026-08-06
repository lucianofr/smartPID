"""Trend buffer router — the in-memory 72-hour ring behind every trend chart.

Companion of ``/history/{controller_id}``: that route replays the SQLite
historian (7-day retention, exports, multitrend replay); this one reads the
live ring (``TrendBuffer``) so a chart can paint the operator's chosen window
instantly and then keep appending realtime frames. Same ``HistoryResponse``
wire shape, so the client treats both identically.

The ring stores one sample per second, so a response is ``seconds`` frames at
most — the payload is bounded by the window the operator asked for, not by the
ring. The chart's selectable window is clamped well below the ring's own span
by the frontend (``TREND_WINDOW_MAX_S``); the deeper backlog is what a future
pan-to-the-past control will read.

Only ``HYDRATE_S`` is pre-loaded at boot, so for a while after a restart the
ring holds less than the operator can ask for. A window it cannot cover is
filled lazily here: one bucketed historian read for that ONE loop, over only
the missing span, then into the ring so the next request is served from memory.
That request pays a few hundred ms; it happens once per loop per depth.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_historian,
    get_trend_buffer,
    require_user,
)
from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_core.application.trend_buffer import (
    HYDRATE_S,
    RETENTION_S,
    TREND_INTERVAL_S,
    TrendBuffer,
)
from smart_pid_domain.dtos.auth import UserClaims
from smart_pid_domain.dtos.history import HistoryResponse, TelemetryFrameDTO

logger = structlog.get_logger()

router = APIRouter()


@router.get("/{controller_id}", response_model=HistoryResponse)
async def query_trend(
    controller_id: int,
    _user: Annotated[UserClaims, Depends(require_user)],
    buffer: Annotated[TrendBuffer, Depends(get_trend_buffer)],
    historian: Annotated[SQLiteHistorian, Depends(get_historian)],
    seconds: Annotated[
        int,
        Query(
            ge=1,
            le=int(RETENTION_S),
            description="Window length in seconds; capped at the 72 h ring",
        ),
    ] = int(HYDRATE_S),
) -> HistoryResponse:
    window = float(seconds)
    missing = buffer.gap(controller_id, window)
    if missing is not None:
        start, end = missing
        # A miss must not fail the request: the ring still answers with whatever
        # it holds, which is exactly the pre-lazy-fill behaviour.
        try:
            rows = await historian.query_decimated(
                controller_id,
                datetime.fromtimestamp(start, tz=UTC),
                datetime.fromtimestamp(end, tz=UTC),
                TREND_INTERVAL_S,
            )
        except Exception:
            logger.warning("trend_lazy_fill_failed", controller_id=controller_id, exc_info=True)
        else:
            stored = buffer.backfill(controller_id, rows)
            logger.info(
                "trend_lazy_filled",
                controller_id=controller_id,
                rows=len(rows),
                stored=stored,
                span_s=round(end - start, 1),
            )

    samples = buffer.query(controller_id, window)
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
