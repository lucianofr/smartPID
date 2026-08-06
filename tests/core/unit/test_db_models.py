"""db_models must mirror the bootstrapped schema column-for-column."""
from __future__ import annotations

import aiosqlite  # raw probe — fixture/probing use stays raw per spec §10
import pytest

from smart_pid_core.adapters.outbound.db_models import SpidBase, UsersBase
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.adapters.outbound.user_repo import UserRepository


class TestModelSchemaParity:
    @pytest.mark.asyncio
    async def test_spid_models_match_bootstrapped_schema(self, tmp_path) -> None:
        db_path = tmp_path / "t.spid"
        repo = SQLiteRepository(db_path)
        await repo.initialize()  # runs _DDL + _apply_migrations
        await repo.close()
        async with aiosqlite.connect(db_path) as db:
            for table in SpidBase.metadata.sorted_tables:
                async with db.execute(f"PRAGMA table_info({table.name})") as cur:
                    db_cols = {r[1] for r in await cur.fetchall()}
                model_cols = {c.name for c in table.columns}
                assert db_cols, f"table {table.name} missing from bootstrap"
                assert model_cols == db_cols, (
                    f"{table.name} drift: only-in-model={model_cols - db_cols} "
                    f"only-in-db={db_cols - model_cols}"
                )

    @pytest.mark.asyncio
    async def test_users_model_matches_bootstrapped_schema(self, tmp_path) -> None:
        db_path = tmp_path / "users.db"
        urepo = UserRepository(db_path)
        await urepo.initialize()
        await urepo.close()
        async with (
            aiosqlite.connect(db_path) as db,
            db.execute("PRAGMA table_info(Usuarios)") as cur,
        ):
            db_cols = {r[1] for r in await cur.fetchall()}
        table = UsersBase.metadata.tables["Usuarios"]
        assert {c.name for c in table.columns} == db_cols

    def test_expected_table_names(self) -> None:
        assert set(SpidBase.metadata.tables) == {
            "Controladores", "Configuracao_Alarmes", "Log_Processo",
            "Log_Sintonia_IA", "Log_Auditoria", "Modelos_IA", "Log_Alarmes",
            "Projeto_Meta", "Log_System_Events", "Configuracao_Simulador",
        }
        assert set(UsersBase.metadata.tables) == {"Usuarios"}
