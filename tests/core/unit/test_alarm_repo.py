# tests/core/unit/test_alarm_repo.py
"""Tests for AlarmRepository — CRUD on Log_Alarmes."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
import pytest_asyncio

from smart_pid_core.adapters.outbound.alarm_repo import AlarmRepository
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_domain.enums import AlarmPriority, AlarmType


@pytest_asyncio.fixture
async def alarm_repo(tmp_path):
    repo = SQLiteRepository(tmp_path / "test.db")
    await repo.initialize()
    alarm_repo = AlarmRepository(repo)
    yield alarm_repo


@pytest.mark.asyncio
async def test_insert_alarm(alarm_repo: AlarmRepository):
    alarm_id = await alarm_repo.insert_alarm(
        controller_id=1,
        alarm_type=AlarmType.HIHI,
        priority=AlarmPriority.CRITICAL,
        value=95.0,
        limit_value=90.0,
        triggered_at=datetime.now(tz=UTC),
    )
    assert alarm_id > 0


@pytest.mark.asyncio
async def test_get_active(alarm_repo: AlarmRepository):
    now = datetime.now(tz=UTC)
    await alarm_repo.insert_alarm(1, AlarmType.HIHI, AlarmPriority.CRITICAL, 95.0, 90.0, now)
    await alarm_repo.insert_alarm(1, AlarmType.HI, AlarmPriority.WARNING, 85.0, 80.0, now)
    active = await alarm_repo.get_active()
    assert len(active) == 2


@pytest.mark.asyncio
async def test_mark_cleared(alarm_repo: AlarmRepository):
    now = datetime.now(tz=UTC)
    await alarm_repo.insert_alarm(1, AlarmType.HIHI, AlarmPriority.CRITICAL, 95.0, 90.0, now)
    await alarm_repo.mark_cleared(1, AlarmType.HIHI, now)
    active = await alarm_repo.get_active()
    assert len(active) == 1
    assert active[0]["cleared_at"] is not None


@pytest.mark.asyncio
async def test_acknowledge(alarm_repo: AlarmRepository):
    now = datetime.now(tz=UTC)
    alarm_id = await alarm_repo.insert_alarm(
        1, AlarmType.HIHI, AlarmPriority.CRITICAL, 95.0, 90.0, now
    )
    await alarm_repo.acknowledge(alarm_id, "operator1", now)
    active = await alarm_repo.get_active()
    assert len(active) == 1
    assert active[0]["acknowledged"] == 1
    assert active[0]["ack_by_user"] == "operator1"


@pytest.mark.asyncio
async def test_cleared_and_acked_removed_from_active(alarm_repo: AlarmRepository):
    now = datetime.now(tz=UTC)
    alarm_id = await alarm_repo.insert_alarm(
        1, AlarmType.HIHI, AlarmPriority.CRITICAL, 95.0, 90.0, now
    )
    await alarm_repo.mark_cleared(1, AlarmType.HIHI, now)
    await alarm_repo.acknowledge(alarm_id, "operator1", now)
    active = await alarm_repo.get_active()
    assert len(active) == 0


@pytest.mark.asyncio
async def test_acknowledge_all(alarm_repo: AlarmRepository):
    now = datetime.now(tz=UTC)
    await alarm_repo.insert_alarm(1, AlarmType.HIHI, AlarmPriority.CRITICAL, 95.0, 90.0, now)
    await alarm_repo.insert_alarm(1, AlarmType.HI, AlarmPriority.WARNING, 85.0, 80.0, now)
    result = await alarm_repo.acknowledge_all("admin", now)
    assert result["acknowledged_count"] == 2


@pytest.mark.asyncio
async def test_get_history(alarm_repo: AlarmRepository):
    now = datetime.now(tz=UTC)
    await alarm_repo.insert_alarm(1, AlarmType.HIHI, AlarmPriority.CRITICAL, 95.0, 90.0, now)
    from datetime import timedelta

    history = await alarm_repo.get_history(
        start=now - timedelta(hours=1),
        end=now + timedelta(hours=1),
    )
    assert len(history) == 1


@pytest.mark.asyncio
async def test_acknowledge_returns_alarm_details(alarm_repo: AlarmRepository):
    """acknowledge() must return dict with controller_id, alarm_type, priority."""
    aid = await alarm_repo.insert_alarm(
        controller_id=1,
        alarm_type=AlarmType.HI,
        priority=AlarmPriority.WARNING,
        value=85.0,
        limit_value=80.0,
        triggered_at=datetime.now(tz=UTC),
    )
    result = await alarm_repo.acknowledge(aid, "operator1", datetime.now(tz=UTC))
    assert result["id"] == aid
    assert result["controller_id"] == 1
    assert result["alarm_type"] == "HI"
    assert result["priority"] == "WARNING"
    assert result["acknowledged"] is True


@pytest.mark.asyncio
async def test_acknowledge_all_returns_controller_ids(alarm_repo: AlarmRepository):
    """acknowledge_all() must return count and affected controller_ids."""
    now = datetime.now(tz=UTC)
    await alarm_repo.insert_alarm(1, AlarmType.HI, AlarmPriority.WARNING, 85.0, 80.0, now)
    await alarm_repo.insert_alarm(2, AlarmType.HIHI, AlarmPriority.CRITICAL, 95.0, 90.0, now)
    await alarm_repo.insert_alarm(1, AlarmType.LO, AlarmPriority.WARNING, 10.0, 15.0, now)

    result = await alarm_repo.acknowledge_all("operator1", now)
    assert result["acknowledged_count"] == 3
    assert set(result["controller_ids"]) == {1, 2}


@pytest.mark.asyncio
async def test_get_active_filter_by_controller(alarm_repo: AlarmRepository):
    now = datetime.now(tz=UTC)
    await alarm_repo.insert_alarm(1, AlarmType.HIHI, AlarmPriority.CRITICAL, 95.0, 90.0, now)
    await alarm_repo.insert_alarm(2, AlarmType.HI, AlarmPriority.WARNING, 85.0, 80.0, now)
    active = await alarm_repo.get_active(controller_id=1)
    assert len(active) == 1
    assert active[0]["controller_id"] == 1
