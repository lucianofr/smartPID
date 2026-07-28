"""Tests for OPC-UA endpoint persistence and connect-with-endpoint."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient


class TestOPCUAAdapterSetEndpoint:
    """OPCUAAdapter.set_endpoint() stops adapter and updates endpoint."""

    def test_set_endpoint_updates_endpoint(self):
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        settings = MagicMock()
        settings.opcua_endpoint = "opc.tcp://old:4840"
        settings.opcua_timeout_s = 5.0
        settings.opcua_retry_max_s = 60.0
        adapter = OPCUAAdapter(settings)

        assert adapter.endpoint == "opc.tcp://old:4840"

        adapter.set_endpoint("opc.tcp://new:4840")

        assert adapter.endpoint == "opc.tcp://new:4840"

    def test_set_endpoint_stops_adapter(self):
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter
        from smart_pid_domain.enums import ConnectionState

        settings = MagicMock()
        settings.opcua_endpoint = "opc.tcp://old:4840"
        settings.opcua_timeout_s = 5.0
        settings.opcua_retry_max_s = 60.0
        adapter = OPCUAAdapter(settings)

        adapter.set_endpoint("opc.tcp://new:4840")

        assert adapter.state == ConnectionState.OFFLINE


def _make_test_app():
    """Create a minimal FastAPI app with the opcua router for testing."""
    from fastapi import FastAPI

    from smart_pid_core.adapters.inbound.api.routers.opcua import router

    app = FastAPI()
    app.include_router(router, prefix="/opcua")
    return app


def _mock_admin_user():
    """Override auth dependency to return admin claims."""
    from smart_pid_core.adapters.inbound.api.dependencies import (
        require_admin,
    )
    from smart_pid_domain.dtos.auth import UserClaims

    admin = UserClaims(user_id="1", username="admin", role="admin")

    def override():
        return admin

    return require_admin, override


class TestPutOPCUAEndpoint:
    """PUT /opcua/endpoint saves endpoint to metadata and configures adapter."""

    def test_save_endpoint_returns_status(self):
        from smart_pid_core.adapters.inbound.api.dependencies import (
            get_opcua_adapter,
            get_repo,
        )
        from smart_pid_domain.enums import ConnectionState

        app = _make_test_app()
        dep_key, dep_override = _mock_admin_user()
        app.dependency_overrides[dep_key] = dep_override

        mock_adapter = MagicMock()
        mock_adapter.state = ConnectionState.OFFLINE
        mock_adapter.endpoint = "opc.tcp://10.0.0.1:4840"
        app.dependency_overrides[get_opcua_adapter] = lambda: mock_adapter

        mock_repo = MagicMock()
        mock_repo.set_meta = AsyncMock()
        app.dependency_overrides[get_repo] = lambda: mock_repo

        client = TestClient(app)
        resp = client.put(
            "/opcua/endpoint",
            json={"endpoint": "opc.tcp://10.0.0.1:4840"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["endpoint"] == "opc.tcp://10.0.0.1:4840"
        assert data["state"] == "OFFLINE"
        mock_repo.set_meta.assert_awaited_once_with(
            "opcua_endpoint", "opc.tcp://10.0.0.1:4840",
        )
        mock_adapter.set_endpoint.assert_called_once_with("opc.tcp://10.0.0.1:4840")

    def test_save_endpoint_rejects_invalid_url(self):
        from smart_pid_core.adapters.inbound.api.dependencies import (
            get_opcua_adapter,
            get_repo,
        )

        app = _make_test_app()
        dep_key, dep_override = _mock_admin_user()
        app.dependency_overrides[dep_key] = dep_override

        mock_adapter = MagicMock()
        app.dependency_overrides[get_opcua_adapter] = lambda: mock_adapter

        mock_repo = MagicMock()
        app.dependency_overrides[get_repo] = lambda: mock_repo

        client = TestClient(app)
        resp = client.put(
            "/opcua/endpoint",
            json={"endpoint": "http://wrong:4840"},
        )

        assert resp.status_code == 422


class TestPostOPCUAConnectWithEndpoint:
    """POST /opcua/connect accepts optional endpoint body."""

    def test_connect_with_endpoint_configures_adapter(self):
        from smart_pid_core.adapters.inbound.api.dependencies import get_opcua_adapter
        from smart_pid_domain.enums import ConnectionState

        app = _make_test_app()
        dep_key, dep_override = _mock_admin_user()
        app.dependency_overrides[dep_key] = dep_override

        mock_adapter = MagicMock()
        mock_adapter.state = ConnectionState.ONLINE
        mock_adapter.endpoint = "opc.tcp://10.0.0.1:4840"
        mock_adapter.wait_connected.return_value = True
        app.dependency_overrides[get_opcua_adapter] = lambda: mock_adapter

        client = TestClient(app)
        resp = client.post(
            "/opcua/connect",
            json={"endpoint": "opc.tcp://10.0.0.1:4840"},
        )

        assert resp.status_code == 200
        mock_adapter.set_endpoint.assert_called_once_with("opc.tcp://10.0.0.1:4840")

    def test_connect_without_endpoint_does_not_reconfigure(self):
        from smart_pid_core.adapters.inbound.api.dependencies import get_opcua_adapter
        from smart_pid_domain.enums import ConnectionState

        app = _make_test_app()
        dep_key, dep_override = _mock_admin_user()
        app.dependency_overrides[dep_key] = dep_override

        mock_adapter = MagicMock()
        mock_adapter.state = ConnectionState.ONLINE
        mock_adapter.endpoint = "opc.tcp://localhost:4840"
        mock_adapter.wait_connected.return_value = True
        app.dependency_overrides[get_opcua_adapter] = lambda: mock_adapter

        client = TestClient(app)
        resp = client.post("/opcua/connect")

        assert resp.status_code == 200
        mock_adapter.set_endpoint.assert_not_called()


class TestProjectServiceOPCUA:
    """ProjectService auto-connects OPC-UA on open_project, stops on new_project."""

    @pytest.fixture
    def mock_repo(self, tmp_path):
        repo = MagicMock()
        repo._db_path = tmp_path / "test.spid"
        repo.reopen = AsyncMock()
        repo.set_meta = AsyncMock()
        repo.get_meta = AsyncMock(return_value="opc.tcp://saved:4840")
        repo.list_all = AsyncMock(return_value=[])
        repo.list_sim_configs = AsyncMock(return_value=[])
        return repo

    @pytest.fixture
    def mock_loop_manager(self):
        lm = MagicMock()
        lm.stop_all = MagicMock()
        return lm

    @pytest.fixture
    def mock_opcua_adapter(self):
        adapter = MagicMock()
        adapter.endpoint = "opc.tcp://old:4840"
        adapter.set_endpoint = MagicMock()
        adapter.start = MagicMock()
        adapter.stop = MagicMock()
        return adapter

    def test_open_project_auto_connects_with_saved_endpoint(
        self, tmp_path, mock_repo, mock_loop_manager, mock_opcua_adapter,
    ):
        from smart_pid_core.application.project_service import ProjectService

        spid_path = tmp_path / "projects" / "myproj.spid"
        spid_path.parent.mkdir(parents=True, exist_ok=True)
        spid_path.touch()

        service = ProjectService(
            repo=mock_repo,
            loop_manager=mock_loop_manager,
            projects_dir=tmp_path / "projects",
            simulator_adapter=None,
            daemon_state=None,
            opcua_adapter=mock_opcua_adapter,
        )

        asyncio.run(service.open_project("myproj"))

        mock_repo.get_meta.assert_any_await("opcua_endpoint")
        mock_opcua_adapter.set_endpoint.assert_called_once_with("opc.tcp://saved:4840")
        mock_opcua_adapter.start.assert_called()

    def test_open_project_no_endpoint_stops_adapter(
        self, tmp_path, mock_repo, mock_loop_manager, mock_opcua_adapter,
    ):
        from smart_pid_core.application.project_service import ProjectService

        mock_repo.get_meta = AsyncMock(return_value=None)

        spid_path = tmp_path / "projects" / "myproj.spid"
        spid_path.parent.mkdir(parents=True, exist_ok=True)
        spid_path.touch()

        service = ProjectService(
            repo=mock_repo,
            loop_manager=mock_loop_manager,
            projects_dir=tmp_path / "projects",
            simulator_adapter=None,
            daemon_state=None,
            opcua_adapter=mock_opcua_adapter,
        )

        asyncio.run(service.open_project("myproj"))

        mock_opcua_adapter.stop.assert_called()
        mock_opcua_adapter.set_endpoint.assert_not_called()

    def test_new_project_stops_opcua_adapter(
        self, tmp_path, mock_repo, mock_loop_manager, mock_opcua_adapter,
    ):
        from smart_pid_core.application.project_service import ProjectService

        service = ProjectService(
            repo=mock_repo,
            loop_manager=mock_loop_manager,
            projects_dir=tmp_path / "projects",
            simulator_adapter=None,
            daemon_state=None,
            opcua_adapter=mock_opcua_adapter,
        )
        (tmp_path / "projects").mkdir(parents=True, exist_ok=True)

        asyncio.run(service.new_project("newproj"))

        mock_opcua_adapter.stop.assert_called()
