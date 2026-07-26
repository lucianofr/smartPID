"""Integration tests for audit trail endpoint."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest_asyncio
from fastapi.testclient import TestClient

from smart_pid_core.adapters.inbound.api.app import create_app
from smart_pid_core.adapters.inbound.api.auth import create_access_token
from smart_pid_core.adapters.outbound.alarm_repo import AlarmRepository
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository
from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.adapters.outbound.user_repo import UserRepository
from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.loop_manager import LoopManager
from smart_pid_core.config import CoreSettings
from smart_pid_domain.enums import AuditAction


@pytest_asyncio.fixture
async def app_fixture(tmp_path):
    repo = SQLiteRepository(tmp_path / "test.db")
    await repo.initialize()
    historian = SQLiteHistorian(repo.session_factory)
    user_db_path = tmp_path / "users.db"
    user_repo = UserRepository(user_db_path)
    await user_repo.initialize()
    alarm_repo = AlarmRepository(repo.session_factory)
    audit_repo = AuditRepository(repo.session_factory)
    bus = EventBus()
    bus.start()
    loop_manager = LoopManager(bus=bus)
    settings = CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        db_path=tmp_path / "test.db",
    )
    app = create_app(
        repo=repo, historian=historian, user_repo=user_repo,
        loop_manager=loop_manager, settings=settings,
        alarm_repo=alarm_repo, audit_repo=audit_repo,
    )
    yield app, audit_repo, settings
    await user_repo.close()
    bus.stop()


def test_get_audit_supervisor(app_fixture):
    import asyncio
    app, audit_repo, settings = app_fixture
    asyncio.get_event_loop().run_until_complete(
        audit_repo.record(1, "admin", AuditAction.LOGIN, None, None)
    )
    client = TestClient(app, base_url="http://127.0.0.1")
    token = create_access_token(
        user_id=1, username="sup1", role="admin",
        secret=settings.jwt_secret, expiry_hours=1,
    )
    now = datetime.now(tz=UTC)
    resp = client.get(
        "/audit",
        params={
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": (now + timedelta(hours=1)).isoformat(),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_get_audit_any_authenticated_user_allowed(app_fixture):
    # Single-admin deployment: any authenticated user may read the audit trail.
    app, audit_repo, settings = app_fixture
    client = TestClient(app, base_url="http://127.0.0.1")
    token = create_access_token(
        user_id=1, username="op1", role="user",
        secret=settings.jwt_secret, expiry_hours=1,
    )
    now = datetime.now(tz=UTC)
    resp = client.get(
        "/audit",
        params={
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": (now + timedelta(hours=1)).isoformat(),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


def test_get_audit_requires_auth(app_fixture):
    app, _audit_repo, _settings = app_fixture
    client = TestClient(app, base_url="http://127.0.0.1")
    now = datetime.now(tz=UTC)
    resp = client.get(
        "/audit",
        params={
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": (now + timedelta(hours=1)).isoformat(),
        },
    )
    assert resp.status_code == 401
