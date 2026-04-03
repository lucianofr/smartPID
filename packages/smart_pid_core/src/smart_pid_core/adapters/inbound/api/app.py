"""FastAPI application factory."""
from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI

from smart_pid_core.adapters.inbound.api.error_handlers import register_error_handlers
from smart_pid_core.adapters.inbound.api.routers import (
    auth,
    commands,
    controllers,
    history,
    simulator,
    system,
)

if TYPE_CHECKING:
    from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
    from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
    from smart_pid_core.adapters.outbound.user_repo import UserRepository
    from smart_pid_core.application.loop_manager import LoopManager
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
    simulator_adapter=None,
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

    # Register routers
    app.include_router(system.router, prefix="/system", tags=["system"])
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(controllers.router, prefix="/config/controllers", tags=["controllers"])
    app.include_router(commands.router, prefix="/command", tags=["commands"])
    app.include_router(history.router, prefix="/history", tags=["history"])
    app.include_router(simulator.router, prefix="/simulator", tags=["simulator"])

    register_error_handlers(app)

    return app
