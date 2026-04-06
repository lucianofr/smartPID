from __future__ import annotations

import pytest

from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_domain.models.controller import Controller


@pytest.fixture
async def repo(tmp_path):
    db_path = tmp_path / "test.spid"
    repo = SQLiteRepository(db_path)
    await repo.initialize()
    return repo


class TestSQLiteRepository:
    @pytest.mark.asyncio
    async def test_initialize_creates_tables(self, repo) -> None:
        tables = await repo._get_table_names()
        assert "Controladores" in tables
        assert "Log_Processo" in tables
        assert "Log_Alarmes" in tables
        assert "Log_Sintonia_IA" in tables
        assert "Log_Auditoria" in tables
        assert "Configuracao_Alarmes" in tables
        # Usuarios table moved to standalone users.db (UserRepository)

    @pytest.mark.asyncio
    async def test_save_and_get_controller(self, repo) -> None:
        ctrl = Controller(id=0, name="TIC-101", description="Temperature loop")
        saved = await repo.save(ctrl)
        assert saved.id > 0
        loaded = await repo.get(saved.id)
        assert loaded.name == "TIC-101"
        assert loaded.description == "Temperature loop"

    @pytest.mark.asyncio
    async def test_list_all_controllers(self, repo) -> None:
        await repo.save(Controller(id=0, name="TIC-101"))
        await repo.save(Controller(id=0, name="FIC-201"))
        controllers = await repo.list_all()
        assert len(controllers) == 2
        names = {c.name for c in controllers}
        assert names == {"TIC-101", "FIC-201"}

    @pytest.mark.asyncio
    async def test_update_controller(self, repo) -> None:
        ctrl = Controller(id=0, name="TIC-101", description="Old")
        saved = await repo.save(ctrl)
        saved_copy = Controller(id=saved.id, name="TIC-101", description="New", scan_rate_ms=500)
        await repo.save(saved_copy)
        loaded = await repo.get(saved.id)
        assert loaded.description == "New"
        assert loaded.scan_rate_ms == 500

    @pytest.mark.asyncio
    async def test_delete_controller(self, repo) -> None:
        ctrl = Controller(id=0, name="TIC-101")
        saved = await repo.save(ctrl)
        await repo.delete(saved.id)
        with pytest.raises(KeyError):
            await repo.get(saved.id)

    @pytest.mark.asyncio
    async def test_get_nonexistent_raises(self, repo) -> None:
        with pytest.raises(KeyError):
            await repo.get(9999)

    @pytest.mark.asyncio
    async def test_wal_mode_enabled(self, repo) -> None:
        mode = await repo._get_journal_mode()
        assert mode == "wal"

class TestModeBindingRoundTrip:
    """TagBindings mode target/actual + int map are persisted and loaded."""

    @pytest.mark.asyncio
    async def test_save_and_load_mode_bindings(self, repo):
        from smart_pid_domain.models.controller import Controller, TagBindings

        ctrl = Controller(
            name="MODE-TEST",
            tag_bindings=TagBindings(
                node_id_pv="ns=2;s=PV",
                node_id_mode_target="ns=2;s=MODE_TGT",
                node_id_mode_actual="ns=2;s=MODE_ACT",
                mode_int_map={"MAN": 1, "AUTO": 2, "CAS": 4},
            ),
        )
        saved = await repo.save(ctrl)
        loaded = await repo.get(saved.id)

        assert loaded.tag_bindings.node_id_mode_target == "ns=2;s=MODE_TGT"
        assert loaded.tag_bindings.node_id_mode_actual == "ns=2;s=MODE_ACT"
        assert loaded.tag_bindings.mode_int_map == {"MAN": 1, "AUTO": 2, "CAS": 4}

    @pytest.mark.asyncio
    async def test_empty_mode_int_map_default(self, repo):
        from smart_pid_domain.models.controller import Controller

        ctrl = Controller(name="NO-MAP-TEST")
        saved = await repo.save(ctrl)
        loaded = await repo.get(saved.id)

        assert loaded.tag_bindings.node_id_mode_target == ""
        assert loaded.tag_bindings.node_id_mode_actual == ""
        assert loaded.tag_bindings.mode_int_map == {}

