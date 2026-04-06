"""Tests for Projeto_Meta and Configuracao_Simulador tables."""
from __future__ import annotations

import pytest

from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository


@pytest.fixture
async def repo(tmp_path):
    """Create a fresh SQLiteRepository for each test."""
    db_path = tmp_path / "test.spid"
    r = SQLiteRepository(db_path)
    await r.initialize()
    yield r
    await r.close()


# ── Projeto_Meta ──────────────────────────────────────────────────────


class TestProjetoMeta:
    async def test_table_exists(self, repo: SQLiteRepository) -> None:
        tables = await repo._get_table_names()
        assert "Projeto_Meta" in tables

    async def test_set_and_get_meta(self, repo: SQLiteRepository) -> None:
        await repo.set_meta("nome", "My Project")
        value = await repo.get_meta("nome")
        assert value == "My Project"

    async def test_get_meta_missing_returns_none(self, repo: SQLiteRepository) -> None:
        value = await repo.get_meta("nonexistent")
        assert value is None

    async def test_set_meta_upserts(self, repo: SQLiteRepository) -> None:
        await repo.set_meta("nome", "First")
        await repo.set_meta("nome", "Second")
        value = await repo.get_meta("nome")
        assert value == "Second"


# ── Configuracao_Simulador ────────────────────────────────────────────


class TestConfiguracaoSimulador:
    async def test_table_exists(self, repo: SQLiteRepository) -> None:
        tables = await repo._get_table_names()
        assert "Configuracao_Simulador" in tables

    async def test_save_and_get_sim_config(self, repo: SQLiteRepository) -> None:
        await repo.save_sim_config(
            controller_id=1, preset="fopdt_default",
            gain=2.0, tau1=10.0, tau2=0.0, dead_time=3.0,
        )
        cfg = await repo.get_sim_config(1)
        assert cfg is not None
        assert cfg["preset"] == "fopdt_default"
        assert cfg["gain"] == 2.0
        assert cfg["tau1"] == 10.0
        assert cfg["tau2"] == 0.0
        assert cfg["dead_time"] == 3.0

    async def test_get_sim_config_missing_returns_none(self, repo: SQLiteRepository) -> None:
        cfg = await repo.get_sim_config(999)
        assert cfg is None

    async def test_save_sim_config_upserts(self, repo: SQLiteRepository) -> None:
        await repo.save_sim_config(
            controller_id=1, preset="fopdt_default",
            gain=2.0, tau1=10.0, tau2=0.0, dead_time=3.0,
        )
        await repo.save_sim_config(
            controller_id=1, preset="sopdt_tank",
            gain=5.0, tau1=20.0, tau2=5.0, dead_time=1.0,
        )
        cfg = await repo.get_sim_config(1)
        assert cfg is not None
        assert cfg["preset"] == "sopdt_tank"
        assert cfg["gain"] == 5.0

    async def test_list_sim_configs(self, repo: SQLiteRepository) -> None:
        await repo.save_sim_config(
            controller_id=1, preset="a", gain=1.0, tau1=1.0, tau2=0.0, dead_time=1.0,
        )
        await repo.save_sim_config(
            controller_id=2, preset="b", gain=2.0, tau1=2.0, tau2=0.0, dead_time=2.0,
        )
        configs = await repo.list_sim_configs()
        assert len(configs) == 2

    async def test_list_sim_configs_empty(self, repo: SQLiteRepository) -> None:
        configs = await repo.list_sim_configs()
        assert configs == []


# ── reopen ────────────────────────────────────────────────────────────


class TestReopen:
    async def test_reopen_switches_database(self, repo: SQLiteRepository, tmp_path) -> None:
        await repo.set_meta("nome", "Original")
        new_path = tmp_path / "new.spid"
        await repo.reopen(new_path)
        # New DB should not have the old meta
        value = await repo.get_meta("nome")
        assert value is None
        # But tables should exist
        tables = await repo._get_table_names()
        assert "Projeto_Meta" in tables

    async def test_reopen_old_db_intact(self, repo: SQLiteRepository, tmp_path) -> None:
        old_path = repo._db_path
        await repo.set_meta("nome", "Original")
        new_path = tmp_path / "new.spid"
        await repo.reopen(new_path)
        # Reopen old DB to verify data persisted
        await repo.reopen(old_path)
        value = await repo.get_meta("nome")
        assert value == "Original"
