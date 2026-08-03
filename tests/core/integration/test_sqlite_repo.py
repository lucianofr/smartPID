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
        saved_copy = Controller(id=saved.id, name="TIC-101", description="New", scan_rate_s=0.5)
        await repo.save(saved_copy)
        loaded = await repo.get(saved.id)
        assert loaded.description == "New"
        assert loaded.scan_rate_s == 0.5

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



class TestForeignKeysStayInert:
    """spec §10: foreign_keys OFF — ON DELETE CASCADE in the DDL must not fire."""

    @pytest.mark.asyncio
    async def test_orphan_child_insert_allowed(self, repo) -> None:
        from sqlalchemy import text

        async with repo.session_factory() as session:
            await session.execute(
                text(
                    "INSERT INTO Configuracao_Alarmes"
                    " (controlador_id, tipo_alarme, prioridade, limite)"
                    " VALUES (:cid, 'HI', 'WARNING', 90.0)"
                ),
                {"cid": 424242},  # no such controller — must NOT raise
            )
            await session.commit()

    @pytest.mark.asyncio
    async def test_delete_controller_clears_its_alarm_config(self, repo) -> None:
        """The alarm config must NOT outlive its controller.

        SQLite hands out ``max(id) + 1``, so the next controller created
        after a delete can land on the freed id and inherit the dead loop's
        limits. That is exactly how a brand-new FIC-101 with nothing
        configured started announcing a HI alarm at 80.
        """
        from sqlalchemy import text

        saved = await repo.save(Controller(id=0, name="TIC-900"))
        async with repo.session_factory() as session:
            await session.execute(
                text(
                    "INSERT INTO Configuracao_Alarmes"
                    " (controlador_id, tipo_alarme, prioridade, limite)"
                    " VALUES (:cid, 'HI', 'WARNING', 90.0)"
                ),
                {"cid": saved.id},
            )
            await session.commit()
        await repo.delete(saved.id)
        async with repo.session_factory() as session:
            count = (
                await session.execute(
                    text("SELECT COUNT(*) FROM Configuracao_Alarmes WHERE controlador_id = :cid"),
                    {"cid": saved.id},
                )
            ).scalar()
        assert count == 0

    @pytest.mark.asyncio
    async def test_delete_controller_closes_its_open_alarms(self, repo) -> None:
        """History is kept, but nothing is left standing.

        An un-cleared row for a deleted loop would be re-seeded as an
        active alarm on the next daemon start, lighting the banner for a
        loop that no longer exists.
        """
        from sqlalchemy import text

        saved = await repo.save(Controller(id=0, name="TIC-901"))
        async with repo.session_factory() as session:
            await session.execute(
                text(
                    "INSERT INTO Log_Alarmes"
                    " (controlador_id, tipo_alarme, prioridade, valor, limite,"
                    "  reconhecido)"
                    " VALUES (:cid, 'HI', 'WARNING', 95.0, 90.0, 0)"
                ),
                {"cid": saved.id},
            )
            await session.commit()
        await repo.delete(saved.id)
        async with repo.session_factory() as session:
            rows = (
                await session.execute(
                    text(
                        "SELECT cleared_at FROM Log_Alarmes"
                        " WHERE controlador_id = :cid"
                    ),
                    {"cid": saved.id},
                )
            ).scalars().all()
        assert len(rows) == 1, "history must survive the delete"
        assert rows[0] is not None, "no alarm may be left open"


class TestSystemEventSeverityVocabulary:
    """The event log has to accept every severity the HMI can filter for.

    The original CHECK allowed CRITICAL/WARNING/INFO only. The optimizer
    records its suggestions at LOG and the history panel offers a LOG
    filter, so those inserts failed on a background task and the panel
    filtered for rows the database had been refusing all along.
    """

    @pytest.mark.asyncio
    async def test_every_hmi_severity_can_be_stored(self, repo) -> None:
        from smart_pid_core.adapters.outbound.system_event_repo import (
            SystemEventRepository,
        )

        events = SystemEventRepository(repo.session_factory)
        for severity in ("CRITICAL", "WARNING", "ADVISORY", "INFO", "LOG"):
            await events.insert_event("AI", severity, f"probe {severity}")

        from datetime import UTC, datetime, timedelta
        now = datetime.now(UTC)
        rows = await events.get_history(
            start=now - timedelta(hours=1), end=now + timedelta(hours=1),
        )
        assert {r["severity"] for r in rows} == {
            "CRITICAL", "WARNING", "ADVISORY", "INFO", "LOG",
        }

    @pytest.mark.asyncio
    async def test_a_legacy_narrow_check_is_widened_on_open(self, tmp_path) -> None:
        """A .spid created before the fix must be migrated, not left broken."""
        import aiosqlite

        from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
        from smart_pid_core.adapters.outbound.system_event_repo import (
            SystemEventRepository,
        )

        path = tmp_path / "legacy.spid"
        async with aiosqlite.connect(path) as db:
            await db.execute(
                """CREATE TABLE Log_System_Events (
                       id        INTEGER PRIMARY KEY AUTOINCREMENT,
                       timestamp TEXT NOT NULL DEFAULT (datetime('now')),
                       source    TEXT NOT NULL,
                       severity  TEXT NOT NULL
                                 CHECK(severity IN ('CRITICAL','WARNING','INFO')),
                       message   TEXT NOT NULL
                   )"""
            )
            await db.execute(
                "INSERT INTO Log_System_Events (source, severity, message)"
                " VALUES ('BACKEND', 'INFO', 'pre-existing row')"
            )
            await db.commit()

        repo = SQLiteRepository(path)
        await repo.initialize()
        try:
            events = SystemEventRepository(repo.session_factory)
            await events.insert_event("AI", "LOG", "sintonia sugerida")

            from datetime import UTC, datetime, timedelta
            now = datetime.now(UTC)
            rows = await events.get_history(
                start=now - timedelta(days=2), end=now + timedelta(hours=1),
            )
            messages = {r["message"] for r in rows}
            assert "sintonia sugerida" in messages
            assert "pre-existing row" in messages, "history must survive the rebuild"
        finally:
            await repo.close()
