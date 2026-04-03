"""System health-check router."""
from __future__ import annotations

import time

from fastapi import APIRouter, Request

from smart_pid_domain.dtos.system import SystemStatusResponse

router = APIRouter()


@router.get("/status", response_model=SystemStatusResponse)
async def system_status(request: Request) -> SystemStatusResponse:
    """Health check — no auth required."""
    start_time = getattr(request.app.state, "start_time", time.monotonic())
    loop_manager = request.app.state.loop_manager
    return SystemStatusResponse(
        status="running",
        uptime_s=round(time.monotonic() - start_time, 1),
        active_controllers=len(loop_manager._loops),
        bus_active=True,
        api_version="2.0.0",
    )
