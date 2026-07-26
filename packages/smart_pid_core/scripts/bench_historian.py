"""Historian write-throughput benchmark — spec §10 "benchmark before/after phase 1".

Run from the worktree root:
    uv run python packages/smart_pid_core/scripts/bench_historian.py

Works both before the SQLAlchemy port (SQLiteHistorian(repo)) and after
(SQLAlchemyHistorian(repo.session_factory)) so the same script produces the
before/after pair recorded in BENCH.md.
"""
from __future__ import annotations

import asyncio
import statistics
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_domain.models.signal import FFSignal
from smart_pid_domain.models.telemetry import TelemetryFrame

N_FRAMES = 50_000
BATCH_SIZE = 500  # matches DBWorker default batch_size
QUERY_RUNS = 5


def _make_frames(n: int) -> list[TelemetryFrame]:
    base = datetime.now(tz=UTC)
    return [
        TelemetryFrame(
            controller_id=1,
            pv=FFSignal.good(50.0 + (i % 100) * 0.1, base),
            sp=FFSignal.good(50.0, base),
            co=FFSignal.good(25.0, base),
            bkcal_in=FFSignal.good(0.0, base),
            integral_val=1.0,
            timestamp=base + timedelta(milliseconds=i),
        )
        for i in range(n)
    ]


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "bench.spid"
        repo = SQLiteRepository(db_path)
        await repo.initialize()
        session_factory = getattr(repo, "session_factory", None)
        if session_factory is not None:
            historian = SQLiteHistorian(session_factory)
            flavor = "sqlalchemy"
        else:
            historian = SQLiteHistorian(repo)  # pre-port constructor
            flavor = "aiosqlite"

        frames = _make_frames(N_FRAMES)
        t0 = time.perf_counter()
        for i in range(0, N_FRAMES, BATCH_SIZE):
            await historian.write_batch(frames[i : i + BATCH_SIZE])
        write_s = time.perf_counter() - t0

        start = frames[0].timestamp - timedelta(seconds=1)
        end = frames[-1].timestamp + timedelta(seconds=1)
        query_times: list[float] = []
        for _ in range(QUERY_RUNS):
            t0 = time.perf_counter()
            rows = await historian.query(1, start, end)
            query_times.append(time.perf_counter() - t0)
        assert len(rows) == N_FRAMES, f"expected {N_FRAMES} rows, got {len(rows)}"

        await repo.close()
        print(f"flavor={flavor}")
        print(f"write: {N_FRAMES} frames in {write_s:.3f}s -> {N_FRAMES / write_s:,.0f} rows/s")
        print(f"query: median {statistics.median(query_times) * 1000:.1f} ms for {N_FRAMES} rows")


if __name__ == "__main__":
    asyncio.run(main())
