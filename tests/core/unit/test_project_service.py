"""Tests for ProjectService with projects_dir."""
from __future__ import annotations

from unittest.mock import MagicMock

import aiosqlite
import pytest

from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.application.project_service import ProjectService


async def _make_archive(path, *, nome: str | None = None):
    """Write a minimal but genuine .spid archive at ``path`` and return it.

    Import validates its input, so tests can no longer hand it arbitrary bytes
    unless that is the thing under test.
    """
    async with aiosqlite.connect(path) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS Controladores "
            "(id INTEGER PRIMARY KEY, nome TEXT NOT NULL)"
        )
        if nome is not None:
            await db.execute(
                "CREATE TABLE IF NOT EXISTS Projeto_Meta "
                "(chave TEXT PRIMARY KEY, valor TEXT NOT NULL)"
            )
            await db.execute(
                "INSERT INTO Projeto_Meta (chave, valor) VALUES ('nome', ?)", (nome,)
            )
        await db.commit()
    return path


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
    src = await _make_archive(projects_dir.parent / "source.spid")

    result = await service.import_project("imported", src)
    assert result.name == "imported"
    assert (projects_dir / "imported.spid").exists()
    # Installed by move, not copy — the staging file is consumed.
    assert not src.exists()


@pytest.mark.asyncio
async def test_import_project_returns_requested_name_not_archive_name(
    service, projects_dir,
):
    """The archive remembers its old name; the response must not echo it."""
    src = await _make_archive(projects_dir.parent / "donor.spid", nome="donor-plant")

    result = await service.import_project("renamed", src)
    assert result.name == "renamed"
    assert (await service.get_current()).name == "renamed"


@pytest.mark.asyncio
async def test_import_project_rejects_non_sqlite_payload(service, projects_dir):
    junk = projects_dir.parent / "junk.spid"
    junk.write_bytes(b"not-a-db" * 64)
    with pytest.raises(ValueError, match="valid .spid"):
        await service.import_project("junk", junk)
    assert not (projects_dir / "junk.spid").exists()


@pytest.mark.asyncio
async def test_import_project_rejects_sqlite_without_project_schema(
    service, projects_dir,
):
    """A real database that is not a project must not become the active one."""
    foreign = projects_dir.parent / "foreign.spid"
    async with aiosqlite.connect(foreign) as db:
        await db.execute("CREATE TABLE Unrelated (id INTEGER PRIMARY KEY)")
        await db.commit()
    with pytest.raises(ValueError, match="valid .spid"):
        await service.import_project("foreign", foreign)
    assert not (projects_dir / "foreign.spid").exists()



@pytest.mark.asyncio
async def test_import_project_rejects_archive_the_daemon_cannot_read(
    service, projects_dir,
):
    """A project-shaped archive with the wrong column set must not install.

    This one bit for real: the table-exists check passed, the file was moved
    into place, the live repository was re-pointed at it, and only then did
    ``list_all()`` fail — leaving the daemon serving 500s with no way back.
    """
    stale = projects_dir.parent / "stale.spid"
    async with aiosqlite.connect(stale) as db:
        # Plausible, but missing every column added since it was written.
        await db.execute(
            "CREATE TABLE Controladores (id INTEGER PRIMARY KEY, nome TEXT NOT NULL)"
        )
        await db.execute("INSERT INTO Controladores (nome) VALUES ('LOOP-01')")
        await db.commit()

    with pytest.raises(ValueError, match="cannot be read"):
        await service.import_project("stale", stale)
    assert not (projects_dir / "stale.spid").exists()
    # The live project is untouched — the archive never became active.
    assert (await service.get_current()).name == "active"

@pytest.mark.asyncio
async def test_import_project_conflict(service, projects_dir):
    (projects_dir / "dup.spid").write_bytes(b"")
    src = await _make_archive(projects_dir.parent / "dupsrc.spid")
    with pytest.raises(FileExistsError):
        await service.import_project("dup", src)


@pytest.mark.asyncio
async def test_prepare_download(service, projects_dir):
    await service.new_project("dl_test")
    path = await service.prepare_download()
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


# --- Path traversal sanitization ---

_MALICIOUS_NAMES = [
    "../../etc/passwd",
    "..",
    ".",
    "../escape",
    "sub/dir/name",
    "name/../../escape",
    "/abs/path",
    "name\x00.spid",
    "a" * 200,  # too long
    "",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("name", _MALICIOUS_NAMES)
async def test_new_project_rejects_unsafe_name(service, projects_dir, name):
    with pytest.raises(ValueError):
        await service.new_project(name)
    # Nothing escaped the directory.
    escaped = projects_dir.parent.parent / "etc" / "passwd.spid"
    assert not escaped.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("name", _MALICIOUS_NAMES)
async def test_open_project_rejects_unsafe_name(service, name):
    with pytest.raises(ValueError):
        await service.open_project(name)


@pytest.mark.asyncio
@pytest.mark.parametrize("name", _MALICIOUS_NAMES)
async def test_import_project_rejects_unsafe_name(service, projects_dir, name):
    src = await _make_archive(projects_dir.parent / "unsafe-src.spid")
    with pytest.raises(ValueError):
        await service.import_project(name, src)
    escaped = projects_dir.parent.parent / "etc" / "passwd.spid"
    assert not escaped.exists()
    # The name is rejected before the archive is touched, so nothing is consumed.
    assert src.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("name", _MALICIOUS_NAMES)
async def test_delete_project_rejects_unsafe_name(service, projects_dir, name):
    victim = projects_dir.parent / "victim.spid"
    victim.write_bytes(b"keep me")
    with pytest.raises(ValueError):
        await service.delete_project(name)
    assert victim.exists()


@pytest.mark.asyncio
async def test_safe_name_with_spaces_and_dots_allowed(service, projects_dir):
    result = await service.new_project("My Project v1.2")
    assert result.name == "My Project v1.2"
    assert (projects_dir / "My Project v1.2.spid").exists()


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
    src = await _make_archive(projects_dir.parent / "imp.spid")

    await service_with_state.import_project("imp_state", src)
    assert daemon_state.active_project == "imp_state"
