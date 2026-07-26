"""Tests for AI control endpoints (start/stop/pause) — Gap #15."""
from __future__ import annotations

from typing import TYPE_CHECKING

from unittest.mock import MagicMock

import pytest

from smart_pid_core.application.loop_manager import LoopContext
from smart_pid_core.application.workers.ai_worker import AIWorker
from smart_pid_domain.enums import AIEngine
from smart_pid_domain.models.controller import AIConfig, Controller, PIDParams

if TYPE_CHECKING:
    from httpx import AsyncClient


async def _register_ai_worker(api_deps: dict) -> int:
    """Save a controller and register a loop carrying a live-looking AI worker.

    ``LoopManager.get_ai_workers()`` — the dependency behind these routes —
    only reports workers whose thread ``is_alive()``, so a worker that was
    never started makes every call 404. These routes just resolve the worker,
    write an audit row and publish CMD.AI, so a spec'd stub exercises the real
    LoopManager lookup without running an AI thread in the test process.
    """
    saved = await api_deps["repo"].save(
        Controller(
            id=0,
            name="AIC-100",
            pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
            ai_config=AIConfig(engine=AIEngine.FUZZY),
        )
    )
    worker = MagicMock(spec=AIWorker)
    worker.is_alive.return_value = True
    lm = api_deps["loop_manager"]
    lm._loops[saved.id] = LoopContext(controller=saved, ai_worker=worker)
    return saved.id


class TestAIStartEndpoint:
    @pytest.mark.asyncio
    async def test_start_ai_returns_ok(
        self, client: AsyncClient, admin_headers: dict[str, str], api_deps: dict
    ) -> None:
        cid = await _register_ai_worker(api_deps)
        resp = await client.post(f"/controllers/{cid}/ai/start", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["controller_id"] == cid
        assert "start" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_start_ai_unknown_controller_404(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.post("/controllers/9999/ai/start", headers=admin_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_start_ai_no_auth(self, client: AsyncClient) -> None:
        resp = await client.post("/controllers/1/ai/start")
        assert resp.status_code == 401


class TestAIStopEndpoint:
    @pytest.mark.asyncio
    async def test_stop_ai_returns_ok(
        self, client: AsyncClient, admin_headers: dict[str, str], api_deps: dict
    ) -> None:
        cid = await _register_ai_worker(api_deps)
        resp = await client.post(f"/controllers/{cid}/ai/stop", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "stop" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_stop_ai_no_auth(self, client: AsyncClient) -> None:
        resp = await client.post("/controllers/1/ai/stop")
        assert resp.status_code == 401


class TestAIPauseEndpoint:
    @pytest.mark.asyncio
    async def test_pause_ai_returns_ok(
        self, client: AsyncClient, admin_headers: dict[str, str], api_deps: dict
    ) -> None:
        cid = await _register_ai_worker(api_deps)
        resp = await client.post(f"/controllers/{cid}/ai/pause", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "pause" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_pause_ai_no_auth(self, client: AsyncClient) -> None:
        resp = await client.post("/controllers/1/ai/pause")
        assert resp.status_code == 401
