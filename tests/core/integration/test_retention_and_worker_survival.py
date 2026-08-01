"""Retention first-pass/chunking and DBWorker survival on a failed flush.

Two defects, both root causes of the 1.08 GB project file and the lock storm:

D1 ``_retention_cleanup`` slept ``interval_hours`` BEFORE its first pass, so a
   daemon restarted more often than daily never pruned ``Log_Processo``. Making
   it run at startup is not enough on its own: a single unbounded ``DELETE`` on
   a multi-hundred-MB table holds the WAL write lock for seconds, which is the
   very contention the busy-timeout work was fighting. It must prune in bounded
   chunks, yielding between them.

D2 An ``OperationalError`` from ``DBWorker._flush()`` escaped the loop's
   ``try`` (which only wrapped ``recv`` and caught ``zmq.ZMQError``) and killed
   the worker thread. Telemetry persistence stopped silently.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from datetime import UTC, datetime, timedelta

import msgpack
import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import OperationalError

from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.workers.db_worker import DBWorker
from smart_pid_core.application.workers.monitor_worker import MonitorWorker
from smart_pid_core.application.workers.stats_worker import StatsWorker
from smart_pid_core.main import _retention_cleanup
from smart_pid_domain.models.controller import Controller


@pytest.fixture
async def repo(tmp_path):
    r = SQLiteRepository(tmp_path / "retention.spid")
    await r.initialize()
    yield r
    await r.close()


async def _seed_process_rows(repo: SQLiteRepository, rows: list[tuple[int, str]]) -> None:
    async with repo.session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO Log_Processo (controlador_id, timestamp, pv, sp, co,"
                " integral_val) VALUES (:cid, :ts, 1.0, 1.0, 1.0, 0.0)"
            ),
            [{"cid": cid, "ts": ts} for cid, ts in rows],
        )
        await session.commit()


async def _count(repo: SQLiteRepository, table: str) -> int:
    async with repo.session_factory() as session:
        return int((await session.execute(text(f"SELECT COUNT(*) FROM {table}"))).scalar_one())


async def _run_one_pass(repo: SQLiteRepository, **kwargs) -> None:
    """Drive _retention_cleanup until its first pass has completed."""
    task = asyncio.create_task(_retention_cleanup(repo.session_factory, **kwargs))
    try:
        await asyncio.sleep(0)
        deadline = time.monotonic() + 15.0
        # First pass must land without waiting out interval_hours.
        while time.monotonic() < deadline:
            await asyncio.sleep(0.05)
            if await _count(repo, "Log_Processo") == 0:
                return
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


class TestRetentionFirstPass:
    async def test_first_pass_runs_without_waiting_the_interval(self, repo) -> None:
        """RED on HEAD: the loop slept 24 h before pruning anything."""
        old = (datetime.now(tz=UTC) - timedelta(days=30)).isoformat()
        await _seed_process_rows(repo, [(1, old)] * 20)
        assert await _count(repo, "Log_Processo") == 20

        await _run_one_pass(repo, interval_hours=24)
        assert await _count(repo, "Log_Processo") == 0, (
            "first retention pass must run at startup, not after the interval"
        )

    async def test_recent_rows_are_retained(self, repo) -> None:
        recent = (datetime.now(tz=UTC) - timedelta(hours=1)).isoformat()
        old = (datetime.now(tz=UTC) - timedelta(days=30)).isoformat()
        await _seed_process_rows(repo, [(1, recent)] * 5 + [(1, old)] * 5)

        task = asyncio.create_task(_retention_cleanup(repo.session_factory))
        try:
            deadline = time.monotonic() + 15.0
            while time.monotonic() < deadline:
                await asyncio.sleep(0.05)
                if await _count(repo, "Log_Processo") == 5:
                    break
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert await _count(repo, "Log_Processo") == 5

    async def test_isoformat_row_just_past_cutoff_is_deleted(self, repo) -> None:
        """RED on HEAD: `isoformat()` rows vs `datetime('now',...)` mis-compare.

        Rows store ``2026-07-23T10:00:00+00:00`` ('T'), the old predicate built
        ``2026-07-23 10:00:00`` (space). 'T' > ' ', so a row *just* older than
        the cutoff compared greater and survived forever.
        """
        just_old = (datetime.now(tz=UTC) - timedelta(days=7, seconds=30)).isoformat()
        await _seed_process_rows(repo, [(1, just_old)] * 3)

        await _run_one_pass(repo)
        assert await _count(repo, "Log_Processo") == 0, (
            "row older than the 7-day cutoff must be pruned regardless of separator"
        )


class TestRetentionChunking:
    async def test_large_table_pruned_in_bounded_chunks(self, repo) -> None:
        """RED on HEAD: one unbounded DELETE held the write lock for the lot."""
        old = (datetime.now(tz=UTC) - timedelta(days=30)).isoformat()
        await _seed_process_rows(repo, [(1, old)] * 250)

        deletes: list[str] = []

        def _record(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001, ARG001, PLR0913
            if "DELETE FROM Log_Processo" in statement:
                deletes.append(statement)

        event.listen(repo.engine.sync_engine, "before_cursor_execute", _record)
        try:
            await _run_one_pass(repo, batch_rows=50)
        finally:
            event.remove(repo.engine.sync_engine, "before_cursor_execute", _record)

        assert await _count(repo, "Log_Processo") == 0
        assert len(deletes) >= 5, (
            f"250 rows at batch_rows=50 must take >=5 bounded deletes, got {len(deletes)}"
        )
        assert all("LIMIT" in s.upper() for s in deletes), (
            "every retention DELETE must be bounded by a LIMIT"
        )


class TestDBWorkerSurvivesFlushFailure:
    @pytest.fixture
    async def setup(self, tmp_path):
        db_path = tmp_path / "worker.spid"
        repo = SQLiteRepository(db_path)
        await repo.initialize()
        historian = SQLiteHistorian(repo.session_factory)  # engine A, for the test's reads
        bus = EventBus(url_prefix=f"inproc://test_survive_{uuid.uuid4().hex[:8]}")
        bus.start()
        yield bus, historian, repo
        bus.stop()
        await repo.close()

    async def test_lock_error_in_flush_does_not_kill_the_worker(
        self, setup, monkeypatch,
    ) -> None:
        """RED on HEAD: the OperationalError escaped and the thread died."""
        bus, historian, repo = setup
        real_write_batch = SQLiteHistorian.write_batch
        calls = {"n": 0}

        async def flaky_write_batch(self, frames):  # noqa: ANN001, ANN202
            calls["n"] += 1
            if calls["n"] == 1:
                raise OperationalError("INSERT", {}, Exception("database is locked"))
            return await real_write_batch(self, frames)

        monkeypatch.setattr(SQLiteHistorian, "write_batch", flaky_write_batch)

        worker = DBWorker(bus=bus, repo=repo, flush_interval_s=0.1)
        worker.start()
        try:
            pub = bus.create_publisher()
            time.sleep(0.05)
            now = datetime.now(tz=UTC)

            # Frame 1 -> the poisoned flush.
            pub.send(b"TELEMETRY.1", msgpack.packb({
                "controller_id": 1, "pv": 11.0, "sp": 50.0, "co": 30.0,
                "integral_val": 0.0, "timestamp": now.isoformat(), "status": "GOOD",
            }))
            time.sleep(0.4)
            assert calls["n"] >= 1, "the poisoned flush never ran"
            assert worker._thread is not None and worker._thread.is_alive(), (
                "worker thread died on a flush error instead of degrading"
            )

            # Frame 2 -> proves the worker is still consuming and persisting.
            pub.send(b"TELEMETRY.2", msgpack.packb({
                "controller_id": 2, "pv": 22.0, "sp": 50.0, "co": 30.0,
                "integral_val": 0.0, "timestamp": now.isoformat(), "status": "GOOD",
            }))
            time.sleep(0.5)

            rows = await historian.query(
                2, now - timedelta(seconds=5), now + timedelta(seconds=5)
            )
            assert len(rows) >= 1, "worker stopped persisting after a flush failure"
            assert rows[0].pv.value == 22.0
            assert worker.flush_failures >= 1, "the dropped batch must be counted"
        finally:
            worker.stop()


def _telemetry(cid: int, pv: float | None) -> bytes:
    """A frame shaped exactly like IOWorker's, with a settable PV value."""
    def sig(v: float | None) -> dict:
        return {
            "value": v, "severity": "GOOD",
            "limit_bits": "NONE", "sub_status": "NONE",
        }

    return msgpack.packb({
        "controller_id": cid,
        "pv": sig(pv), "sp": sig(50.0), "co": sig(10.0), "bkcal_in": sig(10.0),
        "mode": "AUTO", "pid_enabled": True, "integral_val": 0.0,
        "timestamp": datetime.now(tz=UTC).isoformat(),
    })


