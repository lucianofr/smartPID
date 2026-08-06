"""System health-check and log-level control router."""
from __future__ import annotations

import logging
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from smart_pid_core.adapters.inbound.api.dependencies import require_admin
from smart_pid_core.application.log_control import LOG_LEVEL_NAMES, levels_at_or_above
from smart_pid_domain.dtos.auth import UserClaims  # noqa: TC001
from smart_pid_domain.dtos.system import (
    LogLevelsResponse,
    LogLevelsUpdate,
    SystemStatusResponse,
)

router = APIRouter()


def _process_metrics() -> tuple[float | None, float | None]:
    """CPU% for this process and system memory% used.

    Returns (None, None) when psutil is unavailable so a health probe never
    fails just because an optional metrics dependency is missing. The first
    cpu_percent() call after interval=None returns 0.0 by definition, so the
    process handle is cached across requests and the value becomes meaningful
    from the second poll onward.
    """
    try:
        import psutil
    except ImportError:
        return None, None
    proc = getattr(_process_metrics, "_proc", None)
    if proc is None:
        proc = psutil.Process()
        proc.cpu_percent(interval=None)  # prime the delta baseline
        _process_metrics._proc = proc  # type: ignore[attr-defined]
    try:
        return round(proc.cpu_percent(interval=None), 1), round(
            psutil.virtual_memory().percent, 1
        )
    except Exception:  # noqa: BLE001 — metrics must never break the probe
        return None, None


@router.get("/status", response_model=SystemStatusResponse)
async def system_status(request: Request) -> SystemStatusResponse:
    """Health check — no auth required."""
    start_time = getattr(request.app.state, "start_time", time.monotonic())
    loop_manager = request.app.state.loop_manager
    cpu, mem = _process_metrics()
    return SystemStatusResponse(
        status="running",
        uptime_s=round(time.monotonic() - start_time, 1),
        active_controllers=len(loop_manager._loops),
        bus_active=True,
        api_version="2.0.0",
        cpu_percent=cpu,
        memory_percent=mem,
    )


@router.get("/log-levels", response_model=LogLevelsResponse)
async def get_log_levels(
    _admin: Annotated[UserClaims, Depends(require_admin)],
    request: Request,
) -> LogLevelsResponse:
    controller = getattr(request.app.state, "log_level_controller", None)
    if controller is None:
        # Older app builds (e.g. tests that build a bare app) never wire the
        # controller; report the root logger's own effective level instead
        # of failing a read-only probe.
        current = levels_at_or_above(logging.getLogger().getEffectiveLevel())
    else:
        current = controller.levels
    return LogLevelsResponse(levels=list(current), available=list(LOG_LEVEL_NAMES))


@router.put("/log-levels", status_code=status.HTTP_204_NO_CONTENT)
async def set_log_levels(
    body: LogLevelsUpdate,
    _admin: Annotated[UserClaims, Depends(require_admin)],
    request: Request,
) -> Response:
    controller = getattr(request.app.state, "log_level_controller", None)
    if controller is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Log level controller is not configured on this app",
        )
    controller.set_levels(body.levels)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
