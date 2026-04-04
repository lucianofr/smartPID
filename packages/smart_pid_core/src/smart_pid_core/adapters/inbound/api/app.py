"""FastAPI application factory."""
from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI

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
    simulator,
    stats,
    system,
    users,
)

if TYPE_CHECKING:
    from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter
    from smart_pid_core.adapters.outbound.ai_repo import AIRepository
    from smart_pid_core.adapters.outbound.alarm_repo import AlarmRepository
    from smart_pid_core.adapters.outbound.audit_repo import AuditRepository
    from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
    from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter
    from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
    from smart_pid_core.adapters.outbound.user_repo import UserRepository
    from smart_pid_core.application.loop_manager import LoopManager
    from smart_pid_core.application.workers.stats_worker import StatsWorker
    from smart_pid_core.config import CoreSettings


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.start_time = time.monotonic()
    yield


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
    alarm_repo: AlarmRepository | None = None,
    audit_repo: AuditRepository | None = None,
) -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(title="Smart PID API", version="2.0.0", lifespan=_lifespan)

    # Store dependencies on app.state for injection
    app.state.repo = repo
    app.state.historian = historian
    app.state.user_repo = user_repo
    app.state.loop_manager = loop_manager
    app.state.settings = settings
    app.state.simulator_adapter = simulator_adapter
    app.state.opcua_adapter = opcua_adapter
    app.state.stats_workers = stats_workers or {}
    app.state.ai_workers = ai_workers or {}
    app.state.ai_repo = ai_repo
    app.state.alarm_repo = alarm_repo
    app.state.audit_repo = audit_repo

    # Register routers
    app.include_router(system.router, prefix="/system", tags=["system"])
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(controllers.router, prefix="/controllers", tags=["controllers"])
    app.include_router(commands.router, prefix="/commands", tags=["commands"])
    app.include_router(history.router, prefix="/history", tags=["history"])
    app.include_router(simulator.router, prefix="/simulator", tags=["simulator"])
    app.include_router(opcua.router, prefix="/opcua", tags=["opcua"])
    app.include_router(stats.router, prefix="/controllers", tags=["stats"])
    app.include_router(ai.router, prefix="/controllers", tags=["ai"])
    app.include_router(alarms.router, prefix="/alarms", tags=["alarms"])
    app.include_router(users.router, prefix="/users", tags=["users"])
    app.include_router(audit.router, prefix="/audit", tags=["audit"])
    app.include_router(export.router, prefix="/export", tags=["export"])

    register_error_handlers(app)

    return app
