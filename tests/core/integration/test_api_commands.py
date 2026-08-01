"""Tests for /commands endpoints."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from smart_pid_core.application.loop_manager import LoopContext
from smart_pid_core.application.workers.pid_worker import PIDWorker
from smart_pid_core.domain.services.pid_engine import PIDEngine
from smart_pid_core.domain.services.pid_mode_manager import ModeManager
from smart_pid_domain.models.controller import Controller, PIDParams

if TYPE_CHECKING:
    from httpx import AsyncClient


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
            "/commands/setpoint",
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
            "/commands/setpoint",
            json={"controller_id": cid, "value": 150.0},
            headers=user_headers,
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_setpoint_unknown_controller(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/commands/setpoint",
            json={"controller_id": 9999, "value": 50.0},
            headers=user_headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_setpoint_no_auth(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/commands/setpoint",
            json={"controller_id": 1, "value": 50.0},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    @pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
    async def test_setpoint_non_finite_literal_is_422(
        self, client: AsyncClient, user_headers: dict[str, str], literal: str
    ) -> None:
        """A non-finite JSON literal must be refused with a renderable body.

        ``json.loads`` accepts these literals, so the value reaches the DTO and
        is rejected there — but the 422 echoes it back, and JSONResponse
        renders with allow_nan=False. Without the sanitising handler the
        response itself raised and the client saw a 500.
        """
        resp = await client.post(
            "/commands/setpoint",
            content=f'{{"controller_id": 1, "value": {literal}}}',
            headers={**user_headers, "Content-Type": "application/json"},
        )
        assert resp.status_code == 422
        assert resp.json()["detail"][0]["type"] == "finite_number"


class TestModeCommand:
    @pytest.mark.asyncio
    async def test_set_valid_mode(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        cid = await _create_and_start_controller(api_deps)
        resp = await client.post(
            "/commands/mode",
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
            "/commands/mode",
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
            "/commands/output",
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
            "/commands/mode",
            json={"controller_id": cid, "mode": "AUTO"},
            headers=user_headers,
        )
        resp = await client.post(
            "/commands/output",
            json={"controller_id": cid, "value": 50.0},
            headers=user_headers,
        )
        assert resp.status_code == 400


class _FakeOPCUA:
    """Minimal OPC-UA stub that records the last write_pid_params call."""

    is_connected = True

    def __init__(self) -> None:
        self.written: tuple[int, float | None, float | None, float | None] | None = None

    def write_pid_params(
        self, controller_id: int, kp: float | None, ti: float | None, td: float | None,
    ) -> None:
        self.written = (controller_id, kp, ti, td)

    def read_actual_mode(self, controller_id: int):  # noqa: ANN201
        from smart_pid_domain.enums import ControllerMode

        return ControllerMode.AUTO


class TestWriteTuningCommand:
    @pytest.mark.asyncio
    async def test_rejects_user_role(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict, app
    ) -> None:
        """POST /commands/tuning is admin-only (spec §9.2 Appendix A)."""
        cid = await _create_and_start_controller(api_deps)
        fake = _FakeOPCUA()
        app.state.opcua_adapter = fake
        resp = await client.post(
            "/commands/tuning",
            json={"controller_id": cid, "kp": 5.0},
            headers=user_headers,
        )
        assert resp.status_code == 403
        assert fake.written is None

    @pytest.mark.asyncio
    async def test_no_auth_returns_401(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/commands/tuning",
            json={"controller_id": 1, "kp": 5.0},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_out_of_range_params_clamped(
        self,
        client: AsyncClient,
        supervisor_headers: dict[str, str],
        api_deps: dict,
        app,
    ) -> None:
        """A supervisor pushing a huge gain gets clamped to max_tuning_change_pct."""
        cid = await _create_and_start_controller(api_deps)
        fake = _FakeOPCUA()
        app.state.opcua_adapter = fake
        # Current gain is 1.0, max_tuning_change_pct defaults to 10% -> max 1.1
        resp = await client.post(
            "/commands/tuning",
            json={"controller_id": cid, "kp": 100.0},
            headers=supervisor_headers,
        )
        assert resp.status_code == 200
        assert fake.written is not None
        _id, written_kp, _ti, _td = fake.written
        assert written_kp is not None
        # Clamped to no more than +10% of current (1.0 -> 1.1)
        assert written_kp <= 1.1 + 1e-9

    @pytest.mark.asyncio
    async def test_invalid_body_type_rejected(
        self, client: AsyncClient, supervisor_headers: dict[str, str], api_deps: dict
    ) -> None:
        """A non-numeric kp must be rejected by Pydantic validation (422)."""
        cid = await _create_and_start_controller(api_deps)
        resp = await client.post(
            "/commands/tuning",
            json={"controller_id": cid, "kp": "not-a-number"},
            headers=supervisor_headers,
        )
        assert resp.status_code == 422