class TestWorkersSurviveACorruptedFrame:
    """D3/D4: a frame with ``pv.value = null`` used to kill two worker threads.

    ``PIDWorker`` got its ``except Exception`` guard earlier; ``StatsWorker``
    and ``MonitorWorker`` were missed. Both raise a ``TypeError`` on a null PV
    (``None`` reaches arithmetic), which is not ``zmq.ZMQError`` and so escaped
    the loop and ended the thread — with nothing logged. The metrics endpoint
    then served a frozen snapshot forever and, in monitor mode, ``STATUS.{id}``
    stopped entirely: both look exactly like a perfectly steady loop.
    """

    @pytest.fixture
    def bus(self):
        b = EventBus(url_prefix=f"inproc://test_badframe_{uuid.uuid4().hex[:8]}")
        b.start()
        yield b
        b.stop()

    def test_stats_worker_survives_null_pv(self, bus) -> None:
        ctrl = Controller(id=31, name="TIC-031", scan_rate_s=0.05, tss_s=5.0)
        worker = StatsWorker(bus=bus, controller=ctrl)
        worker.start()
        try:
            pub = bus.create_publisher()
            time.sleep(0.1)
            for _ in range(4):
                pub.send(b"TELEMETRY.31", _telemetry(31, 20.0))
                time.sleep(0.05)
            time.sleep(0.2)
            healthy = worker.get_current_stats()["sample_count"]
            assert healthy > 0, "no samples were accumulated before the bad frame"

            pub.send(b"TELEMETRY.31", _telemetry(31, None))
            time.sleep(0.3)
            assert worker._thread is not None and worker._thread.is_alive(), (
                "stats thread died on a corrupted frame"
            )

            for _ in range(4):
                pub.send(b"TELEMETRY.31", _telemetry(31, 21.0))
                time.sleep(0.05)
            time.sleep(0.3)
            assert worker.get_current_stats()["sample_count"] > healthy, (
                "stats stopped advancing after a corrupted frame"
            )
        finally:
            worker.stop()

    def test_monitor_worker_survives_null_pv(self, bus) -> None:
        worker = MonitorWorker(bus=bus, controller_id=32, scan_rate_s=0.05)
        worker.start()
        try:
            pub = bus.create_publisher()
            status_sub = bus.create_subscriber(b"STATUS.32")
            time.sleep(0.1)

            pub.send(b"TELEMETRY.32", _telemetry(32, None))
            time.sleep(0.3)
            assert worker.is_alive(), "monitor thread died on a corrupted frame"

            while status_sub.recv(timeout_ms=0) is not None:
                pass
            pub.send(b"TELEMETRY.32", _telemetry(32, 21.0))
            time.sleep(0.3)
            assert status_sub.recv(timeout_ms=500) is not None, (
                "STATUS stopped being published after a corrupted frame"
            )
        finally:
            worker.stop()
