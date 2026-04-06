"""Tests for /simulator REST endpoints."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from smart_pid_core.adapters.inbound.api.auth import create_access_token

if TYPE_CHECKING:
    from httpx import AsyncClient


@pytest.fixture
def admin_headers(sim_api_deps) -> dict[str, str]:
    token = create_access_token(
        user_id=1, username="admin", role="admin",
        secret=sim_api_deps["settings"].jwt_secret,
    )
    return {"Authorization": f"Bearer {token}"}


class TestGetStatus:
    @pytest.mark.asyncio
    async def test_status_returns_enabled(
        self, client_with_simulator: AsyncClient, admin_headers: dict[str, str],
    ) -> None:
        resp = await client_with_simulator.get("/simulator/status", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is True

    @pytest.mark.asyncio
    async def test_status_requires_auth(self, client_with_simulator: AsyncClient) -> None:
        resp = await client_with_simulator.get("/simulator/status")
        assert resp.status_code == 401


class TestSetPreset:
    @pytest.mark.asyncio
    async def test_set_flow_preset(
        self, client_with_simulator: AsyncClient, admin_headers: dict[str, str],
    ) -> None:
        resp = await client_with_simulator.post(
            "/simulator/preset",
            json={"controller_id": 1, "preset": "FLOW"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


class TestSetParameters:
    @pytest.mark.asyncio
    async def test_set_custom_parameters(
        self, client_with_simulator: AsyncClient, admin_headers: dict[str, str],
    ) -> None:
        resp = await client_with_simulator.put(
            "/simulator/parameters",
            json={"controller_id": 1, "gain": 3.0, "tau1": 15.0, "tau2": 8.0, "dead_time": 4.0},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


class TestDisturbance:
    @pytest.mark.asyncio
    async def test_inject_step(
        self, client_with_simulator: AsyncClient, admin_headers: dict[str, str],
    ) -> None:
        resp = await client_with_simulator.post(
            "/simulator/disturbance",
            json={"controller_id": 1, "type": "step", "amplitude": 5.0},
            headers=admin_headers,
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_clear_disturbance(
        self, client_with_simulator: AsyncClient, admin_headers: dict[str, str],
    ) -> None:
        await client_with_simulator.post(
            "/simulator/disturbance",
            json={"controller_id": 1, "type": "step", "amplitude": 5.0},
            headers=admin_headers,
        )
        resp = await client_with_simulator.delete(
            "/simulator/disturbance/1", headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


class TestSimulatorPIDEndpoints:
    @pytest.mark.asyncio
    async def test_enable_pid(
        self,
        client_with_simulator: AsyncClient,
        admin_headers: dict[str, str],
        sim_api_deps: dict,
    ) -> None:
        sim_api_deps["simulator_adapter"].register_controller(1)
        resp = await client_with_simulator.post(
            "/simulator/1/pid/enable",
            json={"controller_id": 1, "enabled": True},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    @pytest.mark.asyncio
    async def test_set_pid_params(
        self,
        client_with_simulator: AsyncClient,
        admin_headers: dict[str, str],
        sim_api_deps: dict,
    ) -> None:
        sim_api_deps["simulator_adapter"].register_controller(1)
        resp = await client_with_simulator.post(
            "/simulator/1/pid/params",
            json={"controller_id": 1, "kp": 2.0, "ti": 5.0, "td": 1.0},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    @pytest.mark.asyncio
    async def test_set_pid_mode(
        self,
        client_with_simulator: AsyncClient,
        admin_headers: dict[str, str],
        sim_api_deps: dict,
    ) -> None:
        sim_api_deps["simulator_adapter"].register_controller(1)
        resp = await client_with_simulator.post(
            "/simulator/1/pid/mode",
            json={"controller_id": 1, "mode": "AUTO"},
            headers=admin_headers,
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_pid_status(
        self,
        client_with_simulator: AsyncClient,
        admin_headers: dict[str, str],
        sim_api_deps: dict,
    ) -> None:
        adapter = sim_api_deps["simulator_adapter"]
        adapter.register_controller(1)
        adapter.enable_pid(1, enabled=True)
        adapter.set_pid_params(1, kp=3.0, ti=8.0, td=0.5)
        resp = await client_with_simulator.get(
            "/simulator/1/pid/status", headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is True
        assert data["kp"] == 3.0
        assert data["ti"] == 8.0
