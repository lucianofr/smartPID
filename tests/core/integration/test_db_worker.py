from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import msgpack
import pytest

from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.workers.db_worker import DBWorker


@pytest.fixture
async def setup(tmp_path):
    db_path = tmp_path / "test.spid"
    repo = SQLiteRepository(db_path)
    await repo.initialize()
    historian = SQLiteHistorian(repo)
    bus = EventBus()
    bus.start()
    yield bus, historian, repo
    bus.stop()


class TestDBWorker:
    @pytest.mark.asyncio
    async def test_flushes_telemetry_to_db(self, setup) -> None:
        bus, historian, repo = setup
        worker = DBWorker(bus=bus, historian=historian, flush_interval_s=0.1)
        worker.start()
        try:
            pub = bus.create_publisher()
            time.sleep(0.05)
            now = datetime.now(tz=UTC)
            frame_data = {
                "controller_id": 1, "pv": 55.0, "sp": 50.0, "co": 30.0,
                "integral_val": 1.2, "timestamp": now.isoformat(), "status": "GOOD",
            }
            pub.send(b"TELEMETRY.1", msgpack.packb(frame_data))
            time.sleep(0.2)
            result = await historian.query(
                1, now - timedelta(seconds=5), now + timedelta(seconds=5)
            )
            assert len(result) >= 1
            assert result[0].pv.value == 55.0
        finally:
            worker.stop()

    @pytest.mark.asyncio
    async def test_handles_multiple_frames(self, setup) -> None:
        bus, historian, repo = setup
        worker = DBWorker(bus=bus, historian=historian, flush_interval_s=0.1)
        worker.start()
        try:
            pub = bus.create_publisher()
            time.sleep(0.05)
            now = datetime.now(tz=UTC)
            for i in range(5):
                frame_data = {
                    "controller_id": 1, "pv": 50.0 + i, "sp": 50.0, "co": 25.0,
                    "integral_val": 1.0, "timestamp": now.isoformat(), "status": "GOOD",
                }
                pub.send(b"TELEMETRY.1", msgpack.packb(frame_data))
            time.sleep(0.2)
            result = await historian.query(
                1, now - timedelta(seconds=5), now + timedelta(seconds=5)
            )
            assert len(result) == 5
        finally:
            worker.stop()
