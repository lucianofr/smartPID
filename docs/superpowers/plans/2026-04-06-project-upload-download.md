# Project Upload/Download Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace filesystem-path-based project management with backend-managed directory + upload/download via REST, enabling HMI and backend to run on separate machines.

**Architecture:** Backend maintains a `projects_dir` directory with `.spid` files. HMI interacts only via REST (list, new, open by name, import via multipart upload, download via streaming GET). Welcome Dialog moves to post-login, sourcing project list from backend.

**Tech Stack:** FastAPI (multipart upload, FileResponse), httpx (streaming download), aiosqlite (read-only project scanning), PySide6 (QFileDialog for import/download only)

**Spec:** `docs/superpowers/specs/2026-04-06-project-upload-download-design.md`

---

## File Structure

### Domain (smart_pid_domain)
- **Modify:** `packages/smart_pid_domain/src/smart_pid_domain/dtos/project.py` — update DTOs

### Backend (smart_pid_core)
- **Modify:** `packages/smart_pid_core/src/smart_pid_core/config.py` — add `projects_dir`
- **Modify:** `packages/smart_pid_core/src/smart_pid_core/application/project_service.py` — rewrite for name-based ops
- **Modify:** `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/project.py` — new endpoints
- **Modify:** `packages/smart_pid_core/src/smart_pid_core/main.py` — pass `projects_dir` to service

### HMI (smart_pid_hmi)
- **Modify:** `packages/smart_pid_hmi/src/smart_pid_hmi/services/ports.py` — update protocol
- **Modify:** `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py` — new methods
- **Modify:** `packages/smart_pid_hmi/src/smart_pid_hmi/services/mock_service.py` — match protocol
- **Modify:** `packages/smart_pid_hmi/src/smart_pid_hmi/services/app_state.py` — simplify
- **Modify:** `packages/smart_pid_hmi/src/smart_pid_hmi/dialogs/welcome_dialog.py` — backend list
- **Modify:** `packages/smart_pid_hmi/src/smart_pid_hmi/pages/settings_page.py` — download/import
- **Modify:** `packages/smart_pid_hmi/src/smart_pid_hmi/main.py` — post-login flow

### Tests
- **Create:** `tests/core/unit/test_project_service.py`
- **Create:** `tests/core/integration/test_project_api.py`
- **Modify:** `tests/conftest.py` — adapt fixtures
- **Modify:** `tests/hmi/dialogs/test_welcome_dialog.py`
- **Modify:** `tests/hmi/pages/test_settings_page.py`
- **Modify:** Various integration tests that use project DTOs

---

## Task 1: Update Domain DTOs

**Files:**
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/dtos/project.py`
- Test: `tests/core/unit/test_project_dtos.py`

- [ ] **Step 1: Write failing test for new DTOs**

Create `tests/core/unit/test_project_dtos.py`:

```python
"""Tests for project DTOs."""
from smart_pid_domain.dtos.project import (
    ProjectCreate,
    ProjectListItem,
    ProjectListResponse,
    ProjectOpen,
    ProjectResponse,
)


def test_project_create_has_name_only():
    dto = ProjectCreate(name="elkem")
    assert dto.name == "elkem"
    assert not hasattr(dto, "path") or "path" not in dto.model_fields


def test_project_open_has_name():
    dto = ProjectOpen(name="elkem")
    assert dto.name == "elkem"


def test_project_list_item():
    item = ProjectListItem(name="elkem", controller_count=3, size_bytes=73728)
    assert item.name == "elkem"
    assert item.controller_count == 3
    assert item.size_bytes == 73728


def test_project_list_item_defaults():
    item = ProjectListItem(name="test")
    assert item.controller_count == 0
    assert item.size_bytes == 0


def test_project_list_response():
    resp = ProjectListResponse(
        projects=[
            ProjectListItem(name="a", controller_count=1, size_bytes=100),
            ProjectListItem(name="b"),
        ]
    )
    assert len(resp.projects) == 2
    assert resp.projects[0].name == "a"


def test_project_response():
    resp = ProjectResponse(name="elkem", path="elkem.spid", controller_count=3)
    assert resp.name == "elkem"
    assert resp.path == "elkem.spid"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/unit/test_project_dtos.py -v`
Expected: FAIL — `ProjectListItem` and `ProjectListResponse` not found; `ProjectCreate` still has `path`; `ProjectOpen` has `path` not `name`.

- [ ] **Step 3: Update DTOs**

Replace `packages/smart_pid_domain/src/smart_pid_domain/dtos/project.py` with:

```python
"""Project management DTOs."""
from __future__ import annotations

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    """Request to create a new project."""

    name: str


class ProjectOpen(BaseModel):
    """Request to open a project by name."""

    name: str


class ProjectListItem(BaseModel):
    """Single project in a list response."""

    name: str
    controller_count: int = 0
    size_bytes: int = 0


class ProjectListResponse(BaseModel):
    """List of available projects."""

    projects: list[ProjectListItem]


class ProjectResponse(BaseModel):
    """Project metadata response."""

    name: str
    path: str
    controller_count: int = 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/unit/test_project_dtos.py -v`
Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/dtos/project.py tests/core/unit/test_project_dtos.py
git commit -m "feat(domain): update project DTOs for upload/download — name-based, add list types"
```

---

## Task 2: Add `projects_dir` to CoreSettings

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/config.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/main.py`

- [ ] **Step 1: Write failing test**

Create `tests/core/unit/test_projects_dir_setting.py`:

```python
"""Test projects_dir setting."""
from pathlib import Path

from smart_pid_core.config import CoreSettings


def test_projects_dir_default():
    settings = CoreSettings(jwt_secret="test-secret-key-minimum-32-bytes!")
    assert settings.projects_dir == Path.home() / ".smart-pid" / "projects"


def test_projects_dir_override(monkeypatch):
    monkeypatch.setenv("SPID_PROJECTS_DIR", "/tmp/custom-projects")
    settings = CoreSettings(jwt_secret="test-secret-key-minimum-32-bytes!")
    assert settings.projects_dir == Path("/tmp/custom-projects")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/unit/test_projects_dir_setting.py -v`
Expected: FAIL — `projects_dir` not found on `CoreSettings`.

- [ ] **Step 3: Add `projects_dir` to CoreSettings**

In `packages/smart_pid_core/src/smart_pid_core/config.py`, add after `users_db_path`:

```python
    projects_dir: Path = Path.home() / ".smart-pid" / "projects"
