"""Integration tests for Stats REST API."""
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


@pytest.fixture
def mock_stats_worker():
    w = MagicMock()
    w.get_current_stats.return_value = {
        "controller_id": 1, "iae": 5.0, "itae": 10.0, "ise": 25.0,
        "mse": 12.5, "std_dev": 2.0, "total_variation": 3.0,
        "variability_sp": 0.08, "variability_range": 0.04, "sample_count": 100,
    }
    return w


@pytest.fixture
async def stats_client(tmp_path, mock_stats_worker):
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
    settings = CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",  # type: ignore[call-arg]
    )
    admin_hash = hash_password("admin")
    await user_repo.create("admin", admin_hash, "admin")

    app = create_app(
        repo=repo, historian=historian, user_repo=user_repo,
        loop_manager=loop_manager, settings=settings,
        stats_workers={1: mock_stats_worker},
    )
    token = create_access_token(
        user_id=1, username="admin", role="admin", secret=settings.jwt_secret,
    )
    headers = {"Authorization": f"Bearer {token}"}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as c:
        yield c, headers
    loop_manager.stop_all()
    bus.stop()
    await user_repo.close()


class TestStatsAPI:
    @pytest.mark.asyncio
    async def test_get_stats(self, stats_client):
        client, headers = stats_client
        resp = await client.get("/controllers/1/stats", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["iae"] == 5.0
        assert data["sample_count"] == 100

    @pytest.mark.asyncio
    async def test_get_stats_unknown_controller(self, stats_client):
        client, headers = stats_client
        resp = await client.get("/controllers/999/stats", headers=headers)
        assert resp.status_code == 404
