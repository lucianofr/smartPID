"""SystemEventRepository — CRUD for Log_System_Events table."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite


class SystemEventRepository:
    """Persistence layer for system events (write-once, read-many)."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def insert_event(
        self, source: str, severity: str, message: str,
    ) -> int:
        """Insert a system event. Returns the event ID."""
        now = datetime.now(tz=UTC).isoformat()
        async with self._db.execute(
            """INSERT INTO Log_System_Events (timestamp, source, severity, message)
               VALUES (?, ?, ?, ?)""",
            (now, source, severity, message),
        ) as cur:
            event_id = cur.lastrowid
        await self._db.commit()
        return event_id or 0

    async def get_history(
        self,
        start: datetime,
        end: datetime,
        source: str | None = None,
        severity: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Return system events in a time range with optional filters."""
        sql = """SELECT id, timestamp, source, severity, message
                 FROM Log_System_Events
                 WHERE timestamp BETWEEN ? AND ?"""
        params: list = [start.isoformat(), end.isoformat()]
        if source is not None:
            sql += " AND source = ?"
            params.append(source)
        if severity is not None:
            sql += " AND severity = ?"
            params.append(severity)
        sql += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with self._db.execute(sql, params) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]
