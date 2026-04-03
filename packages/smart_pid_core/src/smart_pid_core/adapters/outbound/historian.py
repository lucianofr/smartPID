"""SQLite-backed historian adapter for telemetry data."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite

from smart_pid_domain.enums import SignalStatus
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
                f.pv,
                f.sp,
                f.co,
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

        return [
            TelemetryFrame(
                controller_id=row[0],
                pv=row[2],
                sp=row[3],
                co=row[4],
                integral_val=row[5],
                timestamp=datetime.fromisoformat(row[1]).replace(tzinfo=UTC)
                if datetime.fromisoformat(row[1]).tzinfo is None
                else datetime.fromisoformat(row[1]),
                status=SignalStatus.GOOD,
            )
            for row in rows
        ]

    async def cleanup_older_than(self, days: int) -> int:
        """Delete frames older than `days` days. Returns count deleted."""
        async with self._db.execute(
            f"DELETE FROM Log_Processo WHERE timestamp <= datetime('now', '-{days} days')"
        ) as cur:
            deleted = cur.rowcount
        await self._db.commit()
        return deleted
