"""Integration tests for OPC-UA REST API."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import httpx
import pytest

from smart_pid_core.adapters.inbound.api.app import create_app
from smart_pid_core.adapters.inbound.api.auth import create_access_token, hash_password
from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.adapters.outbound.user_repo import UserRepository
from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.loop_manager import LoopManager
from smart_pid_core.config import CoreSettings
from smart_pid_domain.enums import ConnectionState


@pytest.fixture
def mock_opcua_adapter():
    adapter = MagicMock()
    adapter.state = ConnectionState.ONLINE
    adapter.endpoint = "opc.tcp://localhost:4840"
    adapter.browse_children.return_value = [
        {"node_id": "ns=2;i=1", "display_name": "PV", "node_class": "Variable"},
        {"node_id": "ns=2;i=2", "display_name": "SP", "node_class": "Variable"},
    ]
    adapter.search.return_value = [
        {"node_id": "ns=2;i=1", "display_name": "PV", "node_class": "Variable"},
    ]
    return adapter


@pytest.fixture
async def opcua_api_deps(tmp_path, mock_opcua_adapter):
    db_path = tmp_path / "test.spid"
    repo = SQLiteRepository(db_path)
    await repo.initialize()
    historian = SQLiteHistorian(repo)
    user_db_path = tmp_path / "users.db"
    user_repo = UserRepository(user_db_path)
    await user_repo.initialize()
    bus = EventBus(url_prefix=f"inproc://test_{uuid.uuid4().hex[:8]}")
    bus.start()
    loop_manager = LoopManager(bus=bus)
    settings = CoreSettings(jwt_secret="test-secret-key-minimum-32-bytes!")  # type: ignore[call-arg]

    admin_hash = hash_password("admin")
    await user_repo.create("admin", admin_hash, "admin")

    app = create_app(
        repo=repo,
        historian=historian,
        user_repo=user_repo,
        loop_manager=loop_manager,
        settings=settings,
        opcua_adapter=mock_opcua_adapter,
    )
    token = create_access_token(
        user_id=1, username="admin", role="admin", secret=settings.jwt_secret,
    )
    headers = {"Authorization": f"Bearer {token}"}

    yield app, headers, mock_opcua_adapter
    loop_manager.stop_all()
    bus.stop()
    await user_repo.close()
    await repo.db.close()


@pytest.fixture
async def opcua_client(opcua_api_deps):
    app, headers, _ = opcua_api_deps
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as c:
        yield c, headers


class TestOPCUAAPI:
    @pytest.mark.asyncio
    async def test_get_status(self, opcua_client):
        client, headers = opcua_client
        resp = await client.get("/opcua/status", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "ONLINE"
        assert data["endpoint"] == "opc.tcp://localhost:4840"

    @pytest.mark.asyncio
    async def test_browse_children(self, opcua_client):
        client, headers = opcua_client
        resp = await client.get("/opcua/browse/i=85", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["parent_node_id"] == "i=85"
        assert len(data["children"]) == 2

    @pytest.mark.asyncio
    async def test_search(self, opcua_client):
        client, headers = opcua_client
        resp = await client.get("/opcua/search", params={"q": "PV"}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "PV"
        assert len(data["results"]) == 1