```

- [ ] **Step 4: Ensure `projects_dir` is created on startup**

In `packages/smart_pid_core/src/smart_pid_core/main.py`, in `run_daemon()`, after `await repo.initialize()` (around line 170), add:

```python
    settings.projects_dir.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 5: Run tests to verify**

Run: `uv run pytest tests/core/unit/test_projects_dir_setting.py -v`
Expected: All 2 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/config.py packages/smart_pid_core/src/smart_pid_core/main.py tests/core/unit/test_projects_dir_setting.py
git commit -m "feat(core): add projects_dir setting with SPID_PROJECTS_DIR env var"
```

---

## Task 3: Rewrite ProjectService

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/application/project_service.py`
- Create: `tests/core/unit/test_project_service.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/main.py` (pass `projects_dir`)

- [ ] **Step 1: Write failing tests for `list_projects`**

Create `tests/core/unit/test_project_service.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/unit/test_project_service.py -v`
Expected: FAIL — `ProjectService.__init__` does not accept `projects_dir`.

- [ ] **Step 3: Write failing tests for `new_project` and `open_project`**

Append to `tests/core/unit/test_project_service.py`:

```python
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
    # Create a valid .spid
    path = projects_dir / "demo.spid"
    async with aiosqlite.connect(path) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS Controladores "
            "(id INTEGER PRIMARY KEY, nome TEXT NOT NULL)"
        )
        await db.execute("INSERT INTO Controladores (nome) VALUES (?)", ("c1",))
        await db.commit()
        await db.execute(
            "CREATE TABLE IF NOT EXISTS Metadados (chave TEXT PRIMARY KEY, valor TEXT)"
        )
        await db.execute(
            "INSERT OR REPLACE INTO Metadados (chave, valor) VALUES (?, ?)",
            ("nome", "Demo Project"),
        )
        await db.commit()

    result = await service.open_project("demo")
    assert result.name == "Demo Project"
    assert result.controller_count == 1


@pytest.mark.asyncio
async def test_open_project_not_found(service):
    with pytest.raises(FileNotFoundError):
        await service.open_project("nonexistent")
```

- [ ] **Step 4: Write failing tests for `import_project`, `download_path`, `delete_project`**

Append to `tests/core/unit/test_project_service.py`:

```python
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
```

- [ ] **Step 5: Run all tests to verify they fail**

Run: `uv run pytest tests/core/unit/test_project_service.py -v`
Expected: All FAIL — `ProjectService` API doesn't match.

- [ ] **Step 6: Rewrite ProjectService**

Replace `packages/smart_pid_core/src/smart_pid_core/application/project_service.py`:

```python
"""Project lifecycle orchestration — new, open, import, download, delete."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import aiosqlite

from smart_pid_domain.dtos.project import ProjectListItem, ProjectResponse

if TYPE_CHECKING:
    from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
    from smart_pid_core.application.loop_manager import LoopManager


class ProjectService:
    """Manages project files in a backend-controlled directory."""

    def __init__(
        self,
        repo: SQLiteRepository,
        loop_manager: LoopManager,
        projects_dir: Path,
        simulator_adapter: object | None = None,
    ) -> None:
        self._repo = repo
        self._loop_manager = loop_manager
        self._projects_dir = projects_dir
        self._simulator_adapter = simulator_adapter

    @property
    def projects_dir(self) -> Path:
        return self._projects_dir

    async def get_current(self) -> ProjectResponse:
        """Return metadata about the currently-open project."""
        name = await self._repo.get_meta("nome") or self._repo._db_path.stem
        controllers = await self._repo.list_all()
        return ProjectResponse(
            name=name,
            path=self._repo._db_path.name,
            controller_count=len(controllers),
        )

    async def list_projects(self) -> list[ProjectListItem]:
        """List all .spid files in the projects directory."""
        items: list[ProjectListItem] = []
        for spid in sorted(self._projects_dir.glob("*.spid")):
            count = 0
            try:
                async with aiosqlite.connect(spid) as db:
                    async with db.execute(
                        "SELECT COUNT(*) FROM Controladores"
                    ) as cur:
                        row = await cur.fetchone()
                        count = row[0] if row else 0
            except Exception:
                pass
            items.append(ProjectListItem(
                name=spid.stem,
                controller_count=count,
                size_bytes=spid.stat().st_size,
            ))
        return items

    async def new_project(self, name: str) -> ProjectResponse:
        """Create a new empty project in the projects directory."""
        dest = self._projects_dir / f"{name}.spid"
        if dest.exists():
            raise FileExistsError(f"Project '{name}' already exists")
        self._loop_manager.stop_all()
        self._stop_simulator()
        await self._repo.reopen(dest)
        await self._repo.set_meta("nome", name)
        return ProjectResponse(
            name=name,
            path=dest.name,
            controller_count=0,
        )

    async def open_project(self, name: str) -> ProjectResponse:
        """Open an existing project by name."""
        path = self._projects_dir / f"{name}.spid"
        if not path.exists():
            raise FileNotFoundError(f"Project '{name}' not found")
        self._loop_manager.stop_all()
        self._stop_simulator()
        await self._repo.reopen(path)
        await self._load_simulator_configs()
        return await self.get_current()

    async def import_project(self, name: str, data: bytes) -> ProjectResponse:
        """Import an uploaded .spid file into the projects directory."""
        dest = self._projects_dir / f"{name}.spid"
        if dest.exists():
            raise FileExistsError(f"Project '{name}' already exists")
        dest.write_bytes(data)
        self._loop_manager.stop_all()
        self._stop_simulator()
        await self._repo.reopen(dest)
        await self._load_simulator_configs()
        return await self.get_current()

    def download_path(self) -> Path:
        """Return the filesystem path of the active project for download."""
        return self._repo._db_path

    async def delete_project(self, name: str) -> None:
        """Delete a project file. Cannot delete the active project."""
        path = self._projects_dir / f"{name}.spid"
        if not path.exists():
            raise FileNotFoundError(f"Project '{name}' not found")
        if path == self._repo._db_path:
            raise ValueError(f"Cannot delete the active project '{name}'")
        path.unlink()

    def is_managed_project_active(self) -> bool:
        """Return True if the active project is inside the projects directory."""
        try:
            self._repo._db_path.resolve().relative_to(
                self._projects_dir.resolve()
            )
            return True
        except ValueError:
            return False

    async def _load_simulator_configs(self) -> None:
        """Restore simulator state from Configuracao_Simulador."""
        if self._simulator_adapter is None:
            return
        if not hasattr(self._simulator_adapter, "load_sim_config"):
            return
        configs = await self._repo.list_sim_configs()
        for cfg in configs:
            self._simulator_adapter.load_sim_config(cfg)

    def _stop_simulator(self) -> None:
        """Stop the simulator adapter if present."""
        if self._simulator_adapter is not None and hasattr(
            self._simulator_adapter, "stop"
        ):
            self._simulator_adapter.stop()
```

