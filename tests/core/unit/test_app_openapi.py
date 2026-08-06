"""FastAPI docs/redoc/openapi surface is off by default (F3, security audit
2026-08-05): unauthenticated recon surface with no reason to be public. The
`SPID_API_EXPOSE_OPENAPI` env var (CoreSettings.expose_openapi) restores it
for local dev / the TestSprite MCP workflow.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient

from smart_pid_core.adapters.inbound.api.app import create_app
from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.adapters.outbound.user_repo import UserRepository
from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.loop_manager import LoopManager
from smart_pid_core.config import CoreSettings


@asynccontextmanager
async def _built_app(tmp_path, *, expose_openapi: bool) -> AsyncIterator[FastAPI]:
    repo = SQLiteRepository(tmp_path / "test.spid")
    await repo.initialize()
    historian = SQLiteHistorian(repo.session_factory)
    user_repo = UserRepository(tmp_path / "users.db")
    await user_repo.initialize()
    bus = EventBus(url_prefix=f"inproc://test_{uuid.uuid4().hex[:8]}")
    bus.start()
    loop_manager = LoopManager(bus=bus)
    settings = CoreSettings(
        _env_file=None,
        jwt_secret="test-secret-key-minimum-32-bytes!",
        expose_openapi=expose_openapi,
    )  # type: ignore[call-arg]

    app = create_app(
        repo=repo,
        historian=historian,
        user_repo=user_repo,
        loop_manager=loop_manager,
        settings=settings,
        event_bus=bus,
    )
    try:
        yield app
    finally:
        loop_manager.stop_all()
        bus.stop()
        await user_repo.close()
        await repo.close()


async def test_default_hides_docs_and_schema(tmp_path) -> None:
    async with _built_app(tmp_path, expose_openapi=False) as app:
        client = TestClient(app, base_url="http://127.0.0.1")
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404


async def test_expose_openapi_restores_docs_and_schema(tmp_path) -> None:
    async with _built_app(tmp_path, expose_openapi=True) as app:
        client = TestClient(app, base_url="http://127.0.0.1")
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        assert resp.json()["info"]["title"] == "Smart PID API"
        assert client.get("/docs").status_code == 200
        assert client.get("/redoc").status_code == 200
