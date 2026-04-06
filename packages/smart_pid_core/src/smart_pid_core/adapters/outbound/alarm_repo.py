# packages/smart_pid_core/src/smart_pid_core/adapters/outbound/alarm_repo.py
"""Alarm repository — CRUD operations on Log_Alarmes table."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    import aiosqlite

    from smart_pid_domain.enums import AlarmPriority, AlarmType


class AlarmRepository:
    """Persistence layer for alarm events."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

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
        async with self._db.execute(
            """INSERT INTO Log_Alarmes
               (controlador_id, tipo_alarme, prioridade, valor, limite, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                controller_id,
                str(alarm_type),
                str(priority),
                value,
                limit_value,
                triggered_at.isoformat(),
            ),
        ) as cur:
            alarm_id = cur.lastrowid
        await self._db.commit()
        return alarm_id or 0

    async def mark_cleared(
        self,
        controller_id: int,
        alarm_type: AlarmType,
        cleared_at: datetime,
    ) -> None:
        """Mark the most recent active alarm of this type as cleared."""
        await self._db.execute(
            """UPDATE Log_Alarmes SET cleared_at = ?
               WHERE controlador_id = ? AND tipo_alarme = ? AND cleared_at IS NULL""",
            (cleared_at.isoformat(), controller_id, str(alarm_type)),
        )
        await self._db.commit()

    async def acknowledge(
        self,
        alarm_id: int,
        username: str,
        ack_at: datetime,
    ) -> None:
        """Acknowledge a specific alarm."""
        await self._db.execute(
            """UPDATE Log_Alarmes SET reconhecido = 1, reconhecido_por = ?, reconhecido_em = ?
               WHERE id = ?""",
            (username, ack_at.isoformat(), alarm_id),
        )
        await self._db.commit()

    async def acknowledge_all(self, username: str, ack_at: datetime) -> int:
        """Acknowledge all unacknowledged alarms. Returns count."""
        async with self._db.execute(
            """UPDATE Log_Alarmes SET reconhecido = 1, reconhecido_por = ?, reconhecido_em = ?
               WHERE reconhecido = 0""",
            (username, ack_at.isoformat()),
        ) as cur:
            count = cur.rowcount
        await self._db.commit()
        return count

    async def get_active(
        self,
        controller_id: int | None = None,
        priority: str | None = None,
    ) -> list[dict]:
        """Return alarms that are still visible (not cleared+acked)."""
        sql = """SELECT id, controlador_id as controller_id, tipo_alarme as alarm_type,
                        prioridade as priority, valor as value, limite as limit_value,
                        timestamp as triggered_at, cleared_at,
                        reconhecido as acknowledged,
                        reconhecido_por as ack_by_user, reconhecido_em as ack_at
                 FROM Log_Alarmes
                 WHERE NOT (cleared_at IS NOT NULL AND reconhecido = 1)"""
        params: list = []
        if controller_id is not None:
            sql += " AND controlador_id = ?"
            params.append(controller_id)
        if priority is not None:
            sql += " AND prioridade = ?"
            params.append(priority)
        sql += " ORDER BY timestamp DESC"

        async with self._db.execute(sql, params) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def get_alarm_config(self, controller_id: int) -> list[dict]:
        """Return all alarm threshold configs for a controller."""
        async with self._db.execute(
            """SELECT id, controlador_id as controller_id, tipo_alarme as alarm_type,
                      prioridade as priority, limite as "limit", habilitado as enabled,
                      histerese as deadband, delay_on_s, delay_off_s
               FROM Configuracao_Alarmes WHERE controlador_id = ?
               ORDER BY tipo_alarme""",
            (controller_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def save_alarm_config(
        self,
        controller_id: int,
        thresholds: list[dict],
    ) -> None:
        """Replace all alarm thresholds for a controller (delete + insert)."""
        await self._db.execute(
            "DELETE FROM Configuracao_Alarmes WHERE controlador_id = ?",
            (controller_id,),
        )
        for t in thresholds:
            await self._db.execute(
                """INSERT INTO Configuracao_Alarmes
                   (controlador_id, tipo_alarme, prioridade, limite, habilitado,
                    histerese, delay_on_s, delay_off_s)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    controller_id,
                    t["alarm_type"],
                    t["priority"],
                    t["limit"],
                    1 if t.get("enabled", True) else 0,
                    t.get("deadband", 0.0),
                    t.get("delay_on_s", 0.0),
                    t.get("delay_off_s", 0.0),
                ),
            )
        await self._db.commit()

    async def get_history(
        self,
        start: datetime,
        end: datetime,
        controller_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Return alarm history in a time range."""
        sql = """SELECT id, controlador_id as controller_id, tipo_alarme as alarm_type,
                        prioridade as priority, valor as value, limite as limit_value,
                        timestamp as triggered_at, cleared_at,
                        reconhecido as acknowledged,
                        reconhecido_por as ack_by_user, reconhecido_em as ack_at
                 FROM Log_Alarmes
                 WHERE timestamp BETWEEN ? AND ?"""
        params: list = [start.isoformat(), end.isoformat()]
        if controller_id is not None:
            sql += " AND controlador_id = ?"
            params.append(controller_id)
        sql += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with self._db.execute(sql, params) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]
