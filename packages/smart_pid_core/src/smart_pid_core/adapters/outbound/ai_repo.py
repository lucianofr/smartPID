"""SQLite-backed repository for AI model metadata and tuning logs."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository


class AIRepository:
    """Persistence for AI model metadata and tuning action logs.

    Shares the aiosqlite.Connection owned by SQLiteRepository.
    """

    def __init__(self, repo: SQLiteRepository) -> None:
        self._repo = repo

    @property
    def _db(self):  # noqa: ANN202
        """Always return the current (possibly reopened) connection."""
        return self._repo.db

    async def save_model_metadata(
        self,
        controller_id: int,
        algorithm: str,
        episodes: int,
        avg_reward: float,
        model_path: str,
    ) -> int:
        """Save RL model metadata. Returns the row ID."""
        async with self._db.execute(
            "INSERT INTO Modelos_IA "
            "(controlador_id, algoritmo, episodios, reward_medio, caminho_modelo) "
            "VALUES (?, ?, ?, ?, ?)",
            (controller_id, algorithm, episodes, avg_reward, model_path),
        ) as cur:
            row_id = cur.lastrowid
        await self._db.commit()
        return row_id or 0

    async def get_latest_model(self, controller_id: int) -> dict | None:
        """Return the most recent model metadata for a controller."""
        async with self._db.execute(
            "SELECT id, controlador_id, algoritmo, episodios, reward_medio, "
            "caminho_modelo, criado_em "
            "FROM Modelos_IA WHERE controlador_id = ? ORDER BY criado_em DESC LIMIT 1",
            (controller_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return {
            "id": row[0],
            "controller_id": row[1],
            "algorithm": row[2],
            "episodes": row[3],
            "avg_reward": row[4],
            "model_path": row[5],
            "created_at": row[6],
        }

    async def log_tuning_action(
        self,
        controller_id: int,
        engine: str,
        old_ki: float,
        new_ki: float,
        objective: str,
        metric: float = 0.0,
    ) -> None:
        """Log a Ki adjustment in Log_Sintonia_IA.

        Args:
            controller_id: Controller ID (FK to Controladores).
            engine: AI engine name (e.g. "FUZZY", "RL").
            old_ki: Ki value before adjustment.
            new_ki: Ki value after adjustment.
            objective: Control objective name.
            metric: Computed metric value (e.g. gamma).
        """
        await self._db.execute(
            "INSERT INTO Log_Sintonia_IA "
            "(controlador_id, motor, ki_antes, ki_depois, objetivo, metrica, aprovado) "
            "VALUES (?, ?, ?, ?, ?, ?, 1)",
            (controller_id, engine, old_ki, new_ki, objective, metric),
        )
        await self._db.commit()

    async def get_last_ki(self, controller_id: int) -> float | None:
        """Return the most recent Ki/Ti value computed by AI for a controller."""
        async with self._db.execute(
            "SELECT ki_depois FROM Log_Sintonia_IA "
            "WHERE controlador_id = ? ORDER BY timestamp DESC LIMIT 1",
            (controller_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return float(row[0])

    async def get_tuning_history(
        self,
        controller_id: int,
        limit: int = 50,
    ) -> list[dict]:
        """Return recent tuning log entries."""
        async with self._db.execute(
            "SELECT id, controlador_id, timestamp, motor, ki_antes, ki_depois, "
            "objetivo, metrica, aprovado "
            "FROM Log_Sintonia_IA WHERE controlador_id = ? "
            "ORDER BY timestamp DESC LIMIT ?",
            (controller_id, limit),
        ) as cur:
            rows = await cur.fetchall()
        return [
            {
                "id": r[0],
                "controller_id": r[1],
                "timestamp": r[2],
                "engine": r[3],
                "ki_before": r[4],
                "ki_after": r[5],
                "objective": r[6],
                "metric": r[7],
                "approved": bool(r[8]),
            }
            for r in rows
        ]

    async def get_tuning_history_range(
        self,
        start: datetime,
        end: datetime,
        controller_id: int | None = None,
        limit: int = 500,
    ) -> list[dict]:
        """Return AI tuning log entries in a time range (all controllers)."""
        sql = (
            "SELECT a.id, a.controlador_id as controller_id, "
            "c.nome as controller_name, "
            "a.timestamp, a.motor as engine, "
            "a.ki_antes as ki_before, a.ki_depois as ki_after, "
            "a.objetivo as objective, a.metrica as metric "
            "FROM Log_Sintonia_IA a "
            "LEFT JOIN Controladores c ON c.id = a.controlador_id "
            "WHERE a.timestamp BETWEEN ? AND ?"
        )
        params: list = [start.isoformat(), end.isoformat()]
        if controller_id is not None:
            sql += " AND a.controlador_id = ?"
            params.append(controller_id)
        sql += " ORDER BY a.timestamp DESC LIMIT ?"
        params.append(limit)
        async with self._db.execute(sql, params) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]
