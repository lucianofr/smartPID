from __future__ import annotations
from datetime import datetime, timedelta, timezone
import pytest
from smart_pid_domain.enums import SignalStatus
from smart_pid_domain.models.telemetry import TelemetryFrame
from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository


@pytest.fixture
async def historian(tmp_path):
    db_path = tmp_path / "test.spid"
    repo = SQLiteRepository(db_path)
    await repo.initialize()
    return SQLiteHistorian(repo.db)


def _make_frame(controller_id: int, pv: float, ts: datetime) -> TelemetryFrame:
    return TelemetryFrame(
        controller_id=controller_id, pv=pv, sp=50.0, co=25.0,
        integral_val=1.0, timestamp=ts, status=SignalStatus.GOOD,
    )


class TestSQLiteHistorian:
    @pytest.mark.asyncio
    async def test_write_batch_and_query(self, historian) -> None:
        now = datetime.now(tz=timezone.utc)
        frames = [_make_frame(1, pv=50.0 + i, ts=now + timedelta(seconds=i)) for i in range(10)]
        await historian.write_batch(frames)
        result = await historian.query(1, now - timedelta(seconds=1), now + timedelta(seconds=20))
        assert len(result) == 10
        assert result[0].pv == 50.0
        assert result[9].pv == 59.0

    @pytest.mark.asyncio
    async def test_query_filters_by_controller(self, historian) -> None:
        now = datetime.now(tz=timezone.utc)
        frames = [_make_frame(1, pv=10.0, ts=now), _make_frame(2, pv=20.0, ts=now)]
        await historian.write_batch(frames)
        result = await historian.query(1, now - timedelta(seconds=1), now + timedelta(seconds=1))
        assert len(result) == 1
        assert result[0].controller_id == 1

    @pytest.mark.asyncio
    async def test_query_filters_by_time_range(self, historian) -> None:
        now = datetime.now(tz=timezone.utc)
        frames = [
            _make_frame(1, pv=10.0, ts=now - timedelta(hours=2)),
            _make_frame(1, pv=20.0, ts=now),
        ]
        await historian.write_batch(frames)
        result = await historian.query(1, now - timedelta(hours=1), now + timedelta(hours=1))
        assert len(result) == 1
        assert result[0].pv == 20.0

    @pytest.mark.asyncio
    async def test_cleanup_removes_old_data(self, historian) -> None:
        now = datetime.now(tz=timezone.utc)
        frames = [
            _make_frame(1, pv=10.0, ts=now - timedelta(days=10)),
            _make_frame(1, pv=20.0, ts=now),
        ]
        await historian.write_batch(frames)
        deleted = await historian.cleanup_older_than(7)
        assert deleted == 1
        result = await historian.query(1, now - timedelta(days=20), now + timedelta(days=1))
        assert len(result) == 1
        assert result[0].pv == 20.0

    @pytest.mark.asyncio
    async def test_empty_batch_is_noop(self, historian) -> None:
        await historian.write_batch([])
