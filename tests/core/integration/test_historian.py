from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_domain.models.signal import FFSignal
from smart_pid_domain.models.telemetry import TelemetryFrame


@pytest.fixture
async def historian(tmp_path):
    db_path = tmp_path / "test.spid"
    repo = SQLiteRepository(db_path)
    await repo.initialize()
    return SQLiteHistorian(repo.session_factory)


def _make_frame(controller_id: int, pv: float, ts: datetime) -> TelemetryFrame:
    return TelemetryFrame(
        controller_id=controller_id, pv=FFSignal.good(pv), sp=FFSignal.good(50.0),
        co=FFSignal.good(25.0), bkcal_in=FFSignal.good(0.0),
        integral_val=1.0, timestamp=ts,
    )


class TestSQLiteHistorian:
    @pytest.mark.asyncio
    async def test_write_batch_and_query(self, historian) -> None:
        now = datetime.now(tz=UTC)
        frames = [_make_frame(1, pv=50.0 + i, ts=now + timedelta(seconds=i)) for i in range(10)]
        await historian.write_batch(frames)
        result = await historian.query(1, now - timedelta(seconds=1), now + timedelta(seconds=20))
        assert len(result) == 10
        assert result[0].pv.value == 50.0
        assert result[9].pv.value == 59.0

    @pytest.mark.asyncio
    async def test_query_filters_by_controller(self, historian) -> None:
        now = datetime.now(tz=UTC)
        frames = [_make_frame(1, pv=10.0, ts=now), _make_frame(2, pv=20.0, ts=now)]
        await historian.write_batch(frames)
        result = await historian.query(1, now - timedelta(seconds=1), now + timedelta(seconds=1))
        assert len(result) == 1
        assert result[0].controller_id == 1

    @pytest.mark.asyncio
    async def test_query_filters_by_time_range(self, historian) -> None:
        now = datetime.now(tz=UTC)
        frames = [
            _make_frame(1, pv=10.0, ts=now - timedelta(hours=2)),
            _make_frame(1, pv=20.0, ts=now),
        ]
        await historian.write_batch(frames)
        result = await historian.query(1, now - timedelta(hours=1), now + timedelta(hours=1))
        assert len(result) == 1
        assert result[0].pv.value == 20.0

    @pytest.mark.asyncio
    async def test_cleanup_removes_old_data(self, historian) -> None:
        now = datetime.now(tz=UTC)
        frames = [
            _make_frame(1, pv=10.0, ts=now - timedelta(days=10)),
            _make_frame(1, pv=20.0, ts=now),
        ]
        await historian.write_batch(frames)
        deleted = await historian.cleanup_older_than(7)
        assert deleted == 1
        result = await historian.query(1, now - timedelta(days=20), now + timedelta(days=1))
        assert len(result) == 1
        assert result[0].pv.value == 20.0

    @pytest.mark.asyncio
    async def test_empty_batch_is_noop(self, historian) -> None:
        await historian.write_batch([])


class TestQueryDecimated:
    """Backs the trend ring's lazy fill: one row per bucket, plain tuples."""

    @pytest.mark.asyncio
    async def test_thins_a_ten_hz_write_to_one_row_per_second(self, historian) -> None:
        base = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)
        # 30 s of a 10 Hz scan.
        await historian.write_batch(
            [_make_frame(1, pv=float(i), ts=base + timedelta(seconds=i * 0.1)) for i in range(300)]
        )
        rows = await historian.query_decimated(
            1, base - timedelta(seconds=1), base + timedelta(seconds=60), 1.0
        )
        assert len(rows) == 30
        # First frame of each whole second, so pv advances by 10.
        assert [r[1] for r in rows] == [float(i * 10) for i in range(30)]
        # Ascending, and the shape the ring's columns consume.
        stamps = [r[0] for r in rows]
        assert stamps == sorted(stamps)
        assert rows[0] == (base.timestamp(), 0.0, 50.0, 25.0)

    @pytest.mark.asyncio
    async def test_bucket_width_is_honoured(self, historian) -> None:
        base = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)
        await historian.write_batch(
            [_make_frame(1, pv=float(i), ts=base + timedelta(seconds=i)) for i in range(60)]
        )
        rows = await historian.query_decimated(
            1, base - timedelta(seconds=1), base + timedelta(seconds=120), 10.0
        )
        assert len(rows) == 6

    @pytest.mark.asyncio
    async def test_filters_by_controller_and_range(self, historian) -> None:
        base = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)
        await historian.write_batch(
            [
                _make_frame(1, pv=11.0, ts=base),
                _make_frame(2, pv=22.0, ts=base),
                _make_frame(1, pv=33.0, ts=base + timedelta(hours=2)),
            ]
        )
        rows = await historian.query_decimated(
            1, base - timedelta(seconds=1), base + timedelta(seconds=1), 1.0
        )
        assert [r[1] for r in rows] == [11.0]

    @pytest.mark.asyncio
    async def test_empty_range_returns_no_rows(self, historian) -> None:
        base = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)
        await historian.write_batch([_make_frame(1, pv=1.0, ts=base)])
        rows = await historian.query_decimated(
            1, base + timedelta(hours=1), base + timedelta(hours=2), 1.0
        )
        assert rows == []