- [ ] **Step 7: Update `main.py` to pass `projects_dir`**

In `packages/smart_pid_core/src/smart_pid_core/main.py`, find the `ProjectService` construction (around line 286):

```python
    project_service = ProjectService(
        repo=repo,
        loop_manager=loop_manager,
        simulator_adapter=simulator_adapter,
    )
```

Change to:

```python
    project_service = ProjectService(
        repo=repo,
        loop_manager=loop_manager,
        projects_dir=settings.projects_dir,
        simulator_adapter=simulator_adapter,
    )
```

- [ ] **Step 8: Run project service tests**

Run: `uv run pytest tests/core/unit/test_project_service.py -v`
Expected: All 12 tests PASS.

- [ ] **Step 9: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/application/project_service.py packages/smart_pid_core/src/smart_pid_core/main.py tests/core/unit/test_project_service.py
git commit -m "feat(core): rewrite ProjectService for name-based project management"
```

---

## Task 4: Update Project REST API Endpoints

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/project.py`
- Create: `tests/core/integration/test_project_api.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Update `conftest.py` fixture to pass `projects_dir`**

In `tests/conftest.py`, find the `api_deps` fixture. Add after `repo` initialization:

```python
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()
```

And change the `ProjectService` construction to:

```python
    project_service = ProjectService(
        repo=repo, loop_manager=loop_manager, projects_dir=projects_dir,
    )
```

Do the same for the `sim_api_deps` fixture if it also creates a `ProjectService`.

Also update the yielded dict to include `projects_dir`:

```python
    yield {
        ...,
        "projects_dir": projects_dir,
    }
```

- [ ] **Step 2: Write failing test for `GET /project/list`**

Create `tests/core/integration/test_project_api.py`:

```python
"""Integration tests for project REST API endpoints."""
from __future__ import annotations

import aiosqlite
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_list_projects_empty(api_deps):
    app = api_deps["app"]
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/project/list")
        assert resp.status_code == 200
        data = resp.json()
        assert data["projects"] == []


@pytest.mark.asyncio
async def test_list_projects_with_files(api_deps):
    projects_dir = api_deps["projects_dir"]
    # Create a valid .spid
    path = projects_dir / "testproj.spid"
    async with aiosqlite.connect(path) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS Controladores "
            "(id INTEGER PRIMARY KEY, nome TEXT NOT NULL)"
        )
        await db.execute("INSERT INTO Controladores (nome) VALUES (?)", ("c1",))
        await db.commit()

    app = api_deps["app"]
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/project/list")
        assert resp.status_code == 200
        projects = resp.json()["projects"]
        assert len(projects) == 1
        assert projects[0]["name"] == "testproj"
        assert projects[0]["controller_count"] == 1


