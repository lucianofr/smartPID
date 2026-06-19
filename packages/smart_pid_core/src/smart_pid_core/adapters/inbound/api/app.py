"""FastAPI application factory."""
from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from smart_pid_core.adapters.inbound.api.error_handlers import register_error_handlers
from smart_pid_core.adapters.inbound.api.routers import (
    ai,
    alarms,
    audit,
    auth,
    commands,
    controllers,
    export,
    history,
    opcua,
    project,
    simulator,
    stats,
    system,
    system_events,
)
from smart_pid_core.adapters.inbound.api.ws.realtime import (
    ConnectionManager,
    RealtimeBridge,
    register_realtime_ws,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter
    from smart_pid_core.adapters.outbound.ai_repo import AIRepository
    from smart_pid_core.adapters.outbound.alarm_repo import AlarmRepository
    from smart_pid_core.adapters.outbound.audit_repo import AuditRepository
    from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
    from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter
    from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
    from smart_pid_core.adapters.outbound.system_event_repo import SystemEventRepository
    from smart_pid_core.adapters.outbound.user_repo import UserRepository
    from smart_pid_core.application.event_bus import EventBus
    from smart_pid_core.application.loop_manager import LoopManager
    from smart_pid_core.application.project_service import ProjectService
    from smart_pid_core.application.workers.alarm_worker import AlarmWorker
    from smart_pid_core.application.workers.stats_worker import StatsWorker
    from smart_pid_core.config import CoreSettings


_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'"
    ),
}


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.start_time = time.monotonic()
    bridge = getattr(app.state, "realtime_bridge", None)
    if bridge is not None:
        await bridge.start()
    try:
        yield
    finally:
        if bridge is not None:
            await bridge.stop()


def create_app(
    *,
    repo: SQLiteRepository,
    historian: SQLiteHistorian,
    user_repo: UserRepository,
    loop_manager: LoopManager,
    settings: CoreSettings,
    simulator_adapter: SimulatorAdapter | None = None,
    opcua_adapter: OPCUAAdapter | None = None,
    stats_workers: dict[int, StatsWorker] | None = None,
    ai_workers: dict[int, object] | None = None,
    ai_repo: AIRepository | None = None,
    project_service: ProjectService | None = None,
    alarm_repo: AlarmRepository | None = None,
    alarm_worker: AlarmWorker | None = None,
    audit_repo: AuditRepository | None = None,
    system_event_repo: SystemEventRepository | None = None,
    event_bus: EventBus | None = None,
) -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(title="Smart PID API", version="2.0.0", lifespan=_lifespan)

    # Store dependencies on app.state for injection
    app.state.repo = repo
    app.state.historian = historian
    app.state.user_repo = user_repo
    app.state.loop_manager = loop_manager
    app.state.settings = settings
    app.state.project_service = project_service
    app.state.simulator_adapter = simulator_adapter
    app.state.opcua_adapter = opcua_adapter
    app.state.stats_workers = stats_workers or {}
    app.state.ai_workers = ai_workers or {}
    app.state.ai_repo = ai_repo
    app.state.alarm_repo = alarm_repo
    app.state.alarm_worker = alarm_worker
    app.state.audit_repo = audit_repo
    app.state.system_event_repo = system_event_repo
    app.state.event_bus = event_bus
    app.state.execution_mode = settings.execution_mode

    # RealtimeWS fan-out: one ConnectionManager + one EventBus->WS bridge.
    # The bridge only exists when there is a bus to drain; its start/stop is
    # driven by _lifespan.
    app.state.realtime_manager = ConnectionManager()
    app.state.realtime_bridge = (
        RealtimeBridge(event_bus, app.state.realtime_manager)
        if event_bus is not None
        else None
    )

    # Network hardening (TD-004). Middleware added later wraps earlier ones, so
    # TrustedHost is registered last to run outermost — bad Host headers are
    # rejected before any other processing.
    @app.middleware("http")
    async def _security_headers(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.trusted_hosts,
    )

    # Register routers
    # Stats and AI routers share /controllers prefix but have literal sub-paths
    # (e.g. /controllers/stats) — must be registered BEFORE the controllers CRUD
    # router whose /{controller_id} path param would swallow "stats"/"ai" as int.
    app.include_router(stats.router, prefix="/controllers", tags=["stats"])
    app.include_router(ai.router, prefix="/controllers", tags=["ai"])
    app.include_router(project.router, prefix="/project", tags=["project"])
    app.include_router(system.router, prefix="/system", tags=["system"])
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(controllers.router, prefix="/controllers", tags=["controllers"])
    app.include_router(commands.router, prefix="/commands", tags=["commands"])
    app.include_router(history.router, prefix="/history", tags=["history"])
    app.include_router(simulator.router, prefix="/simulator", tags=["simulator"])
    app.include_router(opcua.router, prefix="/opcua", tags=["opcua"])
    app.include_router(alarms.router, prefix="/alarms", tags=["alarms"])
    app.include_router(audit.router, prefix="/audit", tags=["audit"])
    app.include_router(system_events.router, prefix="/system-events", tags=["system-events"])
    app.include_router(export.router, prefix="/export", tags=["export"])

    # WebSocket realtime route (Backend->Web telemetry fan-out).
    register_realtime_ws(app)

    register_error_handlers(app)

    # SPA last: mount the built web bundle at "/" so it does not shadow the API
    # routers or the WS route. Only when configured and the directory exists.
    if settings.web_dist_dir and os.path.isdir(settings.web_dist_dir):
        app.mount(
            "/",
            StaticFiles(directory=settings.web_dist_dir, html=True),
            name="spa",
        )

    return app
