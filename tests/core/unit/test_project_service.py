"""Tests for ProjectService — project lifecycle orchestration."""
from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from smart_pid_core.application.project_service import ProjectService
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository


@pytest.fixture
async def repo(tmp_path: Path):
    db_path = tmp_path / "test.spid"
    r = SQLiteRepository(db_path)
    await r.initialize()
    yield r
    await r.close()


@pytest.fixture
def loop_manager():
    lm = MagicMock()
    lm.stop_all = MagicMock()
    return lm


@pytest.fixture
def simulator_adapter():
    sa = MagicMock()
    sa.stop = MagicMock()
    return sa


@pytest.fixture
def service(repo, loop_manager, simulator_adapter):
    return ProjectService(
        repo=repo, loop_manager=loop_manager,
        simulator_adapter=simulator_adapter,
    )


class TestGetCurrent:
    async def test_empty_project(self, service: ProjectService) -> None:
        resp = await service.get_current()
        assert resp.controller_count == 0

    async def test_returns_name_from_meta(
        self, service: ProjectService, repo: SQLiteRepository,
    ) -> None:
        await repo.set_meta("nome", "My Project")
        resp = await service.get_current()
        assert resp.name == "My Project"

    async def test_returns_db_path(self, service: ProjectService, repo: SQLiteRepository) -> None:
        resp = await service.get_current()
        assert resp.path == str(repo._db_path)


class TestNewProject:
    async def test_creates_file_and_returns_response(
        self, service: ProjectService, tmp_path: Path,
    ) -> None:
        new_path = tmp_path / "new_project.spid"
        resp = await service.new_project("New Project", new_path)
        assert resp.name == "New Project"
        assert resp.path == str(new_path)
        assert resp.controller_count == 0
        assert new_path.exists()

    async def test_calls_stop_all(
        self, service: ProjectService, loop_manager, tmp_path: Path,
    ) -> None:
        new_path = tmp_path / "new.spid"
        await service.new_project("X", new_path)
        loop_manager.stop_all.assert_called_once()

    async def test_stores_meta(
        self, service: ProjectService, repo: SQLiteRepository, tmp_path: Path,
    ) -> None:
        new_path = tmp_path / "meta.spid"
        await service.new_project("Meta Test", new_path)
        assert await repo.get_meta("nome") == "Meta Test"
        assert await repo.get_meta("criado_em") is not None

    async def test_stops_simulator(
        self, service: ProjectService, simulator_adapter, tmp_path: Path,
    ) -> None:
        new_path = tmp_path / "sim.spid"
        await service.new_project("X", new_path)
        simulator_adapter.stop.assert_called_once()


class TestOpenProject:
    async def test_opens_existing_file(
        self, service: ProjectService, tmp_path: Path,
    ) -> None:
        # Create a valid .spid file first
        existing = tmp_path / "existing.spid"
        prep = SQLiteRepository(existing)
        await prep.initialize()
        await prep.set_meta("nome", "Existing")
        await prep.close()

        resp = await service.open_project(existing)
        assert resp.name == "Existing"
        assert resp.path == str(existing)

    async def test_raises_for_missing_file(self, service: ProjectService, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.spid"
        with pytest.raises(FileNotFoundError):
            await service.open_project(missing)

    async def test_calls_stop_all(
        self, service: ProjectService, loop_manager, tmp_path: Path,
    ) -> None:
        existing = tmp_path / "stop.spid"
        prep = SQLiteRepository(existing)
        await prep.initialize()
        await prep.close()

        await service.open_project(existing)
        loop_manager.stop_all.assert_called_once()

    async def test_stops_simulator(
        self, service: ProjectService, simulator_adapter, tmp_path: Path,
    ) -> None:
        existing = tmp_path / "sim_open.spid"
        prep = SQLiteRepository(existing)
        await prep.initialize()
        await prep.close()

        await service.open_project(existing)
        simulator_adapter.stop.assert_called_once()


class TestSaveAs:
    async def test_copies_and_returns_response(
        self, service: ProjectService, repo: SQLiteRepository, tmp_path: Path,
    ) -> None:
        await repo.set_meta("nome", "Original")
        dest = tmp_path / "copy.spid"
        resp = await service.save_as(dest)
        assert resp.path == str(dest)
        assert dest.exists()

    async def test_does_not_call_stop_all(
        self, service: ProjectService, loop_manager, tmp_path: Path,
    ) -> None:
        dest = tmp_path / "no_stop.spid"
        await service.save_as(dest)
        loop_manager.stop_all.assert_not_called()

    async def test_does_not_stop_simulator(
        self, service: ProjectService, simulator_adapter, tmp_path: Path,
    ) -> None:
        dest = tmp_path / "no_sim_stop.spid"
        await service.save_as(dest)
        simulator_adapter.stop.assert_not_called()
