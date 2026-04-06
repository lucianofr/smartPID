"""Integration tests for auto-excitation endpoints."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from smart_pid_core.adapters.inbound.api.app import create_app
from smart_pid_core.adapters.inbound.api.auth import create_access_token
from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter
from smart_pid_core.config import CoreSettings


def _make_settings() -> CoreSettings:
    return CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        simulator_enabled=True,
    )  # type: ignore[call-arg]


def _mock_opcua() -> MagicMock:
    m = MagicMock()
    m.register_controller.return_value = {}
    return m


@pytest.fixture
def client():
    settings = _make_settings()
    with patch(
        "smart_pid_core.adapters.inbound.simulator_adapter.OPCUAServer",
        return_value=_mock_opcua(),
    ):
        adapter = SimulatorAdapter(settings=settings)
        adapter.register_controller(1)

    app = create_app(
        repo=MagicMock(),
        historian=MagicMock(),
        user_repo=MagicMock(),
        loop_manager=MagicMock(),
        settings=settings,
        simulator_adapter=adapter,
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
    with TestClient(app) as c:
        yield c, adapter, headers


class TestAutoSPEndpoint:
    def test_put_auto_sp_returns_200(self, client):
        c, _, headers = client
        resp = c.put(
            "/simulator/1/auto-sp",
            json={"enabled": True, "sp_min_pct": 25.0, "sp_max_pct": 75.0},
            headers=headers,
        )
        assert resp.status_code == 200

    def test_put_auto_sp_updates_adapter(self, client):
        c, adapter, headers = client
        c.put(
            "/simulator/1/auto-sp",
            json={"enabled": True, "sp_min_pct": 10.0, "sp_max_pct": 90.0},
            headers=headers,
        )
        status = adapter.get_controller_status(1)
        assert status.auto_sp.enabled is True
        assert status.auto_sp.sp_min_pct == 10.0

    def test_put_auto_sp_404_unknown_controller(self, client):
        c, _, headers = client
        resp = c.put("/simulator/999/auto-sp", json={"enabled": True}, headers=headers)
        assert resp.status_code == 404


class TestAutoDisturbanceEndpoint:
    def test_put_auto_dist_returns_200(self, client):
        c, _, headers = client
        resp = c.put(
            "/simulator/1/auto-disturbance",
            json={"enabled": True, "max_amplitude_pct": 20.0},
            headers=headers,
        )
        assert resp.status_code == 200

    def test_put_auto_dist_updates_adapter(self, client):
        c, adapter, headers = client
        c.put(
            "/simulator/1/auto-disturbance",
            json={"enabled": True, "max_amplitude_pct": 30.0},
            headers=headers,
        )
        status = adapter.get_controller_status(1)
        assert status.auto_disturbance.enabled is True
        assert status.auto_disturbance.max_amplitude_pct == 30.0

    def test_put_auto_dist_404_unknown_controller(self, client):
        c, _, headers = client
        resp = c.put(
            "/simulator/999/auto-disturbance", json={"enabled": True}, headers=headers
        )
        assert resp.status_code == 404
