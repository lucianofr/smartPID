"""Integration tests for auto-excitation endpoints."""
from __future__ import annotations

import socket
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from smart_pid_core.adapters.inbound.api.app import create_app
from smart_pid_core.adapters.inbound.api.auth import create_access_token
from smart_pid_core.adapters.outbound.simulator_client import SimulatorClient
from smart_pid_core.adapters.outbound.user_repo import User
from smart_pid_core.config import CoreSettings
from smart_pid_core.simulator_service import app as twin_app


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _make_settings() -> CoreSettings:
    return CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        simulator_enabled=True,
        simulator_interval_ms=20,
        simulator_port=_free_port(),
    )  # type: ignore[call-arg]


def _mock_user_repo() -> MagicMock:
    """Authorization resolves the token against the store on every request
    (E2E-044), so the mock has to answer with a real, active principal."""
    m = MagicMock()
    m.get_by_id = AsyncMock(
        return_value=User(
            id=1, username="tester", password_hash="x",
            role="admin", created_at="",
        )
    )
    return m


@pytest.fixture
async def client() -> AsyncIterator[tuple[httpx.AsyncClient, SimulatorClient, dict]]:
    """Real SimulatorAdapter + real OPC-UA server behind the twin's REST app,
    reached through SimulatorClient over an in-process ASGI transport — the
    same shape as production, both apps just live in one test process.
    """
    settings = _make_settings()
    twin_app.state.settings = settings
    async with twin_app.router.lifespan_context(twin_app):
        transport = httpx.ASGITransport(app=twin_app)
        simulator_client = SimulatorClient(base_url="http://simulator", transport=transport)
        await simulator_client.register_controller(1)

        mock_repo = MagicMock()
        mock_repo.save_sim_config = AsyncMock()
        daemon_app = create_app(
            repo=mock_repo,
            historian=MagicMock(),
            user_repo=_mock_user_repo(),
            loop_manager=MagicMock(),
            settings=settings,
            simulator_client=simulator_client,
            opcua_adapter=None,
            stats_workers=[],
            ai_workers=[],
            ai_repo=MagicMock(),
            alarm_repo=MagicMock(),
            audit_repo=MagicMock(),
        )

        token = create_access_token(
            user_id=1,
            username="tester",
            role="admin",
            secret=settings.jwt_secret,
        )
        headers = {"Authorization": f"Bearer {token}"}
        daemon_transport = httpx.ASGITransport(app=daemon_app)
        async with httpx.AsyncClient(
            transport=daemon_transport, base_url="http://127.0.0.1",
        ) as c:
            yield c, simulator_client, headers
        await simulator_client.aclose()


class TestAutoSPEndpoint:
    @pytest.mark.asyncio
    async def test_put_auto_sp_returns_200(self, client) -> None:
        c, _, headers = client
        resp = await c.put(
            "/simulator/1/auto-sp",
            json={"enabled": True, "sp_min_pct": 25.0, "sp_max_pct": 75.0},
            headers=headers,
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_put_auto_sp_updates_adapter(self, client) -> None:
        c, simulator_client, headers = client
        await c.put(
            "/simulator/1/auto-sp",
            json={"enabled": True, "sp_min_pct": 10.0, "sp_max_pct": 90.0},
            headers=headers,
        )
        status = await simulator_client.get_controller_status(1)
        assert status.auto_sp.enabled is True
        assert status.auto_sp.sp_min_pct == 10.0

    @pytest.mark.asyncio
    async def test_put_auto_sp_404_unknown_controller(self, client) -> None:
        c, _, headers = client
        resp = await c.put("/simulator/999/auto-sp", json={"enabled": True}, headers=headers)
        assert resp.status_code == 404


class TestAutoDisturbanceEndpoint:
    @pytest.mark.asyncio
    async def test_put_auto_dist_returns_200(self, client) -> None:
        c, _, headers = client
        resp = await c.put(
            "/simulator/1/auto-disturbance",
            json={"enabled": True, "max_amplitude_pct": 20.0},
            headers=headers,
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_put_auto_dist_updates_adapter(self, client) -> None:
        c, simulator_client, headers = client
        await c.put(
            "/simulator/1/auto-disturbance",
            json={"enabled": True, "max_amplitude_pct": 30.0},
            headers=headers,
        )
        status = await simulator_client.get_controller_status(1)
        assert status.auto_disturbance.enabled is True
        assert status.auto_disturbance.max_amplitude_pct == 30.0

    @pytest.mark.asyncio
    async def test_put_auto_dist_404_unknown_controller(self, client) -> None:
        c, _, headers = client
        resp = await c.put(
            "/simulator/999/auto-disturbance", json={"enabled": True}, headers=headers
        )
        assert resp.status_code == 404
