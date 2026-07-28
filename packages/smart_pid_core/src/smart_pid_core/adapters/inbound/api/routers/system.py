"""System health-check router."""
from __future__ import annotations

import time

from fastapi import APIRouter, Request

from smart_pid_domain.dtos.system import SystemStatusResponse

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
