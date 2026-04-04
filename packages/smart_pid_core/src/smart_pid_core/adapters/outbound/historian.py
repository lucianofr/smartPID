"""SQLite-backed historian adapter for telemetry data."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite

from smart_pid_domain.models.signal import FFSignal
from smart_pid_domain.models.telemetry import TelemetryFrame


class SQLiteHistorian:
    """Writes and queries process telemetry in Log_Processo.

    Shares the aiosqlite.Connection owned by SQLiteRepository.
    """

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def write_batch(self, frames: list[TelemetryFrame]) -> None:
        """Batch-insert telemetry frames. No-op for empty list."""
        if not frames:
            return
        rows = [
            (
                f.controller_id,
                f.timestamp.isoformat(),
                f.pv.value,
                f.sp.value,
                f.co.value,
                f.integral_val,
            )
            for f in frames
        ]
        await self._db.executemany(
            "INSERT INTO Log_Processo (controlador_id, timestamp, pv, sp, co, integral_val) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        await self._db.commit()

    async def query(
        self,
        controller_id: int,
        start: datetime,
        end: datetime,
    ) -> list[TelemetryFrame]:
        """Return frames for a controller within [start, end] inclusive."""
        async with self._db.execute(
            "SELECT controlador_id, timestamp, pv, sp, co, integral_val "
            "FROM Log_Processo "
            "WHERE controlador_id = ? AND timestamp >= ? AND timestamp <= ? "
            "ORDER BY timestamp",
            (controller_id, start.isoformat(), end.isoformat()),
        ) as cur:
            rows = await cur.fetchall()

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

    async def cleanup_older_than(self, days: int) -> int:
        """Delete frames older than `days` days. Returns count deleted."""
        async with self._db.execute(
            "DELETE FROM Log_Processo WHERE timestamp <= datetime('now', ?)",
            (f"-{days} days",),
        ) as cur:
            deleted = cur.rowcount
        await self._db.commit()
        return deleted
