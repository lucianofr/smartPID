"""SystemEventRepository — CRUD for Log_System_Events table."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class SystemEventRepository:
    """Persistence layer for system events (write-once, read-many).

    Takes the .spid ``async_sessionmaker`` (engine A). The sessionmaker is
    re-bound in place on ``reopen()``, so — unlike the pre-port eager
    ``aiosqlite.Connection`` capture — this repository keeps working after a
    project switch (deliberate, documented behavior change: the stale-
    connection bug is fixed by the port).
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def insert_event(
        self, source: str, severity: str, message: str,
    ) -> int:
        """Insert a system event. Returns the event ID."""
        now = datetime.now(tz=UTC).isoformat()
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    "INSERT INTO Log_System_Events (timestamp, source, severity, message)"
                    " VALUES (:ts, :source, :severity, :message)"
                ),
                {"ts": now, "source": source, "severity": severity, "message": message},
            )
            event_id = result.lastrowid
            await session.commit()
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
                 WHERE timestamp BETWEEN :start AND :end"""
        params: dict = {"start": start.isoformat(), "end": end.isoformat()}
        if source is not None:
            sql += " AND source = :source"
            params["source"] = source
        if severity is not None:
            sql += " AND severity = :severity"
            params["severity"] = severity
        sql += " ORDER BY timestamp DESC LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset

        async with self._session_factory() as session:
            result = await session.execute(text(sql), params)
            rows = result.mappings().all()
        return [dict(r) for r in rows]
