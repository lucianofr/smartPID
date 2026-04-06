"""Audit repository — CRUD operations on Log_Auditoria table."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
    from smart_pid_domain.enums import AuditAction


class AuditRepository:
    """Persistence layer for audit trail entries."""

    def __init__(self, repo: SQLiteRepository) -> None:
        self._repo = repo

    @property
    def _db(self):  # noqa: ANN202
        """Always return the current (possibly reopened) connection."""
        return self._repo.db

    async def record(
        self,
        user_id: int,
        username: str,
        action: AuditAction,
        resource: str | None,
        detail: str | None,
    ) -> None:
        """Insert an audit trail entry."""
        await self._db.execute(
            """INSERT INTO Log_Auditoria (usuario_id, username, timestamp, acao, entidade, detalhe)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                username,
                datetime.now(tz=UTC).isoformat(),
                str(action),
                resource or "",
                detail or "",
            ),
        )
        await self._db.commit()

    async def get_history(
        self,
        start: datetime,
        end: datetime,
        user_id: int | None = None,
        action: AuditAction | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Return audit entries in a time range."""
        sql = """SELECT id, usuario_id as user_id, username, timestamp,
                        acao as action, entidade as resource, detalhe as detail
                 FROM Log_Auditoria WHERE timestamp BETWEEN ? AND ?"""
        params: list = [start.isoformat(), end.isoformat()]
        if user_id is not None:
            sql += " AND usuario_id = ?"
            params.append(user_id)
        if action is not None:
            sql += " AND acao = ?"
            params.append(str(action))
        sql += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with self._db.execute(sql, params) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]
