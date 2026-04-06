"""Tests for AlarmWorker — verifies alarms are persisted to database."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from smart_pid_core.application.workers.alarm_worker import AlarmWorker
from smart_pid_domain.enums import AlarmPriority, AlarmType
from smart_pid_domain.models.alarm_config import AlarmTransition


@pytest.fixture
def mock_bus():
    bus = MagicMock()
    sub = MagicMock()
    pub = MagicMock()
    sub.recv.return_value = None
    bus.create_subscriber.return_value = sub
    bus.create_publisher.return_value = pub
    return bus


@pytest.fixture
def mock_alarm_repo():
    repo = AsyncMock()
    repo.insert_alarm.return_value = 1
    repo.mark_cleared.return_value = None
    return repo


class TestPersistAlarm:
    """Test _persist_alarm directly to verify DB integration."""

    @pytest.mark.asyncio
    async def test_triggered_alarm_calls_insert(self, mock_bus, mock_alarm_repo):
        worker = AlarmWorker(
            bus=mock_bus,
            alarm_configs={},
            alarm_repo=mock_alarm_repo,
        )
        now = datetime.now(tz=UTC)
        transition = AlarmTransition(
            controller_id=1,
            alarm_type=AlarmType.HIHI,
            priority=AlarmPriority.CRITICAL,
            transition="TRIGGERED",
            value=95.0,
            limit=90.0,
            timestamp=now,
        )

        await worker._persist_alarm(transition)

        mock_alarm_repo.insert_alarm.assert_awaited_once_with(
            controller_id=1,
            alarm_type=AlarmType.HIHI,
            priority=AlarmPriority.CRITICAL,
            value=95.0,
            limit_value=90.0,
            triggered_at=now,
        )

    @pytest.mark.asyncio
    async def test_cleared_alarm_calls_mark_cleared(self, mock_bus, mock_alarm_repo):
        worker = AlarmWorker(
            bus=mock_bus,
            alarm_configs={},
            alarm_repo=mock_alarm_repo,
        )
        now = datetime.now(tz=UTC)
        transition = AlarmTransition(
            controller_id=1,
            alarm_type=AlarmType.HIHI,
            priority=AlarmPriority.CRITICAL,
            transition="CLEARED",
            value=85.0,
            limit=90.0,
            timestamp=now,
        )

        await worker._persist_alarm(transition)

        mock_alarm_repo.mark_cleared.assert_awaited_once_with(
            controller_id=1,
            alarm_type=AlarmType.HIHI,
            cleared_at=now,
        )
        mock_alarm_repo.insert_alarm.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_persist_without_repo_is_noop(self, mock_bus):
        worker = AlarmWorker(
            bus=mock_bus,
            alarm_configs={},
            alarm_repo=None,
        )
        now = datetime.now(tz=UTC)
        transition = AlarmTransition(
            controller_id=1,
            alarm_type=AlarmType.HIHI,
            priority=AlarmPriority.CRITICAL,
            transition="TRIGGERED",
            value=95.0,
            limit=90.0,
            timestamp=now,
        )

        # Should not raise
        await worker._persist_alarm(transition)

    @pytest.mark.asyncio
    async def test_persist_exception_does_not_propagate(self, mock_bus, mock_alarm_repo):
        mock_alarm_repo.insert_alarm.side_effect = RuntimeError("DB write failed")
        worker = AlarmWorker(
            bus=mock_bus,
            alarm_configs={},
            alarm_repo=mock_alarm_repo,
        )
        now = datetime.now(tz=UTC)
        transition = AlarmTransition(
            controller_id=1,
            alarm_type=AlarmType.HIHI,
            priority=AlarmPriority.CRITICAL,
            transition="TRIGGERED",
            value=95.0,
            limit=90.0,
            timestamp=now,
        )

        # Should not raise — error is logged, not propagated
        await worker._persist_alarm(transition)


class TestAlarmWorkerIntegration:
    """Integration test: AlarmWorker persists alarms to real SQLite."""

    @pytest.mark.asyncio
    async def test_alarm_persisted_to_sqlite(self, tmp_path):
        from smart_pid_core.adapters.outbound.alarm_repo import AlarmRepository
        from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository

        repo = SQLiteRepository(tmp_path / "test.db")
        await repo.initialize()
        alarm_repo = AlarmRepository(repo)

        mock_bus = MagicMock()
        mock_bus.create_subscriber.return_value = MagicMock()
        mock_bus.create_publisher.return_value = MagicMock()

        worker = AlarmWorker(
            bus=mock_bus,
            alarm_configs={},
            alarm_repo=alarm_repo,
        )

        now = datetime.now(tz=UTC)
        triggered = AlarmTransition(
            controller_id=1,
            alarm_type=AlarmType.HIHI,
            priority=AlarmPriority.CRITICAL,
            transition="TRIGGERED",
            value=95.0,
            limit=90.0,
            timestamp=now,
        )

        await worker._persist_alarm(triggered)

        active = await alarm_repo.get_active(controller_id=1)
        assert len(active) == 1
        assert active[0]["alarm_type"] == "HIHI"
        assert active[0]["priority"] == "CRITICAL"
        assert active[0]["value"] == 95.0

        # Now clear it
        cleared = AlarmTransition(
            controller_id=1,
            alarm_type=AlarmType.HIHI,
            priority=AlarmPriority.CRITICAL,
            transition="CLEARED",
            value=85.0,
            limit=90.0,
            timestamp=now,
        )

        await worker._persist_alarm(cleared)

        active = await alarm_repo.get_active(controller_id=1)
        assert len(active) == 1
        assert active[0]["cleared_at"] is not None

        await repo.db.close()
