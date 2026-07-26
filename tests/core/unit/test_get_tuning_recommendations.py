"""Tests for GET /commands/tuning-recommendations/{controller_id}."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

import pytest
from httpx import ASGITransport, AsyncClient

from smart_pid_core.adapters.inbound.api.app import create_app
from smart_pid_core.adapters.inbound.api.auth import create_access_token, hash_password
from smart_pid_core.adapters.outbound.alarm_repo import AlarmRepository
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository
from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.adapters.outbound.user_repo import UserRepository
from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.loop_manager import LoopManager
from smart_pid_core.config import CoreSettings
from smart_pid_domain.enums import TuningRecStatus


@dataclass
class _FakeRec:
    """Tuning recommendation stub matching TuningRecommendation fields."""

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    controller_id: int = 1
    current_kp: float = 1.0
    current_ti: float = 10.0
    current_td: float = 0.5
    recommended_kp: float = 1.2
    recommended_ti: float = 9.0
    recommended_td: float = 0.6
    reason: str = "Fuzzy engine: reduce overshoot"
    timestamp: float = field(default_factory=time.time)
    status: TuningRecStatus = TuningRecStatus.PENDING


@pytest.fixture
async def deps(tmp_path):
    """Standard deps for tuning recommendation tests."""
    db_path = tmp_path / "test.spid"
    repo = SQLiteRepository(db_path)
    await repo.initialize()
    historian = SQLiteHistorian(repo.session_factory)
    user_db_path = tmp_path / "users.db"
    user_repo = UserRepository(user_db_path)
    await user_repo.initialize()
    alarm_repo = AlarmRepository(repo)
    audit_repo = AuditRepository(repo)
    bus = EventBus(url_prefix=f"inproc://test_{uuid.uuid4().hex[:8]}")
    bus.start()
    loop_manager = LoopManager(bus=bus, execution_mode="monitor")
    settings = CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        execution_mode="monitor",
    )  # type: ignore[call-arg]

    admin_hash = hash_password("admin")
    await user_repo.create("admin", admin_hash, "admin")

    yield {
        "repo": repo,
        "historian": historian,
        "user_repo": user_repo,
        "alarm_repo": alarm_repo,
        "audit_repo": audit_repo,
        "loop_manager": loop_manager,
        "settings": settings,
        "bus": bus,
    }
    loop_manager.stop_all()
    bus.stop()
    await user_repo.close()
    await repo.db.close()


def _make_app(deps_dict):
    return create_app(
        repo=deps_dict["repo"],
        historian=deps_dict["historian"],
        user_repo=deps_dict["user_repo"],
        loop_manager=deps_dict["loop_manager"],
        settings=deps_dict["settings"],
        alarm_repo=deps_dict["alarm_repo"],
        audit_repo=deps_dict["audit_repo"],
    )


def _operator_headers(settings) -> dict[str, str]:
    token = create_access_token(
        user_id=2, username="operator", role="user",
        secret=settings.jwt_secret,
    )
    return {"Authorization": f"Bearer {token}"}


class TestGetTuningRecommendation:
    """Tests for GET /commands/tuning-recommendations/{controller_id}."""

    @pytest.mark.asyncio
    async def test_returns_404_when_no_recommendation(self, deps) -> None:
        app = _make_app(deps)
        headers = _operator_headers(deps["settings"])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
            resp = await client.get(
                "/commands/tuning-recommendations/999", headers=headers,
            )
        assert resp.status_code == 404
        assert "No tuning recommendation" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_returns_recommendation_when_exists(self, deps) -> None:
        app = _make_app(deps)
        rec = _FakeRec(controller_id=1)
        app.state.tuning_recommendations = {1: rec}
        headers = _operator_headers(deps["settings"])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
            resp = await client.get(
                "/commands/tuning-recommendations/1", headers=headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["controller_id"] == 1
        assert data["current_kp"] == 1.0
        assert data["current_ti"] == 10.0
        assert data["current_td"] == 0.5
        assert data["recommended_kp"] == 1.2
        assert data["recommended_ti"] == 9.0
        assert data["recommended_td"] == 0.6
        assert data["reason"] == "Fuzzy engine: reduce overshoot"
        assert data["status"] == "pending"
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_requires_authentication(self, deps) -> None:
        app = _make_app(deps)
        app.state.tuning_recommendations = {1: _FakeRec()}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
            resp = await client.get("/commands/tuning-recommendations/1")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_operator_can_access(self, deps) -> None:
        """Operator role should be able to view tuning recommendations."""
        app = _make_app(deps)
        app.state.tuning_recommendations = {1: _FakeRec()}
        headers = _operator_headers(deps["settings"])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
            resp = await client.get(
                "/commands/tuning-recommendations/1", headers=headers,
            )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_source_field_optional(self, deps) -> None:
        """source is None when domain model lacks it (backwards compat)."""
        app = _make_app(deps)
        app.state.tuning_recommendations = {1: _FakeRec()}
        headers = _operator_headers(deps["settings"])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
            resp = await client.get(
                "/commands/tuning-recommendations/1", headers=headers,
            )
        assert resp.status_code == 200
        assert resp.json()["source"] is None

    @pytest.mark.asyncio
    async def test_empty_recommendations_dict_returns_404(self, deps) -> None:
        """Explicit empty dict in app.state still returns 404."""
        app = _make_app(deps)
        app.state.tuning_recommendations = {}
        headers = _operator_headers(deps["settings"])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
            resp = await client.get(
                "/commands/tuning-recommendations/1", headers=headers,
            )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_no_tuning_recommendations_attr_returns_404(self, deps) -> None:
        """When app.state has no tuning_recommendations at all, returns 404."""
        app = _make_app(deps)
        # Don't set tuning_recommendations on app.state at all
        headers = _operator_headers(deps["settings"])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
            resp = await client.get(
                "/commands/tuning-recommendations/1", headers=headers,
            )
        assert resp.status_code == 404
