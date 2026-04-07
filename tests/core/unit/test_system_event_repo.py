"""Tests for SystemEventRepository."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import aiosqlite
import pytest
import pytest_asyncio

from smart_pid_core.adapters.outbound.system_event_repo import SystemEventRepository


@pytest_asyncio.fixture
async def db():
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.executescript("""
        CREATE TABLE Log_System_Events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL DEFAULT (datetime('now')),
            source TEXT NOT NULL,
            severity TEXT NOT NULL CHECK(severity IN ('CRITICAL','WARNING','INFO')),
            message TEXT NOT NULL
        );
        CREATE INDEX idx_sysevents_timestamp ON Log_System_Events(timestamp);
        CREATE INDEX idx_sysevents_severity ON Log_System_Events(severity);
    """)
    yield conn
    await conn.close()


@pytest_asyncio.fixture
async def repo(db):
    return SystemEventRepository(db)


@pytest.mark.asyncio
async def test_insert_event(repo):
    eid = await repo.insert_event("BACKEND", "INFO", "Backend started")
    assert eid > 0


@pytest.mark.asyncio
async def test_get_history_empty(repo):
    now = datetime.now(tz=UTC)
    result = await repo.get_history(start=now - timedelta(hours=1), end=now)
    assert result == []


@pytest.mark.asyncio
async def test_get_history_with_events(repo):
    await repo.insert_event("BACKEND", "INFO", "Backend started")
    await repo.insert_event("OPCUA", "WARNING", "Connection lost")
    now = datetime.now(tz=UTC)
    result = await repo.get_history(
        start=now - timedelta(hours=1), end=now + timedelta(hours=1),
    )
    assert len(result) == 2


@pytest.mark.asyncio
async def test_get_history_filter_by_source(repo):
    await repo.insert_event("BACKEND", "INFO", "Started")
    await repo.insert_event("OPCUA", "WARNING", "Lost")
    now = datetime.now(tz=UTC)
    result = await repo.get_history(
        start=now - timedelta(hours=1), end=now + timedelta(hours=1),
        source="OPCUA",
    )
    assert len(result) == 1
    assert result[0]["source"] == "OPCUA"


@pytest.mark.asyncio
async def test_get_history_filter_by_severity(repo):
    await repo.insert_event("BACKEND", "INFO", "Started")
    await repo.insert_event("WORKER", "CRITICAL", "Crash")
    now = datetime.now(tz=UTC)
    result = await repo.get_history(
        start=now - timedelta(hours=1), end=now + timedelta(hours=1),
        severity="CRITICAL",
    )
    assert len(result) == 1
    assert result[0]["severity"] == "CRITICAL"


@pytest.mark.asyncio
async def test_get_history_pagination(repo):
    for i in range(10):
        await repo.insert_event("BACKEND", "INFO", f"Event {i}")
    now = datetime.now(tz=UTC)
    page1 = await repo.get_history(
        start=now - timedelta(hours=1), end=now + timedelta(hours=1),
        limit=3, offset=0,
    )
    assert len(page1) == 3
    page2 = await repo.get_history(
        start=now - timedelta(hours=1), end=now + timedelta(hours=1),
        limit=3, offset=3,
    )
    assert len(page2) == 3
    assert page1[0]["id"] != page2[0]["id"]
