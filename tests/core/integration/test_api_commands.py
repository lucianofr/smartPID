"""Tests for /command endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from smart_pid_core.application.loop_manager import LoopContext
from smart_pid_core.application.workers.pid_worker import PIDWorker
from smart_pid_core.domain.services.pid_engine import PIDEngine
from smart_pid_core.domain.services.pid_mode_manager import ModeManager
from smart_pid_domain.models.controller import Controller, PIDParams


async def _create_and_start_controller(api_deps: dict) -> int:
    """Helper: save controller to DB and register its loop (no thread start)."""
    repo = api_deps["repo"]
    ctrl = Controller(id=0, name="TIC-101", pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.0))
    saved = await repo.save(ctrl)
    # Register loop context without starting the PIDWorker thread to avoid hangs
    lm = api_deps["loop_manager"]
    bus = api_deps["bus"]
    engine = PIDEngine()
    mode_manager = ModeManager()
    pid_worker = PIDWorker(bus=bus, controller=saved, engine=engine, mode_manager=mode_manager)
    # Don't call pid_worker.start() — we only need the command interface
    ctx = LoopContext(
        controller=saved, pid_worker=pid_worker, engine=engine, mode_manager=mode_manager,
    )
    lm._loops[saved.id] = ctx
    return saved.id


class TestSetpointCommand:
    @pytest.mark.asyncio
    async def test_set_valid_setpoint(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        cid = await _create_and_start_controller(api_deps)
        resp = await client.post(
            "/command/setpoint",
            json={"controller_id": cid, "value": 55.0},
            headers=user_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    @pytest.mark.asyncio
    async def test_setpoint_above_limit(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        cid = await _create_and_start_controller(api_deps)
        resp = await client.post(
            "/command/setpoint",
            json={"controller_id": cid, "value": 150.0},
            headers=user_headers,
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_setpoint_unknown_controller(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/command/setpoint",
            json={"controller_id": 9999, "value": 50.0},
            headers=user_headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_setpoint_no_auth(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/command/setpoint",
            json={"controller_id": 1, "value": 50.0},
        )
        assert resp.status_code == 401


class TestModeCommand:
    @pytest.mark.asyncio
    async def test_set_valid_mode(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        cid = await _create_and_start_controller(api_deps)
        resp = await client.post(
            "/command/mode",
            json={"controller_id": cid, "mode": "MAN"},
            headers=user_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    @pytest.mark.asyncio
    async def test_set_invalid_mode(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        cid = await _create_and_start_controller(api_deps)
        resp = await client.post(
            "/command/mode",
            json={"controller_id": cid, "mode": "CAS"},
            headers=user_headers,
        )
        assert resp.status_code == 400


class TestOutputCommand:
    @pytest.mark.asyncio
    async def test_set_output_in_man_mode(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        cid = await _create_and_start_controller(api_deps)
        # Worker starts in MAN mode
        resp = await client.post(
            "/command/output",
            json={"controller_id": cid, "value": 50.0},
            headers=user_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    @pytest.mark.asyncio
    async def test_set_output_not_in_man_fails(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        cid = await _create_and_start_controller(api_deps)
        # Switch to AUTO first
        await client.post(
            "/command/mode",
            json={"controller_id": cid, "mode": "AUTO"},
            headers=user_headers,
        )
        resp = await client.post(
            "/command/output",
            json={"controller_id": cid, "value": 50.0},
            headers=user_headers,
        )
        assert resp.status_code == 400
