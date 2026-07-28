"""spec §10 .spid lifecycle guarantees: reopen drain, download checkpoint, busy-timeout."""
from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import aiosqlite  # raw probes on bare files/copies — file format, not data layer
import msgpack
import pytest
from sqlalchemy import text

from smart_pid_core.adapters.outbound.db_engine import create_sqlite_engine
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.project_service import ProjectService
from smart_pid_core.application.workers.db_worker import DBWorker
from smart_pid_domain.models.controller import Controller


@pytest.fixture
async def projects_dir(tmp_path):
    d = tmp_path / "projects"
    d.mkdir()
    return d


@pytest.fixture
async def repo(tmp_path):
    r = SQLiteRepository(tmp_path / "active.spid")
    await r.initialize()
    yield r
    await r.close()


@pytest.fixture
def loop_manager():
    lm = MagicMock()
    lm.stop_all = MagicMock()
    return lm


@pytest.fixture
def service(repo, loop_manager, projects_dir):
    return ProjectService(repo=repo, loop_manager=loop_manager, projects_dir=projects_dir)


class TestReopenDrain:
    @pytest.mark.asyncio
    async def test_switch_away_releases_all_handles_then_delete(
        self, service, projects_dir,
    ) -> None:
        """open → write → switch away: no -wal/-shm sibling survives; delete works."""
        await service.new_project("alpha")
        alpha = projects_dir / "alpha.spid"
        # generate WAL traffic on engine A
        await service._repo.save(Controller(id=0, name="TIC-101"))
        await service.new_project("beta")  # checkpoint + dispose alpha engines
        assert not Path(str(alpha) + "-wal").exists()
        assert not Path(str(alpha) + "-shm").exists()
        await service.delete_project("alpha")
        assert not alpha.exists()

    @pytest.mark.asyncio
    async def test_reopened_file_contains_pre_switch_writes(
        self, service, projects_dir,
    ) -> None:
        """Nothing written before the switch may be stranded in a discarded WAL."""
        await service.new_project("gamma")
        saved = await service._repo.save(Controller(id=0, name="FIC-201"))
        await service.new_project("delta")
        gamma = projects_dir / "gamma.spid"
        async with aiosqlite.connect(gamma) as db:  # the bare file, no live engine
            async with db.execute(
                "SELECT nome FROM Controladores WHERE id = ?", (saved.id,)
            ) as cur:
                row = await cur.fetchone()
        assert row is not None and row[0] == "FIC-201"


class TestDownloadCheckpoint:
    @pytest.mark.asyncio
    async def test_prepare_download_truncates_wal(self, service, repo) -> None:
        for i in range(50):
            await repo.save(Controller(id=0, name=f"LIC-{i:03d}"))
        wal = Path(str(repo.db_path) + "-wal")
        assert wal.exists() and wal.stat().st_size > 0  # WAL has content pre-checkpoint
        path = await service.prepare_download()
        assert path == repo.db_path
        assert wal.stat().st_size == 0  # TRUNCATE folded the WAL into the main file

    @pytest.mark.asyncio
    async def test_downloaded_copy_is_complete_without_wal(
        self, service, repo, tmp_path,
    ) -> None:
        for i in range(20):
            await repo.save(Controller(id=0, name=f"PIC-{i:03d}"))
        path = await service.prepare_download()
        copy = tmp_path / "downloaded.spid"
        copy.write_bytes(path.read_bytes())  # what FileResponse streams: the file ALONE
        async with aiosqlite.connect(copy) as db:
            async with db.execute("SELECT COUNT(*) FROM Controladores") as cur:
                row = await cur.fetchone()
        assert row[0] == 20


class TestBusyTimeout:
    @pytest.mark.asyncio
    async def test_second_writer_waits_instead_of_failing(self, repo) -> None:
        """Two engines on one .spid (the A/B shape): busy_timeout absorbs contention."""
        engine_b = create_sqlite_engine(repo.db_path)

        async def hold_write_lock() -> None:
            async with repo.engine.begin() as conn:
                await conn.execute(
                    text("INSERT INTO Projeto_Meta (chave, valor) VALUES ('locka', '1')"),
                )
                await asyncio.sleep(0.3)  # keep the write txn open

        holder = asyncio.create_task(hold_write_lock())
        await asyncio.sleep(0.05)  # lock is now held by engine A
        # would raise 'database is locked' with busy_timeout=0
        async with engine_b.begin() as conn:
            await conn.execute(
                text("INSERT INTO Projeto_Meta (chave, valor) VALUES ('lockb', '2')"),
            )
        await holder
        async with engine_b.connect() as conn:
            n = (
                await conn.execute(
                    text("SELECT COUNT(*) FROM Projeto_Meta WHERE chave IN ('locka','lockb')"),
                )
            ).scalar()
        assert n == 2
        await engine_b.dispose()


class TestDBWorkerAcrossSwitch:
    @pytest.mark.asyncio
    async def test_project_switch_restarts_worker_onto_new_file(
        self, repo, loop_manager, projects_dir,
    ) -> None:
        """Frames published after a switch land in the NEW project via a fresh engine B."""
        bus = EventBus(url_prefix=f"inproc://test_{uuid.uuid4().hex[:8]}")
        bus.start()
        worker = DBWorker(bus=bus, repo=repo, flush_interval_s=0.1)
        worker.start()
        service = ProjectService(
            repo=repo, loop_manager=loop_manager,
            projects_dir=projects_dir, db_worker=worker,
        )
        try:
            await service.new_project("fresh")  # drains worker, reopens, restarts worker
            pub = bus.create_publisher()
            time.sleep(0.05)
            frame = {
                "controller_id": 7, "pv": 61.0, "sp": 60.0, "co": 31.0,
                "integral_val": 0.5, "timestamp": "2026-07-26T12:00:00+00:00",
                "status": "GOOD",
            }
            pub.send(b"TELEMETRY.7", msgpack.packb(frame))
            time.sleep(0.3)  # worker flush interval + margin
            async with repo.session_factory() as session:
                n = (
                    await session.execute(
                        text("SELECT COUNT(*) FROM Log_Processo WHERE controlador_id = 7"),
                    )
                ).scalar()
            assert n == 1
        finally:
            worker.stop()
            bus.stop()
