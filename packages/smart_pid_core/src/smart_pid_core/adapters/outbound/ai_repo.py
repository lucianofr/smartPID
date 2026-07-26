"""SQLite-backed repository for AI model metadata and tuning logs."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class AIRepository:
    """Persistence for AI model metadata and tuning action logs.

    Bound to the injected .spid session factory (engine A).
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save_model_metadata(
        self,
        controller_id: int,
        algorithm: str,
        episodes: int,
        avg_reward: float,
        model_path: str,
    ) -> int:
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    "INSERT INTO Modelos_IA "
                    "(controlador_id, algoritmo, episodios, reward_medio, caminho_modelo) "
                    "VALUES (:cid, :algo, :eps, :reward, :path)"
                ),
                {"cid": controller_id, "algo": algorithm, "eps": episodes,
                 "reward": avg_reward, "path": model_path},
            )
            row_id = result.lastrowid
            await session.commit()
        return row_id or 0

    async def get_latest_model(self, controller_id: int) -> dict | None:
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT id, controlador_id, algoritmo, episodios, reward_medio, "
                    "caminho_modelo, criado_em "
                    "FROM Modelos_IA WHERE controlador_id = :cid "
                    "ORDER BY criado_em DESC LIMIT 1"
                ),
                {"cid": controller_id},
            )
            row = result.first()
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
        async with self._session_factory() as session:
            await session.execute(
                text(
                    "INSERT INTO Log_Sintonia_IA "
                    "(controlador_id, motor, ki_antes, ki_depois, objetivo, metrica, aprovado) "
                    "VALUES (:cid, :motor, :old, :new, :obj, :metric, 1)"
                ),
                {"cid": controller_id, "motor": engine, "old": old_ki,
                 "new": new_ki, "obj": objective, "metric": metric},
            )
            await session.commit()

    async def get_last_ki(self, controller_id: int) -> float | None:
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT ki_depois FROM Log_Sintonia_IA "
                    "WHERE controlador_id = :cid ORDER BY timestamp DESC LIMIT 1"
                ),
                {"cid": controller_id},
            )
            row = result.first()
        if row is None:
            return None
        return float(row[0])

    async def get_tuning_history(
        self,
        controller_id: int,
        limit: int = 50,
    ) -> list[dict]:
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT id, controlador_id, timestamp, motor, ki_antes, ki_depois, "
                    "objetivo, metrica, aprovado "
                    "FROM Log_Sintonia_IA WHERE controlador_id = :cid "
                    "ORDER BY timestamp DESC LIMIT :limit"
                ),
                {"cid": controller_id, "limit": limit},
            )
            rows = result.all()
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
        sql = (
            "SELECT a.id, a.controlador_id as controller_id, "
            "c.nome as controller_name, "
            "a.timestamp, a.motor as engine, "
            "a.ki_antes as ki_before, a.ki_depois as ki_after, "
            "a.objetivo as objective, a.metrica as metric "
            "FROM Log_Sintonia_IA a "
            "LEFT JOIN Controladores c ON c.id = a.controlador_id "
            "WHERE a.timestamp BETWEEN :start AND :end"
        )
        params: dict = {"start": start.isoformat(), "end": end.isoformat()}
        if controller_id is not None:
            sql += " AND a.controlador_id = :cid"
            params["cid"] = controller_id
        sql += " ORDER BY a.timestamp DESC LIMIT :limit"
        params["limit"] = limit
        async with self._session_factory() as session:
            result = await session.execute(text(sql), params)
            rows = result.mappings().all()
        return [dict(r) for r in rows]