@pytest.mark.asyncio
async def test_new_project(api_deps):
    app = api_deps["app"]
    token = api_deps["token"]
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/project/new",
            json={"name": "newproj"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "newproj"
        assert data["path"] == "newproj.spid"


@pytest.mark.asyncio
async def test_new_project_conflict(api_deps):
    projects_dir = api_deps["projects_dir"]
    (projects_dir / "exists.spid").write_bytes(b"")
    app = api_deps["app"]
    token = api_deps["token"]
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/project/new",
            json={"name": "exists"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409


@pytest.mark.asyncio
async def test_open_project(api_deps):
    projects_dir = api_deps["projects_dir"]
    path = projects_dir / "openme.spid"
    async with aiosqlite.connect(path) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS Controladores "
            "(id INTEGER PRIMARY KEY, nome TEXT NOT NULL)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS Metadados "
            "(chave TEXT PRIMARY KEY, valor TEXT)"
        )
        await db.execute(
            "INSERT INTO Metadados (chave, valor) VALUES (?, ?)",
            ("nome", "OpenMe"),
        )
        await db.commit()

    app = api_deps["app"]
    token = api_deps["token"]
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/project/open",
            json={"name": "openme"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "OpenMe"


@pytest.mark.asyncio
async def test_open_project_not_found(api_deps):
    app = api_deps["app"]
    token = api_deps["token"]
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/project/open",
            json={"name": "ghost"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_import_project(api_deps, tmp_path):
    # Build a valid .spid to upload
    src = tmp_path / "upload.spid"
    async with aiosqlite.connect(src) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS Controladores "
            "(id INTEGER PRIMARY KEY, nome TEXT NOT NULL)"
        )
        await db.commit()
    file_bytes = src.read_bytes()

    app = api_deps["app"]
    token = api_deps["token"]
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/project/import",
            files={"file": ("upload.spid", file_bytes, "application/octet-stream")},
            data={"name": "uploaded"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "uploaded"


@pytest.mark.asyncio
async def test_download_project(api_deps):
    app = api_deps["app"]
    token = api_deps["token"]
    # First create a project so there's something to download
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.post(
            "/project/new",
            json={"name": "dltest"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = await client.get("/project/download")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/octet-stream"
        assert "dltest.spid" in resp.headers.get("content-disposition", "")
        assert len(resp.content) > 0


@pytest.mark.asyncio
async def test_delete_project(api_deps):
    projects_dir = api_deps["projects_dir"]
    (projects_dir / "removeme.spid").write_bytes(b"fake")
    app = api_deps["app"]
    token = api_deps["token"]
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.delete(
            "/project/removeme",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 204
        assert not (projects_dir / "removeme.spid").exists()


@pytest.mark.asyncio
async def test_delete_active_project_rejected(api_deps):
    app = api_deps["app"]
    token = api_deps["token"]
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Create and switch to a project
        await client.post(
            "/project/new",
            json={"name": "nodelete"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = await client.delete(
            "/project/nodelete",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/core/integration/test_project_api.py -v`
Expected: FAIL — endpoints don't exist yet or have wrong signatures.

- [ ] **Step 4: Rewrite project router**

Replace `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/project.py`:

```python
"""Project management REST API routes."""
from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse

from smart_pid_domain.dtos.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectOpen,
    ProjectResponse,
)

router = APIRouter()


@router.get("/current", response_model=ProjectResponse)
async def get_current(request: Request) -> ProjectResponse:
    """Return metadata about the currently-open project."""
    svc = request.app.state.project_service
    return await svc.get_current()


@router.get("/list", response_model=ProjectListResponse)
async def list_projects(request: Request) -> ProjectListResponse:
    """List all available projects in the backend directory."""
    svc = request.app.state.project_service
    items = await svc.list_projects()
    return ProjectListResponse(projects=items)


@router.post("/new", response_model=ProjectResponse)
async def new_project(body: ProjectCreate, request: Request) -> ProjectResponse:
    """Create a new empty project by name."""
    svc = request.app.state.project_service
    try:
        return await svc.new_project(body.name)
    except FileExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/open", response_model=ProjectResponse)
async def open_project(body: ProjectOpen, request: Request) -> ProjectResponse:
    """Open an existing project by name."""
    svc = request.app.state.project_service
    try:
        return await svc.open_project(body.name)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.post("/import", response_model=ProjectResponse)
async def import_project(
    request: Request,
    file: UploadFile,
    name: str = Form(default=""),
) -> ProjectResponse:
    """Upload a .spid file to the backend projects directory."""
    svc = request.app.state.project_service
    proj_name = name.strip() or (file.filename or "imported").removesuffix(".spid")
    data = await file.read()
    try:
        return await svc.import_project(proj_name, data)
    except FileExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc


@router.get("/download")
async def download_project(request: Request) -> FileResponse:
    """Download the active project as a .spid file."""
    svc = request.app.state.project_service
    path = svc.download_path()
    return FileResponse(
        path=str(path),
        filename=path.name,
        media_type="application/octet-stream",
    )


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(name: str, request: Request) -> None:
    """Delete a project file from the backend directory."""
    svc = request.app.state.project_service
    try:
        await svc.delete_project(name)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
```

- [ ] **Step 5: Run all project API tests**

Run: `uv run pytest tests/core/integration/test_project_api.py -v`
Expected: All 11 tests PASS.

- [ ] **Step 6: Run full test suite to check for regressions**

Run: `uv run pytest tests/ -x -k "not test_preset_changed_signal and not test_pid_apply_button and not test_controls_disabled and not test_controls_enabled and not test_enable_signal" --tb=short -q`
Expected: No new failures. Some existing tests that use old `ProjectCreate(name=..., path=...)` or `ProjectOpen(path=...)` may fail — fix them in next step.

- [ ] **Step 7: Fix any broken tests referencing old DTOs**

Search for tests using `ProjectCreate(name=..., path=...)`, `ProjectOpen(path=...)`, or `ProjectSaveAs`. Update them to use the new signatures. Common places:
- `tests/core/integration/test_audit_api.py`
- `tests/core/unit/test_commands_monitor_mode.py`
- `tests/core/unit/test_get_tuning_recommendations.py`

For each, change `ProjectService(repo=repo, loop_manager=loop_manager)` to `ProjectService(repo=repo, loop_manager=loop_manager, projects_dir=tmp_path / "projects")` and ensure the projects dir exists.

- [ ] **Step 8: Run full test suite again**

Run: `uv run pytest tests/ -x -k "not test_preset_changed_signal and not test_pid_apply_button and not test_controls_disabled and not test_controls_enabled and not test_enable_signal" --tb=short -q`
Expected: All pass (except pre-existing simulator page failures).

- [ ] **Step 9: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/project.py tests/core/integration/test_project_api.py tests/conftest.py
git add -u  # catch any fixed test files
git commit -m "feat(core): new project REST API — list, import, download, delete, name-based open/new"
```

---

## Task 5: Update HMI API Client and Protocol

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/services/ports.py`
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py`
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/services/mock_service.py`

- [ ] **Step 1: Update protocol**

In `packages/smart_pid_hmi/src/smart_pid_hmi/services/ports.py`, find the project management section and replace with:

```python
    # Project management
    def get_current_project(self) -> dict: ...
    def list_projects(self) -> list[dict]: ...
    def new_project(self, name: str) -> dict: ...
    def open_project(self, name: str) -> dict: ...
    def import_project(self, name: str, file_path: str) -> dict: ...
    def download_project(self, save_path: str) -> None: ...
    def delete_project(self, name: str) -> None: ...
```

- [ ] **Step 2: Update APIClient**

In `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py`, replace the project management section (after `get_current_project`):

```python
    # Project management

    def get_current_project(self) -> dict:
        resp = self._http.get("/project/current", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def list_projects(self) -> list[dict]:
        resp = self._http.get("/project/list", headers=self._headers())
        resp.raise_for_status()
        return resp.json().get("projects", [])

    def new_project(self, name: str) -> dict:
        resp = self._http.post(
            "/project/new", json={"name": name}, headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def open_project(self, name: str) -> dict:
        resp = self._http.post(
            "/project/open", json={"name": name}, headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def import_project(self, name: str, file_path: str) -> dict:
        with open(file_path, "rb") as f:
            resp = self._http.post(
                "/project/import",
                files={"file": (f.name, f, "application/octet-stream")},
                data={"name": name},
                headers=self._headers(),
            )
        resp.raise_for_status()
        return resp.json()

    def download_project(self, save_path: str) -> None:
        with self._http.stream("GET", "/project/download", headers=self._headers()) as resp:
            resp.raise_for_status()
            with open(save_path, "wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)

    def delete_project(self, name: str) -> None:
        resp = self._http.delete(
            f"/project/{name}", headers=self._headers(),
        )
        resp.raise_for_status()
```

- [ ] **Step 3: Update MockAPIClient**

In `packages/smart_pid_hmi/src/smart_pid_hmi/services/mock_service.py`, replace the project management section:

```python
    # Project management

    def get_current_project(self) -> dict:
        return {"name": "Mock Project", "path": "mock.spid", "controller_count": 2}

    def list_projects(self) -> list[dict]:
        return [
            {"name": "Mock Project", "controller_count": 2, "size_bytes": 1024},
            {"name": "Test Project", "controller_count": 0, "size_bytes": 512},
        ]

    def new_project(self, name: str) -> dict:
        return {"name": name, "path": f"{name}.spid", "controller_count": 0}

    def open_project(self, name: str) -> dict:
        return {"name": name, "path": f"{name}.spid", "controller_count": 0}

    def import_project(self, name: str, file_path: str) -> dict:
        return {"name": name, "path": f"{name}.spid", "controller_count": 0}

    def download_project(self, save_path: str) -> None:
        pass  # No-op in mock mode

    def delete_project(self, name: str) -> None:
        pass  # No-op in mock mode
```

- [ ] **Step 4: Run existing tests to check no regressions**

Run: `uv run pytest tests/ -x -k "not test_preset_changed_signal and not test_pid_apply_button and not test_controls_disabled and not test_controls_enabled and not test_enable_signal" --tb=short -q`
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/services/ports.py packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py packages/smart_pid_hmi/src/smart_pid_hmi/services/mock_service.py
git commit -m "feat(hmi): update API client for name-based project ops + upload/download"
```

---

## Task 6: Simplify AppStateManager

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/services/app_state.py`

- [ ] **Step 1: Write failing test**

Create `tests/hmi/test_app_state.py`:

```python
"""Tests for simplified AppStateManager."""
import json

import pytest

from smart_pid_hmi.services.app_state import AppStateManager


def test_default_state(tmp_path):
    mgr = AppStateManager(tmp_path / "state.json")
    assert mgr.last_project_name is None
    assert mgr.last_theme is None


def test_set_and_save(tmp_path):
    path = tmp_path / "state.json"
    mgr = AppStateManager(path)
    mgr.set_last_project_name("elkem")
    mgr.set_last_theme("dark_room")
    mgr.save()

    data = json.loads(path.read_text())
    assert data["last_project_name"] == "elkem"
    assert data["last_theme"] == "dark_room"
    assert "recent_projects" not in data
    assert "last_project" not in data


def test_load_existing(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({
        "last_project_name": "test",
        "last_theme": "ocean",
    }))
    mgr = AppStateManager(path)
    assert mgr.last_project_name == "test"
    assert mgr.last_theme == "ocean"


def test_load_migrates_old_format(tmp_path):
    """Old format with last_project (path) should be ignored gracefully."""
    path = tmp_path / "state.json"
    path.write_text(json.dumps({
        "last_project": "/old/path/project.spid",
        "recent_projects": [{"name": "x", "path": "/x", "controller_count": 0}],
        "last_theme": "isa101",
    }))
    mgr = AppStateManager(path)
    assert mgr.last_project_name is None  # old path-based field ignored
    assert mgr.last_theme == "isa101"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/hmi/test_app_state.py -v`
Expected: FAIL — `AppStateManager` has old API.

- [ ] **Step 3: Rewrite AppStateManager**

Replace `packages/smart_pid_hmi/src/smart_pid_hmi/services/app_state.py`:

```python
"""App-level state persistence — last project name, theme preference."""
from __future__ import annotations

import json
from pathlib import Path


class AppStateManager:
    """Manages ~/.config/smart-pid/app.json for cross-session state."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (Path.home() / ".config" / "smart-pid" / "app.json")
        self._last_project_name: str | None = None
        self._last_theme: str | None = None
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._last_project_name = data.get("last_project_name")
            self._last_theme = data.get("last_theme")
        except (json.JSONDecodeError, OSError):
            pass

    @property
    def last_project_name(self) -> str | None:
        return self._last_project_name

    @property
    def last_theme(self) -> str | None:
        return self._last_theme

    def set_last_project_name(self, name: str) -> None:
        self._last_project_name = name

    def set_last_theme(self, name: str) -> None:
        self._last_theme = name

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "last_project_name": self._last_project_name,
            "last_theme": self._last_theme,
        }
        self._path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8",
        )
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/hmi/test_app_state.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/services/app_state.py tests/hmi/test_app_state.py
git commit -m "feat(hmi): simplify AppStateManager — name-only, no recent list"
```

---

## Task 7: Redesign Welcome Dialog

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/dialogs/welcome_dialog.py`
- Modify: `tests/hmi/dialogs/test_welcome_dialog.py`

- [ ] **Step 1: Write failing tests**

Create/replace `tests/hmi/dialogs/test_welcome_dialog.py`:

```python
"""Tests for redesigned WelcomeDialog."""
import pytest
from PySide6.QtWidgets import QListWidget, QPushButton

from smart_pid_hmi.dialogs.welcome_dialog import WelcomeDialog


@pytest.fixture
def projects():
    return [
        {"name": "alpha", "controller_count": 3, "size_bytes": 1024},
        {"name": "beta", "controller_count": 0, "size_bytes": 512},
    ]


def test_creation(qtbot, projects):
    dlg = WelcomeDialog(projects=projects)
    qtbot.addWidget(dlg)
    assert dlg.windowTitle() == "Smart PID Edge Optimizer"


def test_project_list_populated(qtbot, projects):
    dlg = WelcomeDialog(projects=projects)
    qtbot.addWidget(dlg)
    list_widget = dlg.findChild(QListWidget, "project_list")
    assert list_widget is not None
    assert list_widget.count() == 2


def test_new_button_exists(qtbot, projects):
    dlg = WelcomeDialog(projects=projects)
    qtbot.addWidget(dlg)
    btn = dlg.findChild(QPushButton, "welcome_new_btn")
    assert btn is not None


def test_import_button_exists(qtbot, projects):
    dlg = WelcomeDialog(projects=projects)
    qtbot.addWidget(dlg)
    btn = dlg.findChild(QPushButton, "welcome_import_btn")
    assert btn is not None


def test_delete_button_exists(qtbot, projects):
    dlg = WelcomeDialog(projects=projects)
    qtbot.addWidget(dlg)
    btn = dlg.findChild(QPushButton, "welcome_delete_btn")
    assert btn is not None


def test_no_open_file_button(qtbot, projects):
    """Old 'Open Project' (QFileDialog) button should not exist."""
    dlg = WelcomeDialog(projects=projects)
    qtbot.addWidget(dlg)
    btn = dlg.findChild(QPushButton, "welcome_open_btn")
    assert btn is None


def test_empty_project_list(qtbot):
    dlg = WelcomeDialog(projects=[])
    qtbot.addWidget(dlg)
    list_widget = dlg.findChild(QListWidget, "project_list")
    assert list_widget.count() == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/hmi/dialogs/test_welcome_dialog.py -v`
Expected: FAIL — old `WelcomeDialog` has `recent_projects` param, not `projects`.

- [ ] **Step 3: Rewrite WelcomeDialog**

Replace `packages/smart_pid_hmi/src/smart_pid_hmi/dialogs/welcome_dialog.py`:

```python
"""WelcomeDialog — project selection shown after login."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class _NameInputDialog(QDialog):
    """Themed input dialog for project name."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.setModal(True)
        self.setMinimumWidth(320)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Project name:"))
        self._input = QLineEdit()
        self._input.setObjectName("name_input")
        layout.addWidget(self._input)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

    @property
    def text(self) -> str:
        return self._input.text()


class WelcomeDialog(QDialog):
    """Modal dialog for project selection — shown after login."""

    def __init__(
        self,
        projects: list[dict] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Smart PID Edge Optimizer")
        self.setModal(True)
        self.setMinimumSize(420, 400)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        self.result_action: str | None = None  # "new", "open", "import"
        self.result_name: str | None = None  # project name (new/open)
        self.result_path: str | None = None  # local file path (import only)

        self._projects = list(projects or [])

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Title
        title = QLabel("\u2699 Smart PID Edge Optimizer")
        title.setObjectName("welcome_title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setProperty("heading", True)
        layout.addWidget(title)

        subtitle = QLabel("Project Management")
        subtitle.setObjectName("welcome_subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setProperty("muted", True)
        layout.addWidget(subtitle)

        # Buttons
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(8)

        new_btn = QPushButton("New Project")
        new_btn.setObjectName("welcome_new_btn")
        new_btn.setMinimumHeight(40)
        new_btn.clicked.connect(self._on_new)
        btn_layout.addWidget(new_btn)

        import_btn = QPushButton("Import from File (.spid)")
        import_btn.setObjectName("welcome_import_btn")
        import_btn.setMinimumHeight(40)
        import_btn.clicked.connect(self._on_import)
        btn_layout.addWidget(import_btn)

        layout.addLayout(btn_layout)

        # Available projects from backend
        available_label = QLabel("AVAILABLE PROJECTS")
        available_label.setObjectName("welcome_available_label")
        available_label.setProperty("muted", True)
        layout.addWidget(available_label)

        self._project_list = QListWidget()
        self._project_list.setObjectName("project_list")
        self._project_list.itemDoubleClicked.connect(self._on_project_selected)
        self._populate_list()
        layout.addWidget(self._project_list)

        # Delete button
        delete_row = QHBoxLayout()
        delete_row.addStretch()
        delete_btn = QPushButton("Delete Selected")
        delete_btn.setObjectName("welcome_delete_btn")
        delete_btn.clicked.connect(self._on_delete)
        delete_row.addWidget(delete_btn)
        layout.addLayout(delete_row)

    def _populate_list(self) -> None:
        self._project_list.clear()
        for proj in self._projects:
            count = proj.get("controller_count", 0)
            name = proj["name"]
            item = QListWidgetItem(f"{name}  ({count} loops)")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self._project_list.addItem(item)

    def set_projects(self, projects: list[dict]) -> None:
        """Update the project list (e.g. after a delete)."""
        self._projects = list(projects)
        self._populate_list()

    def _on_new(self) -> None:
        dlg = _NameInputDialog(parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.text.strip():
            return
        self.result_action = "new"
        self.result_name = dlg.text.strip()
        self.accept()

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Project", "", "Smart PID Project (*.spid)",
        )
        if not path:
            return
        self.result_action = "import"
        self.result_path = path
        # Use filename stem as default name
        from pathlib import Path as P
        self.result_name = P(path).stem
        self.accept()

    def _on_project_selected(self, item: QListWidgetItem) -> None:
        name = item.data(Qt.ItemDataRole.UserRole)
        if name:
            self.result_action = "open"
            self.result_name = name
            self.accept()

    def _on_delete(self) -> None:
        item = self._project_list.currentItem()
        if item is None:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        if name:
            self.result_action = "delete"
            self.result_name = name
            # Don't accept — caller handles delete and refreshes list
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/hmi/dialogs/test_welcome_dialog.py -v`
Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/dialogs/welcome_dialog.py tests/hmi/dialogs/test_welcome_dialog.py
git commit -m "feat(hmi): redesign WelcomeDialog — backend project list, import, delete"
```

---

## Task 8: Update Settings Page

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/pages/settings_page.py`
- Modify: `tests/hmi/pages/test_settings_page.py`

- [ ] **Step 1: Write failing tests for new buttons/signals**

Add to `tests/hmi/pages/test_settings_page.py`:

```python
def test_download_button_exists(qtbot, theme):
    from smart_pid_hmi.themes.manager import ThemeManager
    tm = ThemeManager()
    tm.register(theme)
    page = SettingsPage(theme_manager=tm)
    qtbot.addWidget(page)
    btn = page.findChild(QPushButton, "project_download_btn")
    assert btn is not None


def test_import_button_exists(qtbot, theme):
    from smart_pid_hmi.themes.manager import ThemeManager
    tm = ThemeManager()
    tm.register(theme)
    page = SettingsPage(theme_manager=tm)
    qtbot.addWidget(page)
    btn = page.findChild(QPushButton, "project_import_btn")
    assert btn is not None


def test_no_save_as_button(qtbot, theme):
    from smart_pid_hmi.themes.manager import ThemeManager
    tm = ThemeManager()
    tm.register(theme)
    page = SettingsPage(theme_manager=tm)
    qtbot.addWidget(page)
    btn = page.findChild(QPushButton, "project_save_as_btn")
    assert btn is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/hmi/pages/test_settings_page.py -v -k "download or import or save_as"`
Expected: FAIL — download/import buttons don't exist, save_as still exists.

- [ ] **Step 3: Update Settings page project section**

In `packages/smart_pid_hmi/src/smart_pid_hmi/pages/settings_page.py`:

Replace the signals section — remove `project_save_as_requested`, add new ones:

```python
    # Project signals (immediate — not affected by Apply/Cancel)
    project_changed = Signal(str, str)  # (name, path)
    project_new_requested = Signal()  # open Welcome Dialog
    project_open_requested = Signal()  # open Welcome Dialog
    project_download_requested = Signal()
    project_import_requested = Signal()
```

Replace the project buttons section (New, Open, Save As) with:

```python
        proj_btn_row = QHBoxLayout()

        self._project_new_btn = QPushButton("New")
        self._project_new_btn.setObjectName("project_new_btn")
        self._project_new_btn.clicked.connect(lambda: self.project_new_requested.emit())
        proj_btn_row.addWidget(self._project_new_btn)

        self._project_open_btn = QPushButton("Open")
        self._project_open_btn.setObjectName("project_open_btn")
        self._project_open_btn.clicked.connect(lambda: self.project_open_requested.emit())
        proj_btn_row.addWidget(self._project_open_btn)

        self._project_download_btn = QPushButton("Download")
        self._project_download_btn.setObjectName("project_download_btn")
        self._project_download_btn.clicked.connect(lambda: self.project_download_requested.emit())
        proj_btn_row.addWidget(self._project_download_btn)

        proj_btn_row2 = QHBoxLayout()
        self._project_import_btn = QPushButton("Import")
        self._project_import_btn.setObjectName("project_import_btn")
        self._project_import_btn.clicked.connect(lambda: self.project_import_requested.emit())
        proj_btn_row2.addWidget(self._project_import_btn)
        proj_btn_row2.addStretch()

        proj_btn_row.addStretch()
        project_form.addRow(proj_btn_row)
        project_form.addRow(proj_btn_row2)
```

Remove old methods `_on_project_new`, `_on_project_open`, `_on_project_save_as` since the Settings page no longer handles file dialogs — MainWindow does.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/hmi/pages/test_settings_page.py -v`
Expected: All PASS (new button tests pass, old save_as test passes because button is gone).

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/pages/settings_page.py tests/hmi/pages/test_settings_page.py
git commit -m "feat(hmi): Settings page — Download/Import buttons replace Save As"
```

---

## Task 9: Rewire MainWindow — Post-Login Project Flow

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/main.py`

This is the largest and most critical task. It replaces the pre-login Welcome Dialog and pending project mechanism with a post-login flow that queries the backend.

- [ ] **Step 1: Remove pending project fields and old signal connections**

In `MainWindow.__init__`, remove:
```python
        self._pending_project_action: str | None = None
        self._pending_project_path: str | None = None
        self._pending_project_name: str | None = None
```

Update signal connections — replace old project signal connections:
```python
        self._settings_page.project_new_requested.connect(self._show_project_dialog)
        self._settings_page.project_open_requested.connect(self._show_project_dialog)
        self._settings_page.project_download_requested.connect(self._on_project_download)
        self._settings_page.project_import_requested.connect(self._show_project_dialog)
```

Remove the old connections to `_on_project_new`, `_on_project_open`, `_on_project_save_as`.

- [ ] **Step 2: Rewrite `_login_success` — post-login project detection**

Replace the `_login_success` method. After the standard login setup (telemetry, dashboard, etc.), check if backend has a managed project active:

```python
    @Slot()
    def _login_success(self) -> None:
        self._conn_indicator.setStyleSheet(
            "color: #00C853; background: transparent;"
            " font-size: 18px; padding: 0 4px;"
        )
        self._set_active_nav(self._dashboard_nav)
        self._user_label.setText(self._session.username or "")
        self._telemetry_source.start()
        self._bus_bridge.start()
        self._stack.setCurrentWidget(self._dashboard_page)
        self._check_simulator_available()
        self._show_admin_controls()
        self._alarm_panel.load_active_alarms()
        self._kpi_timer.start(30_000)

        # Check if backend has a managed project active
        QTimer.singleShot(500, self._check_active_project)
```

- [ ] **Step 3: Implement `_check_active_project`**

Add this method to MainWindow:

```python
    @Slot()
    def _check_active_project(self) -> None:
        """After login, check if backend has a project active in projects_dir."""
        try:
            current = self._api_client.get_current_project()
            path = current.get("path", "")
            name = current.get("name", "")
            count = current.get("controller_count", 0)
            self._settings_page.update_project_info(name, path, count)

            # If the project is managed (not the scratch default), proceed
            # The scratch default has path "project.spid" (relative, in cwd)
            if path != "project.spid":
                self._app_state.set_last_project_name(name)
                self._app_state.save()
                self._load_dashboard()
                return
        except Exception as e:
            print(f"[PROJECT CHECK] Error: {e}")  # noqa: T201

        # No managed project — show Welcome Dialog
        self._show_project_dialog()
```

- [ ] **Step 4: Implement `_show_project_dialog`**

```python
    def _show_project_dialog(self) -> None:
        """Show the Welcome Dialog with projects from backend."""
        from smart_pid_hmi.dialogs.welcome_dialog import WelcomeDialog

        try:
            projects = self._api_client.list_projects()
        except Exception:
            projects = []

        dialog = WelcomeDialog(projects=projects, parent=self)
        while True:
            result = dialog.exec()
            if result != QDialog.DialogCode.Accepted:
                # Handle delete action (dialog doesn't accept on delete)
                if dialog.result_action == "delete" and dialog.result_name:
                    self._handle_project_delete(dialog)
                    continue
                break

            action = dialog.result_action
            if action == "new" and dialog.result_name:
                self._handle_project_new(dialog.result_name)
                break
            elif action == "open" and dialog.result_name:
                self._handle_project_open(dialog.result_name)
                break
            elif action == "import" and dialog.result_path:
                name = dialog.result_name or ""
                self._handle_project_import(name, dialog.result_path)
                break
```

- [ ] **Step 5: Implement project action handlers**

```python
    def _handle_project_new(self, name: str) -> None:
        """Create a new project on the backend."""
        def do_new():
            try:
                result = self._api_client.new_project(name)
                self._app_state.set_last_project_name(result["name"])
                self._app_state.save()
                self._project_info_signal.emit(
                    result["name"], result["path"],
                    int(result.get("controller_count", 0)),
                )
                self._load_dashboard()
            except Exception as e:
                self._api_error_signal.emit(str(e))

        threading.Thread(target=do_new, daemon=True).start()

    def _handle_project_open(self, name: str) -> None:
        """Open an existing project on the backend."""
        def do_open():
            try:
                result = self._api_client.open_project(name)
                self._app_state.set_last_project_name(result["name"])
                self._app_state.save()
                self._project_info_signal.emit(
                    result["name"], result["path"],
                    int(result.get("controller_count", 0)),
                )
                self._load_dashboard()
            except Exception as e:
                self._api_error_signal.emit(str(e))

        threading.Thread(target=do_open, daemon=True).start()

    def _handle_project_import(self, name: str, file_path: str) -> None:
        """Upload a .spid file to the backend."""
        def do_import():
            try:
                result = self._api_client.import_project(name, file_path)
                self._app_state.set_last_project_name(result["name"])
                self._app_state.save()
                self._project_info_signal.emit(
                    result["name"], result["path"],
                    int(result.get("controller_count", 0)),
                )
                self._load_dashboard()
            except Exception as e:
                self._api_error_signal.emit(str(e))

        threading.Thread(target=do_import, daemon=True).start()

    def _handle_project_delete(self, dialog) -> None:
        """Delete a project and refresh the dialog list."""
        name = dialog.result_name
        try:
            self._api_client.delete_project(name)
            projects = self._api_client.list_projects()
            dialog.set_projects(projects)
            dialog.result_action = None
            dialog.result_name = None
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(dialog, "Error", str(e))

    def _on_project_download(self) -> None:
        """Download the active project to a local file."""
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self, "Download Project", "", "Smart PID Project (*.spid)",
        )
        if not path:
            return
        if not path.endswith(".spid"):
            path += ".spid"

        def do_download():
            try:
                self._api_client.download_project(path)
            except Exception as e:
                self._api_error_signal.emit(str(e))

        threading.Thread(target=do_download, daemon=True).start()
```

- [ ] **Step 6: Update `main()` function — remove pre-login Welcome Dialog**

Replace the `main()` function startup logic:

```python
def main() -> None:
    """Entry point for the HMI application."""
    settings = HMISettings()
    session = Session()

    if settings.mock_mode:
        from smart_pid_hmi.services.mock_service import MockAPIClient, MockTelemetrySource

        api_client = MockAPIClient()
        telemetry_source = MockTelemetrySource()
    else:
        from smart_pid_hmi.services.api_client import APIClient
        from smart_pid_hmi.services.telemetry_sub import TelemetrySub

        api_client = APIClient(base_url=settings.server_url, session=session)
        telemetry_source = TelemetrySub(zmq_url=settings.zmq_url)

    bus_bridge = BusBridge(queue=telemetry_source.queue, refresh_ms=settings.refresh_ms)

    app = QApplication(sys.argv)
    window = MainWindow(
        settings=settings,
        session=session,
        api_client=api_client,
        telemetry_source=telemetry_source,
        bus_bridge=bus_bridge,
    )

    window.show()
    sys.exit(app.exec())
```

Remove the entire pre-login Welcome Dialog block and `_pending_project_*` setup. The Welcome Dialog is now shown post-login inside `_check_active_project`.

- [ ] **Step 7: Remove old project methods**

Remove these methods from MainWindow:
- `_on_project_new(self, name, path)` — replaced by `_handle_project_new(name)`
- `_do_new_project(self, name, path)` — replaced by `_handle_project_new(name)`
- `_on_project_open(self, path)` — replaced by `_handle_project_open(name)`
- `_do_open_project(self, path)` — replaced by `_handle_project_open(name)`
- `_on_project_save_as(self, path)` — replaced by `_on_project_download()`
- `_refresh_project_info()` — replaced by `_check_active_project()`
- `_on_project_info_received()` — keep this, still used by `_project_info_signal`

Also remove unused imports: `Path` (if no longer needed), `QDialog` (if not imported elsewhere — check first).

- [ ] **Step 8: Ensure `QDialog` import is present**

`_show_project_dialog` uses `QDialog.DialogCode.Accepted`. Make sure `QDialog` is imported at the top of `main.py`:

```python
from PySide6.QtWidgets import QDialog
```

Add it to the existing import block if not already present.

- [ ] **Step 9: Run full test suite**

Run: `uv run pytest tests/ -x -k "not test_preset_changed_signal and not test_pid_apply_button and not test_controls_disabled and not test_controls_enabled and not test_enable_signal" --tb=short -q`
Expected: All pass (except pre-existing simulator page failures).

- [ ] **Step 10: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/main.py
git commit -m "feat(hmi): post-login project flow — Welcome Dialog from backend, upload/download"
```

---

## Task 10: Update CLAUDE.md and Final Integration Test

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/superpowers/specs/2026-04-06-project-upload-download-design.md` (mark as implemented)

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v -k "not test_preset_changed_signal and not test_pid_apply_button and not test_controls_disabled and not test_controls_enabled and not test_enable_signal"`
Expected: All pass.

- [ ] **Step 2: Run lint**

Run: `uv run --with ruff ruff check .`
Fix any issues.

- [ ] **Step 3: Update CLAUDE.md communication section**

In `CLAUDE.md`, update the communication section to reflect that:
- Project management uses upload/download via REST (not filesystem paths)
- `SPID_PROJECTS_DIR` env var added
- Welcome Dialog is shown post-login

- [ ] **Step 4: Mark spec as implemented**

In `docs/superpowers/specs/2026-04-06-project-upload-download-design.md`, change:
```
**Status:** Approved
```
to:
```
**Status:** Implemented
```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md docs/superpowers/specs/2026-04-06-project-upload-download-design.md
git commit -m "docs: mark project upload/download as implemented, update CLAUDE.md"
```

- [ ] **Step 6: Run full test suite one final time**

Run: `uv run pytest tests/ -v`
Expected: All pass except pre-existing simulator page failures.
