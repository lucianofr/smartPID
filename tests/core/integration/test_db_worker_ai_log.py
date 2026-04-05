"""Tests for DBWorker LOG.AI persistence — Gap #16."""
from __future__ import annotations

import uuid

import msgpack
import pytest

from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.workers.db_worker import DBWorker


@pytest.mark.asyncio
async def test_db_worker_persists_ai_log(tmp_path) -> None:
    """DBWorker subscribes to LOG.AI.* and inserts into Log_Sintonia_IA."""
    db_path = tmp_path / "test.spid"
    repo = SQLiteRepository(db_path)
    await repo.initialize()
    historian = SQLiteHistorian(repo.db)

    bus = EventBus(url_prefix=f"inproc://test_{uuid.uuid4().hex[:8]}")
    bus.start()

    worker = DBWorker(bus=bus, historian=historian, flush_interval_s=0.1)
    worker.start()

    # Give subscriber time to connect
    import time
    time.sleep(0.05)

    # Publish an AI log message
    pub = bus.create_publisher()
    time.sleep(0.02)
    log_data = {
        "controller_id": 42,
        "engine": "FUZZY",
        "gamma": 0.5,
        "old_ki": 10.0,
        "new_ki": 10.75,
        "objective": "SP_TRACKING",
        "reasoning": "test",
        "timestamp": "2026-04-05T12:00:00+00:00",
    }
    pub.send(b"LOG.AI.42", msgpack.packb(log_data))

    # Wait for flush
    time.sleep(0.3)
    worker.stop()
    pub.close()

    # Verify in DB
    async with repo.db.execute(
        "SELECT controlador_id, motor, ki_antes, ki_depois, objetivo, metrica "
        "FROM Log_Sintonia_IA WHERE controlador_id = 42"
    ) as cur:
        rows = await cur.fetchall()

    assert len(rows) == 1
    row = rows[0]
    assert row[0] == 42  # controlador_id
    assert row[1] == "FUZZY"  # motor
    assert row[2] == 10.0  # ki_antes
    assert row[3] == 10.75  # ki_depois
    assert row[4] == "SP_TRACKING"  # objetivo
    assert row[5] == 0.5  # metrica (gamma)

    bus.stop()
    await repo.db.close()


@pytest.mark.asyncio
async def test_db_worker_ai_log_buffer_empty_noop(tmp_path) -> None:
    """DBWorker flush of empty AI buffer is a no-op."""
    db_path = tmp_path / "test.spid"
    repo = SQLiteRepository(db_path)
    await repo.initialize()
    historian = SQLiteHistorian(repo.db)

    bus = EventBus(url_prefix=f"inproc://test_{uuid.uuid4().hex[:8]}")
    bus.start()

    worker = DBWorker(bus=bus, historian=historian, flush_interval_s=0.1)
    worker.start()

    import time
    time.sleep(0.2)
    worker.stop()

    async with repo.db.execute(
        "SELECT COUNT(*) FROM Log_Sintonia_IA"
    ) as cur:
        row = await cur.fetchone()
    assert row[0] == 0

    bus.stop()
    await repo.db.close()
