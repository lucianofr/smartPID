"""Tests for ProjectService with projects_dir."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import aiosqlite
import pytest

from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.application.project_service import ProjectService


@pytest.fixture
async def projects_dir(tmp_path):
    d = tmp_path / "projects"
    d.mkdir()
    return d


@pytest.fixture
async def repo(tmp_path):
    db_path = tmp_path / "active.spid"
    r = SQLiteRepository(db_path)
    await r.initialize()
    return r


@pytest.fixture
def loop_manager():
    lm = MagicMock()
    lm.stop_all = MagicMock()
    return lm


@pytest.fixture
def service(repo, loop_manager, projects_dir):
    return ProjectService(
        repo=repo,
        loop_manager=loop_manager,
        projects_dir=projects_dir,
    )


@pytest.mark.asyncio
async def test_list_projects_empty(service):
    result = await service.list_projects()
    assert result == []


@pytest.mark.asyncio
async def test_list_projects_finds_spid_files(service, projects_dir):
    # Create two .spid files with proper schema
    for name in ("alpha", "beta"):
        path = projects_dir / f"{name}.spid"
        async with aiosqlite.connect(path) as db:
            await db.execute(
                "CREATE TABLE IF NOT EXISTS Controladores "
                "(id INTEGER PRIMARY KEY, nome TEXT NOT NULL)"
            )
            if name == "alpha":
                await db.execute(
                    "INSERT INTO Controladores (nome) VALUES (?)", ("ctrl1",)
                )
            await db.commit()

    result = await service.list_projects()
    names = {p.name for p in result}
    assert names == {"alpha", "beta"}
    alpha = next(p for p in result if p.name == "alpha")
    assert alpha.controller_count == 1
    beta = next(p for p in result if p.name == "beta")
    assert beta.controller_count == 0


@pytest.mark.asyncio
async def test_list_projects_ignores_non_spid(service, projects_dir):
    (projects_dir / "readme.txt").write_text("hello")
    result = await service.list_projects()
    assert result == []


@pytest.mark.asyncio
async def test_new_project_creates_file(service, projects_dir):
    result = await service.new_project("myproj")
    assert result.name == "myproj"
    assert result.path == "myproj.spid"
    assert (projects_dir / "myproj.spid").exists()


@pytest.mark.asyncio
async def test_new_project_conflict(service, projects_dir):
    (projects_dir / "existing.spid").write_bytes(b"")
    with pytest.raises(FileExistsError):
        await service.new_project("existing")


@pytest.mark.asyncio
async def test_open_project_by_name(service, projects_dir):
    # Create a valid .spid using the real repo to get correct schema
    path = projects_dir / "demo.spid"
    prep_repo = SQLiteRepository(path)
    await prep_repo.initialize()
    await prep_repo.set_meta("nome", "Demo Project")
    await prep_repo.close()

    result = await service.open_project("demo")
    assert result.name == "Demo Project"
    assert result.controller_count == 0


@pytest.mark.asyncio
async def test_open_project_not_found(service):
    with pytest.raises(FileNotFoundError):
        await service.open_project("nonexistent")


@pytest.mark.asyncio
async def test_import_project(service, projects_dir):
    # Create a valid .spid in memory
    src = projects_dir.parent / "source.spid"
    async with aiosqlite.connect(src) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS Controladores "
            "(id INTEGER PRIMARY KEY, nome TEXT NOT NULL)"
        )
        await db.commit()
    data = src.read_bytes()

    result = await service.import_project("imported", data)
    assert result.name == "imported"
    assert (projects_dir / "imported.spid").exists()


@pytest.mark.asyncio
async def test_import_project_conflict(service, projects_dir):
    (projects_dir / "dup.spid").write_bytes(b"")
    with pytest.raises(FileExistsError):
        await service.import_project("dup", b"data")


@pytest.mark.asyncio
async def test_download_path(service, projects_dir):
    await service.new_project("dl_test")
    path = service.download_path()
    assert path.exists()
    assert path.name == "dl_test.spid"


@pytest.mark.asyncio
async def test_delete_project(service, projects_dir):
    # Create a project file (not the active one)
    path = projects_dir / "todelete.spid"
    path.write_bytes(b"fake")
    await service.delete_project("todelete")
    assert not path.exists()


@pytest.mark.asyncio
async def test_delete_active_project_rejected(service, projects_dir):
    await service.new_project("active_one")
    with pytest.raises(ValueError, match="active"):
        await service.delete_project("active_one")


@pytest.mark.asyncio
async def test_delete_nonexistent(service):
    with pytest.raises(FileNotFoundError):
        await service.delete_project("ghost")


# --- DaemonState integration tests ---


@pytest.fixture
def daemon_state(tmp_path):
    from smart_pid_core.application.daemon_state import DaemonState
    return DaemonState(tmp_path / "daemon_state.json")


@pytest.fixture
def service_with_state(repo, loop_manager, projects_dir, daemon_state):
    return ProjectService(
        repo=repo,
        loop_manager=loop_manager,
        projects_dir=projects_dir,
        daemon_state=daemon_state,
    )


@pytest.mark.asyncio
async def test_new_project_saves_daemon_state(service_with_state, daemon_state):
    await service_with_state.new_project("stateful")
    assert daemon_state.active_project == "stateful"


@pytest.mark.asyncio
async def test_open_project_saves_daemon_state(
    service_with_state, projects_dir, daemon_state,
):
    path = projects_dir / "demo2.spid"
    prep_repo = SQLiteRepository(path)
    await prep_repo.initialize()
    await prep_repo.set_meta("nome", "Demo2")
    await prep_repo.close()

    await service_with_state.open_project("demo2")
    assert daemon_state.active_project == "demo2"


@pytest.mark.asyncio
async def test_import_project_saves_daemon_state(
    service_with_state, projects_dir, daemon_state,
):
    import aiosqlite as _aiosqlite

    src = projects_dir.parent / "imp.spid"
    async with _aiosqlite.connect(src) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS Controladores "
            "(id INTEGER PRIMARY KEY, nome TEXT NOT NULL)"
        )
        await db.commit()

    await service_with_state.import_project("imp_state", src.read_bytes())
    assert daemon_state.active_project == "imp_state"
