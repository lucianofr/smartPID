# packages/smart_pid_core/src/smart_pid_core/adapters/outbound/alarm_repo.py
"""Alarm repository — CRUD operations on Log_Alarmes / Configuracao_Alarmes."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from smart_pid_domain.enums import AlarmPriority, AlarmType


class AlarmRepository:
    """Persistence layer for alarm events (injected .spid session factory)."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def insert_alarm(
        self,
        controller_id: int,
        alarm_type: AlarmType,
        priority: AlarmPriority,
        value: float,
        limit_value: float,
        triggered_at: datetime,
    ) -> int:
        """Insert a new alarm record. Returns the alarm ID."""
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    """INSERT INTO Log_Alarmes
                       (controlador_id, tipo_alarme, prioridade, valor, limite, timestamp)
                       VALUES (:cid, :atype, :prio, :value, :limit, :ts)"""
                ),
                {
                    "cid": controller_id,
                    "atype": str(alarm_type),
                    "prio": str(priority),
                    "value": value,
                    "limit": limit_value,
                    "ts": triggered_at.isoformat(),
                },
            )
            alarm_id = result.lastrowid
            await session.commit()
        return alarm_id or 0

    async def mark_cleared(
        self,
        controller_id: int,
        alarm_type: AlarmType,
        cleared_at: datetime,
    ) -> None:
        async with self._session_factory() as session:
            await session.execute(
                text(
                    """UPDATE Log_Alarmes SET cleared_at = :cleared
                       WHERE controlador_id = :cid AND tipo_alarme = :atype
                         AND cleared_at IS NULL"""
                ),
                {"cleared": cleared_at.isoformat(), "cid": controller_id,
                 "atype": str(alarm_type)},
            )
            await session.commit()

    async def acknowledge(
        self,
        alarm_id: int,
        username: str,
        ack_at: datetime,
    ) -> dict:
        async with self._session_factory() as session:
            await session.execute(
                text(
                    """UPDATE Log_Alarmes
                       SET reconhecido = 1, reconhecido_por = :user, reconhecido_em = :ts
                       WHERE id = :aid"""
                ),
                {"user": username, "ts": ack_at.isoformat(), "aid": alarm_id},
            )
            await session.commit()
            result = await session.execute(
                text(
                    """SELECT id, controlador_id as controller_id, tipo_alarme as alarm_type,
                              prioridade as priority
                       FROM Log_Alarmes WHERE id = :aid"""
                ),
                {"aid": alarm_id},
            )
            row = result.mappings().first()
        if row is None:
            return {"id": alarm_id, "acknowledged": True}
        return {
            "id": row["id"],
            "controller_id": row["controller_id"],
            "alarm_type": row["alarm_type"],
            "priority": row["priority"],
            "acknowledged": True,
        }

    async def acknowledge_all(self, username: str, ack_at: datetime) -> dict:
        async with self._session_factory() as session:
            result = await session.execute(
                text("SELECT DISTINCT controlador_id FROM Log_Alarmes WHERE reconhecido = 0"),
            )
            controller_ids = [row["controlador_id"] for row in result.mappings().all()]
            result = await session.execute(
                text(
                    """UPDATE Log_Alarmes
                       SET reconhecido = 1, reconhecido_por = :user, reconhecido_em = :ts
                       WHERE reconhecido = 0"""
                ),
                {"user": username, "ts": ack_at.isoformat()},
            )
            count = result.rowcount
            await session.commit()
        return {"acknowledged_count": count, "controller_ids": controller_ids}

    async def get_active(
        self,
        controller_id: int | None = None,
        priority: str | None = None,
    ) -> list[dict]:
        sql = """SELECT a.id, a.controlador_id as controller_id,
                        c.nome as controller_name,
                        a.tipo_alarme as alarm_type,
                        a.prioridade as priority, a.valor as value,
                        a.limite as "limit",
                        a.timestamp, a.cleared_at,
                        a.reconhecido as acknowledged,
                        a.reconhecido_por as ack_by_user, a.reconhecido_em as ack_at,
                        CASE
                            WHEN a.reconhecido = 1 THEN 'ACKNOWLEDGED'
                            WHEN a.cleared_at IS NOT NULL THEN 'CLEARED_UNACK'
                            ELSE 'UNACKNOWLEDGED'
                        END as status
                 FROM Log_Alarmes a
                 LEFT JOIN Controladores c ON c.id = a.controlador_id
                 WHERE NOT (a.cleared_at IS NOT NULL AND a.reconhecido = 1)"""
        params: dict = {}
        if controller_id is not None:
            sql += " AND a.controlador_id = :cid"
            params["cid"] = controller_id
        if priority is not None:
            sql += " AND a.prioridade = :prio"
            params["prio"] = priority
        sql += " ORDER BY a.timestamp DESC"
        async with self._session_factory() as session:
            result = await session.execute(text(sql), params)
            rows = result.mappings().all()
        return [dict(r) for r in rows]

    async def get_alarm_config(self, controller_id: int) -> list[dict]:
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    """SELECT id, controlador_id as controller_id, tipo_alarme as alarm_type,
                              prioridade as priority, limite as "limit", habilitado as enabled,
                              histerese as deadband, delay_on_s, delay_off_s
                       FROM Configuracao_Alarmes WHERE controlador_id = :cid
                       ORDER BY tipo_alarme"""
                ),
                {"cid": controller_id},
            )
            rows = result.mappings().all()
        return [dict(r) for r in rows]

    async def save_alarm_config(
        self,
        controller_id: int,
        thresholds: list[dict],
    ) -> None:
        async with self._session_factory() as session:
            await session.execute(
                text("DELETE FROM Configuracao_Alarmes WHERE controlador_id = :cid"),
                {"cid": controller_id},
            )
            for t in thresholds:
                await session.execute(
                    text(
                        """INSERT INTO Configuracao_Alarmes
                           (controlador_id, tipo_alarme, prioridade, limite, habilitado,
                            histerese, delay_on_s, delay_off_s)
                           VALUES (:cid, :atype, :prio, :limit, :enabled,
                                   :deadband, :don, :doff)"""
                    ),
                    {
                        "cid": controller_id,
                        "atype": t["alarm_type"],
                        "prio": t["priority"],
                        "limit": t["limit"],
                        "enabled": 1 if t.get("enabled", True) else 0,
                        "deadband": t.get("deadband", 0.0),
                        "don": t.get("delay_on_s", 0.0),
                        "doff": t.get("delay_off_s", 0.0),
                    },
                )
            await session.commit()

    async def get_history(
        self,
        start: datetime,
        end: datetime,
        controller_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        sql = """SELECT a.id, a.controlador_id as controller_id,
                        c.nome as controller_name,
                        a.tipo_alarme as alarm_type,
                        a.prioridade as priority, a.valor as value,
                        a.limite as "limit",
                        a.timestamp, a.cleared_at,
                        a.reconhecido as acknowledged,
                        a.reconhecido_por as ack_by_user, a.reconhecido_em as ack_at,
                        CASE
                            WHEN a.reconhecido = 1 THEN 'ACKNOWLEDGED'
                            WHEN a.cleared_at IS NOT NULL THEN 'CLEARED_UNACK'
                            ELSE 'UNACKNOWLEDGED'
                        END as status
                 FROM Log_Alarmes a
                 LEFT JOIN Controladores c ON c.id = a.controlador_id
                 WHERE a.timestamp BETWEEN :start AND :end"""
        params: dict = {"start": start.isoformat(), "end": end.isoformat()}
        if controller_id is not None:
            sql += " AND a.controlador_id = :cid"
            params["cid"] = controller_id
        sql += " ORDER BY a.timestamp DESC LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset
        async with self._session_factory() as session:
            result = await session.execute(text(sql), params)
            rows = result.mappings().all()
        return [dict(r) for r in rows]
