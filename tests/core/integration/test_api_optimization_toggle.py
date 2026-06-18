"""Tests for /commands/optimization — enable/disable PID online tuning per loop."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from smart_pid_core.application.loop_manager import LoopContext
from smart_pid_core.application.workers.ai_worker import AIWorker
from smart_pid_domain.enums import AIEngine
from smart_pid_domain.models.controller import AIConfig, Controller, PIDParams

if TYPE_CHECKING:
    from httpx import AsyncClient


async def _create_loop_with_ai_worker(api_deps: dict, *, enabled: bool = True) -> int:
    """Save a controller (FUZZY engine) and register a loop with an AI worker.

    The AI worker thread is NOT started — we only exercise the in-memory
    enabled flag and the persisted state.
    """
    repo = api_deps["repo"]
    ctrl = Controller(
        id=0,
        name="FIC-200",
        pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
        ai_config=AIConfig(engine=AIEngine.FUZZY),
        optimization_enabled=enabled,
    )
    saved = await repo.save(ctrl)
    lm = api_deps["loop_manager"]
    bus = api_deps["bus"]
    ai_worker = AIWorker(bus=bus, controller=saved)
    ctx = LoopContext(controller=saved, ai_worker=ai_worker)
    lm._loops[saved.id] = ctx
    return saved.id


class TestOptimizationToggle:
    @pytest.mark.asyncio
    async def test_disable_optimization_persists_and_reports(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        cid = await _create_loop_with_ai_worker(api_deps, enabled=True)

        resp = await client.post(
            "/commands/optimization",
            json={"controller_id": cid, "enabled": False},
            headers=user_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["controller_id"] == cid
        # Response reports the new state.
        assert body["enabled"] is False

        # State is persisted to the repo.
        reloaded = await api_deps["repo"].get(cid)
        assert reloaded.optimization_enabled is False

        # The live AI worker reflects the disabled state (no tuning will run).
        worker = api_deps["loop_manager"].get_context(cid).ai_worker
        assert worker.is_enabled is False

    @pytest.mark.asyncio
    async def test_enable_optimization_persists_and_reports(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        cid = await _create_loop_with_ai_worker(api_deps, enabled=False)

        resp = await client.post(
            "/commands/optimization",
            json={"controller_id": cid, "enabled": True},
            headers=user_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True

        reloaded = await api_deps["repo"].get(cid)
        assert reloaded.optimization_enabled is True

        worker = api_deps["loop_manager"].get_context(cid).ai_worker
        assert worker.is_enabled is True

    @pytest.mark.asyncio
    async def test_optimization_unknown_controller(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/commands/optimization",
            json={"controller_id": 9999, "enabled": True},
            headers=user_headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_optimization_no_auth(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/commands/optimization",
            json={"controller_id": 1, "enabled": True},
        )
        assert resp.status_code == 401


class TestAIWorkerRespectsOptimizationFlag:
    """The worker gates tuning on the per-loop optimization flag."""

    def test_worker_disabled_when_optimization_disabled(self, api_deps: dict) -> None:
        bus = api_deps["bus"]
        ctrl = Controller(
            id=1,
            name="FIC-201",
            ai_config=AIConfig(engine=AIEngine.FUZZY),
            optimization_enabled=False,
        )
        worker = AIWorker(bus=bus, controller=ctrl)
        assert worker.is_enabled is False

    def test_worker_enabled_when_optimization_enabled(self, api_deps: dict) -> None:
        bus = api_deps["bus"]
        ctrl = Controller(
            id=1,
            name="FIC-202",
            ai_config=AIConfig(engine=AIEngine.FUZZY),
            optimization_enabled=True,
        )
        worker = AIWorker(bus=bus, controller=ctrl)
        assert worker.is_enabled is True
