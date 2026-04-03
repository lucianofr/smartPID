"""Tests for AuditRepository — CRUD on Log_Auditoria."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio

from smart_pid_core.adapters.outbound.audit_repo import AuditRepository
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_domain.enums import AuditAction


@pytest_asyncio.fixture
async def audit_repo(tmp_path):
    repo = SQLiteRepository(tmp_path / "test.db")
    await repo.initialize()
    audit_repo = AuditRepository(repo.db)
    yield audit_repo


@pytest.mark.asyncio
async def test_record_audit(audit_repo: AuditRepository):
    await audit_repo.record(
        user_id=1,
        username="admin",
        action=AuditAction.LOGIN,
        resource=None,
        detail=None,
    )
    now = datetime.now(tz=UTC)
    history = await audit_repo.get_history(
        start=now - timedelta(hours=1),
        end=now + timedelta(hours=1),
    )
    assert len(history) == 1
    assert history[0]["action"] == "LOGIN"
    assert history[0]["username"] == "admin"


@pytest.mark.asyncio
async def test_record_with_detail(audit_repo: AuditRepository):
    await audit_repo.record(
        user_id=1,
        username="admin",
        action=AuditAction.SP_CHANGE,
        resource="controller:1",
        detail='{"old": 50.0, "new": 60.0}',
    )
    now = datetime.now(tz=UTC)
    history = await audit_repo.get_history(
        start=now - timedelta(hours=1), end=now + timedelta(hours=1)
    )
    assert history[0]["resource"] == "controller:1"
    assert "old" in history[0]["detail"]


@pytest.mark.asyncio
async def test_filter_by_action(audit_repo: AuditRepository):
    await audit_repo.record(1, "admin", AuditAction.LOGIN, None, None)
    await audit_repo.record(1, "admin", AuditAction.SP_CHANGE, "controller:1", None)
    now = datetime.now(tz=UTC)
    history = await audit_repo.get_history(
        start=now - timedelta(hours=1),
        end=now + timedelta(hours=1),
        action=AuditAction.LOGIN,
    )
    assert len(history) == 1
    assert history[0]["action"] == "LOGIN"


@pytest.mark.asyncio
async def test_filter_by_user(audit_repo: AuditRepository):
    await audit_repo.record(1, "admin", AuditAction.LOGIN, None, None)
    await audit_repo.record(2, "operator1", AuditAction.LOGIN, None, None)
    now = datetime.now(tz=UTC)
    history = await audit_repo.get_history(
        start=now - timedelta(hours=1),
        end=now + timedelta(hours=1),
        user_id=2,
    )
    assert len(history) == 1
    assert history[0]["username"] == "operator1"


@pytest.mark.asyncio
async def test_pagination(audit_repo: AuditRepository):
    for i in range(5):
        await audit_repo.record(1, "admin", AuditAction.LOGIN, None, f"entry-{i}")
    now = datetime.now(tz=UTC)
    page = await audit_repo.get_history(
        start=now - timedelta(hours=1),
        end=now + timedelta(hours=1),
        limit=2,
        offset=0,
    )
    assert len(page) == 2
