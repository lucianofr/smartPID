"""Audit repository — CRUD operations on Log_Auditoria table."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from smart_pid_domain.enums import AuditAction


class AuditRepository:
    """Persistence layer for audit trail entries (injected .spid session factory)."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def record(
        self,
        user_id: int,
        username: str,
        action: AuditAction,
        resource: str | None,
        detail: str | None,
    ) -> None:
        """Insert an audit trail entry."""
        async with self._session_factory() as session:
            await session.execute(
                text(
                    """INSERT INTO Log_Auditoria
                       (usuario_id, username, timestamp, acao, entidade, detalhe)
                       VALUES (:uid, :user, :ts, :acao, :entidade, :detalhe)"""
                ),
                {
                    "uid": user_id,
                    "user": username,
                    "ts": datetime.now(tz=UTC).isoformat(),
                    "acao": str(action),
                    "entidade": resource or "",
                    "detalhe": detail or "",
                },
            )
            await session.commit()

    async def get_history(
        self,
        start: datetime,
        end: datetime,
        user_id: int | None = None,
        action: AuditAction | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        sql = """SELECT id, usuario_id as user_id, username, timestamp,
                        acao as action, entidade as resource, detalhe as detail
                 FROM Log_Auditoria WHERE timestamp BETWEEN :start AND :end"""
        params: dict = {"start": start.isoformat(), "end": end.isoformat()}
        if user_id is not None:
            sql += " AND usuario_id = :uid"
            params["uid"] = user_id
        if action is not None:
            sql += " AND acao = :acao"
            params["acao"] = str(action)
        sql += " ORDER BY timestamp DESC LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset

        async with self._session_factory() as session:
            result = await session.execute(text(sql), params)
            rows = result.mappings().all()
        return [dict(r) for r in rows]
