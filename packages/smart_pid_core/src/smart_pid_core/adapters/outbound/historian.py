"""SQLite-backed historian adapter for telemetry data (SQLAlchemy async)."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import insert, text

from smart_pid_core.adapters.outbound.db_models import log_processo
from smart_pid_domain.models.signal import FFSignal
from smart_pid_domain.models.telemetry import TelemetryFrame

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class SQLiteHistorian:
    """Writes and queries process telemetry in Log_Processo.

    Bound to an injected async_sessionmaker: the main-loop instance receives
    engine A's factory (API reads, export); the DB worker builds its own
    instance over engine B on its private loop. The main-loop factory is
    re-bound in place across reopen(), so this class never goes stale.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def write_batch(self, frames: list[TelemetryFrame]) -> None:
        """Batch-insert telemetry frames. No-op for empty list.

        HOT PATH (spec §10): Core executemany — ``conn.execute(insert(...),
        rows)`` with a list of parameter dicts — one commit per batch.
        ``session.add_all()`` (per-object flush) is forbidden here.
        """
        if not frames:
            return
        rows = [
            {
                "controlador_id": f.controller_id,
                "timestamp": f.timestamp.isoformat(),
                "pv": f.pv.value,
                "sp": f.sp.value,
                "co": f.co.value,
                "integral_val": f.integral_val,
            }
            for f in frames
        ]
        async with self._session_factory() as session:
            conn = await session.connection()
            await conn.execute(insert(log_processo), rows)
            await session.commit()

    async def query(
        self,
        controller_id: int,
        start: datetime,
        end: datetime,
    ) -> list[TelemetryFrame]:
        """Return frames for a controller within [start, end] inclusive."""
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT controlador_id, timestamp, pv, sp, co, integral_val "
                    "FROM Log_Processo "
                    "WHERE controlador_id = :cid AND timestamp >= :start AND timestamp <= :end "
                    "ORDER BY timestamp"
                ),
                {"cid": controller_id, "start": start.isoformat(), "end": end.isoformat()},
            )
            rows = result.all()

        results: list[TelemetryFrame] = []
        for row in rows:
            ts = datetime.fromisoformat(row[1])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            results.append(
                TelemetryFrame(
                    controller_id=row[0],
                    pv=FFSignal.good(row[2], ts),
                    sp=FFSignal.good(row[3], ts),
                    co=FFSignal.good(row[4], ts),
                    bkcal_in=FFSignal.good(0.0, ts),
                    integral_val=row[5],
                    timestamp=ts,
                )
            )
        return results

    async def query_decimated(
        self,
        controller_id: int,
        start: datetime,
        end: datetime,
        interval_s: float,
    ) -> list[tuple[float, float, float, float]]:
        """One row per ``interval_s`` bucket as ``(epoch, pv, sp, co)``, ascending.

        Backs the trend ring's lazy fill. ``Log_Processo`` holds every frame of
        the 10 Hz scan while the ring keeps one per second, so a raw range read
        would materialise ~10x the rows the ring can store — and as
        ``TelemetryFrame`` objects with four ``FFSignal`` each. SQLite does the
        thinning instead: one bucket per ``interval_s``, and SQLite's documented
        bare-column rule pairs ``pv``/``sp``/``co`` with the ``MIN(timestamp)``
        row of each bucket. Plain tuples, because the caller feeds them straight
        into the ring's float columns.

        Bucketing is NOT a spacing guarantee: ``strftime('%s')`` truncates to
        whole seconds, so the last frame of one bucket and the first of the next
        can be ~0.1 s apart. Enforcing the ring's minimum spacing stays with
        ``TrendBuffer.backfill``.
        """
        bucket = max(1, int(interval_s))
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT MIN(timestamp) AS ts, pv, sp, co "
                    "FROM Log_Processo "
                    "WHERE controlador_id = :cid "
                    "AND timestamp >= :start AND timestamp <= :end "
                    "GROUP BY CAST(strftime('%s', timestamp) AS INTEGER) / :bucket "
                    "ORDER BY ts"
                ),
                {
                    "cid": controller_id,
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "bucket": bucket,
                },
            )
            rows = result.all()

        samples: list[tuple[float, float, float, float]] = []
        for row in rows:
            ts = datetime.fromisoformat(row[0])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            samples.append((ts.timestamp(), row[1], row[2], row[3]))
        return samples

    async def write_ai_log(self, entry: dict) -> None:
        """Insert a single AI tuning log entry into Log_Sintonia_IA."""
        async with self._session_factory() as session:
            await session.execute(
                text(
                    "INSERT INTO Log_Sintonia_IA "
                    "(controlador_id, timestamp, motor, ki_antes, ki_depois,"
                    " objetivo, metrica, aprovado)"
                    " VALUES (:cid, :ts, :motor, :ki_antes, :ki_depois, :objetivo, :metrica, 1)"
                ),
                {
                    "cid": entry["controller_id"],
                    "ts": entry.get("timestamp", ""),
                    "motor": entry.get("engine", "NONE"),
                    "ki_antes": entry.get("old_ki"),
                    "ki_depois": entry.get("new_ki"),
                    "objetivo": entry.get("objective", ""),
                    "metrica": entry.get("gamma"),
                },
            )
            await session.commit()

    async def cleanup_older_than(self, days: int) -> int:
        """Delete frames older than `days` days. Returns count deleted."""
        async with self._session_factory() as session:
            result = await session.execute(
                text("DELETE FROM Log_Processo WHERE timestamp <= datetime('now', :offset)"),
                {"offset": f"-{days} days"},
            )
            await session.commit()
        return result.rowcount
