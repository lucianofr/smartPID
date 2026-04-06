# Project Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add project lifecycle management (New/Open/Save As) with backend-centric orchestration, welcome dialog, app-level user DB separation, and Apply/Cancel pattern for Settings and Simulator pages.

**Architecture:** Backend-centric — a new `ProjectService` orchestrates project transitions (stop loops, close DB, create/open/copy `.spid`). HMI manages app state (`app.json`) and presents project UI in Settings page + welcome dialog. Users move to a separate app-level SQLite DB.

**Tech Stack:** Python 3.13, FastAPI, aiosqlite, PySide6, pydantic v2, pydantic-settings, pytest + pytest-asyncio, httpx

**Spec:** `docs/superpowers/specs/2026-04-06-project-management-design.md`

---

### Task 1: Add `users_db_path` to CoreSettings

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/config.py`
- Test: `tests/core/unit/test_config_users_db.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/core/unit/test_config_users_db.py
"""Tests for CoreSettings.users_db_path."""
from __future__ import annotations

from pathlib import Path

import pytest

from smart_pid_core.config import CoreSettings


class TestUsersDbPath:
    def test_default_users_db_path(self) -> None:
        settings = CoreSettings(jwt_secret="test-secret-key-minimum-32-bytes!")
        expected = Path.home() / ".config" / "smart-pid" / "users.db"
        assert settings.users_db_path == expected

    def test_custom_users_db_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SPID_USERS_DB_PATH", "/tmp/custom_users.db")
        settings = CoreSettings(jwt_secret="test-secret-key-minimum-32-bytes!")
        assert settings.users_db_path == Path("/tmp/custom_users.db")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/unit/test_config_users_db.py -v`
Expected: FAIL with `AttributeError: 'CoreSettings' object has no attribute 'users_db_path'`

- [ ] **Step 3: Add `users_db_path` field to CoreSettings**

In `packages/smart_pid_core/src/smart_pid_core/config.py`, add after the `db_batch_size` field:

```python
    # User database (app-level, separate from project)
    users_db_path: Path = Path.home() / ".config" / "smart-pid" / "users.db"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/unit/test_config_users_db.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/config.py tests/core/unit/test_config_users_db.py
git commit -m "feat(core): add users_db_path to CoreSettings for app-level user DB"
```

---

### Task 2: Separate UserRepository to its own SQLite connection

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/user_repo.py`
- Test: `tests/core/unit/test_user_repo_standalone.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/core/unit/test_user_repo_standalone.py
"""Tests for standalone UserRepository with its own DB file."""
from __future__ import annotations

import pytest

from smart_pid_core.adapters.outbound.user_repo import UserRepository


class TestUserRepoStandalone:
    @pytest.mark.asyncio
    async def test_initialize_creates_usuarios_table(self, tmp_path) -> None:
        db_path = tmp_path / "users.db"
        repo = UserRepository(db_path)
        await repo.initialize()
        # Should be able to list (empty)
        users = await repo.list_all()
        assert users == []
        await repo.close()

    @pytest.mark.asyncio
    async def test_create_and_retrieve_user(self, tmp_path) -> None:
        db_path = tmp_path / "users.db"
        repo = UserRepository(db_path)
        await repo.initialize()
        user = await repo.create("admin", "hash123", "ADMIN")
        assert user.username == "admin"
        assert user.role == "ADMIN"
        fetched = await repo.get_by_username("admin")
        assert fetched is not None
        assert fetched.id == user.id
        await repo.close()

    @pytest.mark.asyncio
    async def test_close_and_reopen(self, tmp_path) -> None:
        db_path = tmp_path / "users.db"
        repo = UserRepository(db_path)
        await repo.initialize()
        await repo.create("admin", "hash123", "ADMIN")
        await repo.close()
        # Reopen same file
        repo2 = UserRepository(db_path)
        await repo2.initialize()
        users = await repo2.list_all()
        assert len(users) == 1
        assert users[0].username == "admin"
        await repo2.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/unit/test_user_repo_standalone.py -v`
Expected: FAIL — `UserRepository.__init__()` currently takes `db: aiosqlite.Connection`, not a `Path`.

- [ ] **Step 3: Refactor UserRepository to manage its own connection**

Replace the full `user_repo.py` with:

```python
# packages/smart_pid_core/src/smart_pid_core/adapters/outbound/user_repo.py
"""User repository backed by a standalone Usuarios SQLite database."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import aiosqlite

if TYPE_CHECKING:
    from pathlib import Path

_USERS_DDL = """
CREATE TABLE IF NOT EXISTS Usuarios (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nome        TEXT    NOT NULL UNIQUE,
    senha_hash  TEXT    NOT NULL,
    perfil      TEXT    NOT NULL DEFAULT 'OPERATOR',
    ativo       INTEGER NOT NULL DEFAULT 1,
    criado_em   TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


@dataclass
class User:
    """Lightweight user record from DB."""

    id: int
    username: str
    password_hash: str
    role: str
    created_at: str
    active: bool = True


class UserRepository:
    """CRUD operations on the Usuarios table in a standalone SQLite DB."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Open DB, enable WAL, create Usuarios table."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.executescript(_USERS_DDL)
        await self._db.commit()

    @property
    def db(self) -> aiosqlite.Connection:
        assert self._db is not None, "UserRepository not initialized"
        return self._db

    async def create(self, username: str, password_hash: str, role: str) -> User:
        """Insert a new user. Raises on duplicate username."""
        async with self.db.execute(
            "INSERT INTO Usuarios (nome, senha_hash, perfil) VALUES (?, ?, ?)",
            (username, password_hash, role),
        ) as cur:
            new_id = cur.lastrowid
        await self.db.commit()
        return User(
            id=new_id or 0,
            username=username,
            password_hash=password_hash,
            role=role,
            created_at="",
        )

    async def get_by_username(self, username: str) -> User | None:
        """Return active user or None if not found."""
        async with self.db.execute(
            "SELECT id, nome, senha_hash, perfil, criado_em, ativo"
            " FROM Usuarios WHERE nome = ? AND ativo = 1",
            (username,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return User(
            id=row["id"],
            username=row["nome"],
            password_hash=row["senha_hash"],
            role=row["perfil"],
            created_at=row["criado_em"],
            active=bool(row["ativo"]),
        )

    async def list_all(self) -> list[User]:
        """Return all users."""
        async with self.db.execute(
            "SELECT id, nome, senha_hash, perfil, criado_em, ativo"
            " FROM Usuarios ORDER BY id"
        ) as cur:
            rows = await cur.fetchall()
        return [
            User(
                id=r["id"], username=r["nome"], password_hash=r["senha_hash"],
                role=r["perfil"], created_at=r["criado_em"], active=bool(r["ativo"]),
            )
            for r in rows
        ]

    async def get_by_id(self, user_id: int) -> User | None:
        """Return user by id or None if not found."""
        async with self.db.execute(
            "SELECT id, nome, senha_hash, perfil, criado_em, ativo"
            " FROM Usuarios WHERE id = ?",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return User(
            id=row["id"], username=row["nome"], password_hash=row["senha_hash"],
            role=row["perfil"], created_at=row["criado_em"], active=bool(row["ativo"]),
        )

    async def update(
        self,
        user_id: int,
        role: str | None = None,
        password_hash: str | None = None,
        active: bool | None = None,
    ) -> User | None:
        """Update user fields. Returns updated user or None if not found."""
        updates: list[str] = []
        params: list[str | int] = []
        if role is not None:
            updates.append("perfil = ?")
            params.append(role)
        if password_hash is not None:
            updates.append("senha_hash = ?")
            params.append(password_hash)
        if active is not None:
            updates.append("ativo = ?")
            params.append(1 if active else 0)
        if not updates:
            return await self.get_by_id(user_id)
        params.append(user_id)
        await self.db.execute(
            f"UPDATE Usuarios SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        await self.db.commit()
        return await self.get_by_id(user_id)

    async def deactivate(self, user_id: int) -> User | None:
        """Soft-delete a user by setting ativo=0."""
        await self.db.execute(
            "UPDATE Usuarios SET ativo = 0 WHERE id = ?", (user_id,),
        )
        await self.db.commit()
        return await self.get_by_id(user_id)

    async def close(self) -> None:
        """Close the SQLite connection."""
        if self._db is not None:
            await self._db.close()
            self._db = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/unit/test_user_repo_standalone.py -v`
Expected: PASS

- [ ] **Step 5: Update `main.py` to use standalone UserRepository**

In `packages/smart_pid_core/src/smart_pid_core/main.py`, replace the user repo initialization block:

Old:
```python
    # Phase 2: User repo + seed admin
    user_repo = UserRepository(repo.db)
```

New:
```python
    # Phase 2: User repo (app-level, separate from project DB)
    user_repo = UserRepository(settings.users_db_path)
    await user_repo.initialize()
```

And in the shutdown section, add before `await repo.close()`:
```python
    await user_repo.close()
```

- [ ] **Step 6: Update conftest.py to use new UserRepository signature**

In `tests/conftest.py`, update the `api_deps` fixture:

Old:
```python
    user_repo = UserRepository(repo.db)
```

New:
```python
    user_db_path = tmp_path / "users.db"
    user_repo = UserRepository(user_db_path)
    await user_repo.initialize()
```

Add in the teardown (before `await repo.db.close()`):
```python
    await user_repo.close()
```

Same for `sim_api_deps` fixture — replace `UserRepository(repo.db)` with standalone init and add `await user_repo.close()` in teardown.

- [ ] **Step 7: Remove Usuarios DDL from SQLiteRepository**

In `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py`, remove the `Usuarios` table DDL from the `_DDL` string (lines 34-41). The `Usuarios` table now lives exclusively in `users.db`.

- [ ] **Step 8: Run all tests to verify nothing broke**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 9: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/outbound/user_repo.py \
      packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py \
      packages/smart_pid_core/src/smart_pid_core/main.py \
      tests/conftest.py \
      tests/core/unit/test_user_repo_standalone.py
git commit -m "refactor(core): separate UserRepository into standalone users.db"
```

---

### Task 3: Add `Projeto_Meta` and `Configuracao_Simulador` tables to SQLiteRepository

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py`
- Test: `tests/core/unit/test_sqlite_repo_new_tables.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/core/unit/test_sqlite_repo_new_tables.py
"""Tests for new project management tables in SQLiteRepository."""
from __future__ import annotations

import pytest

from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository


class TestProjetoMetaTable:
    @pytest.mark.asyncio
    async def test_projeto_meta_table_exists(self, tmp_path) -> None:
        repo = SQLiteRepository(tmp_path / "test.spid")
        await repo.initialize()
        tables = await repo._get_table_names()
        assert "Projeto_Meta" in tables
        await repo.close()

    @pytest.mark.asyncio
    async def test_set_and_get_meta(self, tmp_path) -> None:
        repo = SQLiteRepository(tmp_path / "test.spid")
        await repo.initialize()
        await repo.set_meta("nome", "Test Project")
        await repo.set_meta("criado_em", "2026-04-06T10:00:00")
        name = await repo.get_meta("nome")
        assert name == "Test Project"
        created = await repo.get_meta("criado_em")
        assert created == "2026-04-06T10:00:00"
        await repo.close()

    @pytest.mark.asyncio
    async def test_get_meta_missing_returns_none(self, tmp_path) -> None:
        repo = SQLiteRepository(tmp_path / "test.spid")
        await repo.initialize()
        result = await repo.get_meta("nonexistent")
        assert result is None
        await repo.close()


class TestConfiguracaoSimuladorTable:
    @pytest.mark.asyncio
    async def test_configuracao_simulador_table_exists(self, tmp_path) -> None:
        repo = SQLiteRepository(tmp_path / "test.spid")
        await repo.initialize()
        tables = await repo._get_table_names()
        assert "Configuracao_Simulador" in tables
        await repo.close()

    @pytest.mark.asyncio
    async def test_save_and_load_sim_config(self, tmp_path) -> None:
        repo = SQLiteRepository(tmp_path / "test.spid")
        await repo.initialize()
        await repo.save_sim_config(
            controller_id=1, preset="TEMPERATURE", gain=2.5,
            tau1=30.0, tau2=10.0, dead_time=5.0,
        )
        cfg = await repo.get_sim_config(1)
        assert cfg is not None
        assert cfg["preset"] == "TEMPERATURE"
        assert cfg["gain"] == 2.5
        assert cfg["tau1"] == 30.0
        assert cfg["tau2"] == 10.0
        assert cfg["dead_time"] == 5.0
        await repo.close()

    @pytest.mark.asyncio
    async def test_get_sim_config_missing_returns_none(self, tmp_path) -> None:
        repo = SQLiteRepository(tmp_path / "test.spid")
        await repo.initialize()
        cfg = await repo.get_sim_config(999)
        assert cfg is None
        await repo.close()

    @pytest.mark.asyncio
    async def test_save_sim_config_upserts(self, tmp_path) -> None:
        repo = SQLiteRepository(tmp_path / "test.spid")
        await repo.initialize()
        await repo.save_sim_config(
            controller_id=1, preset="FLOW", gain=1.0,
            tau1=5.0, tau2=0.0, dead_time=1.0,
        )
        await repo.save_sim_config(
            controller_id=1, preset="PRESSURE", gain=0.5,
            tau1=10.0, tau2=0.0, dead_time=2.0,
        )
        cfg = await repo.get_sim_config(1)
        assert cfg is not None
        assert cfg["preset"] == "PRESSURE"
        assert cfg["gain"] == 0.5
        await repo.close()

    @pytest.mark.asyncio
    async def test_list_all_sim_configs(self, tmp_path) -> None:
        repo = SQLiteRepository(tmp_path / "test.spid")
        await repo.initialize()
        await repo.save_sim_config(1, "FLOW", 1.0, 5.0, 0.0, 1.0)
        await repo.save_sim_config(2, "TEMP", 2.0, 30.0, 10.0, 5.0)
        configs = await repo.list_sim_configs()
        assert len(configs) == 2
        await repo.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/unit/test_sqlite_repo_new_tables.py -v`
Expected: FAIL — tables and methods don't exist yet.

- [ ] **Step 3: Add DDL and methods to SQLiteRepository**

In `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py`, append to the `_DDL` string (after `Log_Alarmes` table):

```sql

CREATE TABLE IF NOT EXISTS Projeto_Meta (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS Configuracao_Simulador (
    controlador_id INTEGER PRIMARY KEY REFERENCES Controladores(id),
    preset TEXT NOT NULL DEFAULT 'fopdt_default',
    gain REAL NOT NULL,
    tau1 REAL NOT NULL,
    tau2 REAL NOT NULL,
    dead_time REAL NOT NULL
);
```

Add these methods to the `SQLiteRepository` class (before the test helpers section):

```python
    # ------------------------------------------------------------------
    # Project meta
    # ------------------------------------------------------------------

    async def set_meta(self, key: str, value: str) -> None:
        """Insert or update a project metadata key."""
        await self.db.execute(
            "INSERT OR REPLACE INTO Projeto_Meta (chave, valor) VALUES (?, ?)",
            (key, value),
        )
        await self.db.commit()

    async def get_meta(self, key: str) -> str | None:
        """Get a project metadata value by key, or None."""
        async with self.db.execute(
            "SELECT valor FROM Projeto_Meta WHERE chave = ?", (key,),
        ) as cur:
            row = await cur.fetchone()
        return row["valor"] if row else None

    # ------------------------------------------------------------------
    # Simulator config persistence
    # ------------------------------------------------------------------

    async def save_sim_config(
        self,
        controller_id: int,
        preset: str,
        gain: float,
        tau1: float,
        tau2: float,
        dead_time: float,
    ) -> None:
        """Insert or update simulator config for a controller."""
        await self.db.execute(
            "INSERT OR REPLACE INTO Configuracao_Simulador"
            " (controlador_id, preset, gain, tau1, tau2, dead_time)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (controller_id, preset, gain, tau1, tau2, dead_time),
        )
        await self.db.commit()

    async def get_sim_config(self, controller_id: int) -> dict | None:
        """Get simulator config for a controller, or None."""
        async with self.db.execute(
            "SELECT preset, gain, tau1, tau2, dead_time"
            " FROM Configuracao_Simulador WHERE controlador_id = ?",
            (controller_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return {
            "preset": row["preset"],
            "gain": row["gain"],
            "tau1": row["tau1"],
            "tau2": row["tau2"],
            "dead_time": row["dead_time"],
        }

    async def list_sim_configs(self) -> list[dict]:
        """Return all simulator configs."""
        async with self.db.execute(
            "SELECT controlador_id, preset, gain, tau1, tau2, dead_time"
            " FROM Configuracao_Simulador ORDER BY controlador_id",
        ) as cur:
            rows = await cur.fetchall()
        return [
            {
                "controller_id": r["controlador_id"],
                "preset": r["preset"],
                "gain": r["gain"],
                "tau1": r["tau1"],
                "tau2": r["tau2"],
                "dead_time": r["dead_time"],
            }
            for r in rows
        ]
```

- [ ] **Step 4: Add `reopen` method to SQLiteRepository**

Add this method to the `SQLiteRepository` class after the `close()` method:

```python
    async def reopen(self, db_path: Path) -> None:
        """Close current DB and open a new one at the given path."""
        await self.close()
        self._db_path = db_path
        await self.initialize()
```

Add `Path` to the TYPE_CHECKING imports if not already there.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/core/unit/test_sqlite_repo_new_tables.py -v`
Expected: PASS

- [ ] **Step 6: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py \
      tests/core/unit/test_sqlite_repo_new_tables.py
git commit -m "feat(core): add Projeto_Meta and Configuracao_Simulador tables with CRUD methods"
```

---

### Task 4: Create ProjectService

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/application/project_service.py`
- Test: `tests/core/unit/test_project_service.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/core/unit/test_project_service.py
"""Tests for ProjectService — project lifecycle orchestration."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.application.project_service import ProjectService


@pytest.fixture
async def repo(tmp_path):
    db_path = tmp_path / "current.spid"
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
        repo=repo,
        loop_manager=loop_manager,
        simulator_adapter=simulator_adapter,
    )


class TestGetCurrent:
    @pytest.mark.asyncio
    async def test_get_current_empty_project(self, service) -> None:
        result = await service.get_current()
        assert result.controller_count == 0
        assert result.path != ""

    @pytest.mark.asyncio
    async def test_get_current_with_name(self, service, repo) -> None:
        await repo.set_meta("nome", "My Project")
        result = await service.get_current()
        assert result.name == "My Project"


class TestNewProject:
    @pytest.mark.asyncio
    async def test_new_project_creates_file(self, service, tmp_path) -> None:
        new_path = tmp_path / "new_project.spid"
        result = await service.new_project("Test Project", new_path)
        assert result.name == "Test Project"
        assert result.path == str(new_path)
        assert result.controller_count == 0
        assert new_path.exists()

    @pytest.mark.asyncio
    async def test_new_project_stops_loops(self, service, loop_manager, tmp_path) -> None:
        new_path = tmp_path / "new.spid"
        await service.new_project("P", new_path)
        loop_manager.stop_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_new_project_stores_meta(self, service, repo, tmp_path) -> None:
        new_path = tmp_path / "new.spid"
        await service.new_project("My Project", new_path)
        name = await repo.get_meta("nome")
        assert name == "My Project"
        created = await repo.get_meta("criado_em")
        assert created is not None


class TestOpenProject:
    @pytest.mark.asyncio
    async def test_open_existing_project(self, service, repo, tmp_path) -> None:
        # Create a project file first
        project_path = tmp_path / "existing.spid"
        temp_repo = SQLiteRepository(project_path)
        await temp_repo.initialize()
        await temp_repo.set_meta("nome", "Existing")
        await temp_repo.close()

        result = await service.open_project(project_path)
        assert result.name == "Existing"
        assert result.path == str(project_path)

    @pytest.mark.asyncio
    async def test_open_nonexistent_raises(self, service, tmp_path) -> None:
        with pytest.raises(FileNotFoundError):
            await service.open_project(tmp_path / "nope.spid")

    @pytest.mark.asyncio
    async def test_open_stops_loops(self, service, loop_manager, tmp_path) -> None:
        project_path = tmp_path / "existing.spid"
        temp_repo = SQLiteRepository(project_path)
        await temp_repo.initialize()
        await temp_repo.close()
        await service.open_project(project_path)
        loop_manager.stop_all.assert_called_once()


class TestSaveAs:
    @pytest.mark.asyncio
    async def test_save_as_copies_file(self, service, repo, tmp_path) -> None:
        await repo.set_meta("nome", "Original")
        dest = tmp_path / "copy.spid"
        result = await service.save_as(dest)
        assert dest.exists()
        assert result.name == "Original"
        assert result.path == str(dest)

    @pytest.mark.asyncio
    async def test_save_as_does_not_stop_loops(
        self, service, loop_manager, tmp_path,
    ) -> None:
        dest = tmp_path / "copy.spid"
        await service.save_as(dest)
        loop_manager.stop_all.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/unit/test_project_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'smart_pid_core.application.project_service'`

- [ ] **Step 3: Implement ProjectService**

```python
# packages/smart_pid_core/src/smart_pid_core/application/project_service.py
"""ProjectService — orchestrates project lifecycle transitions."""
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from smart_pid_domain.dtos.project import ProjectResponse

if TYPE_CHECKING:
    from pathlib import Path

    from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
    from smart_pid_core.application.loop_manager import LoopManager


class ProjectService:
    """Orchestrates project transitions: new, open, save-as."""

    def __init__(
        self,
        repo: SQLiteRepository,
        loop_manager: LoopManager,
        simulator_adapter: object | None = None,
    ) -> None:
        self._repo = repo
        self._loop_manager = loop_manager
        self._simulator_adapter = simulator_adapter

    async def get_current(self) -> ProjectResponse:
        """Return info about the currently active project."""
        name = await self._repo.get_meta("nome") or ""
        controllers = await self._repo.list_all()
        return ProjectResponse(
            name=name,
            path=str(self._repo._db_path),
            controller_count=len(controllers),
        )

    async def new_project(self, name: str, path: Path) -> ProjectResponse:
        """Create a new empty project and switch to it."""
        self._loop_manager.stop_all()
        self._stop_simulator()
        await self._repo.reopen(path)
        now = datetime.now(timezone.utc).isoformat()
        await self._repo.set_meta("nome", name)
        await self._repo.set_meta("criado_em", now)
        return await self.get_current()

    async def open_project(self, path: Path) -> ProjectResponse:
        """Open an existing .spid project file."""
        if not path.exists():
            raise FileNotFoundError(f"Project file not found: {path}")
        self._loop_manager.stop_all()
        self._stop_simulator()
        await self._repo.reopen(path)
        return await self.get_current()

    async def save_as(self, path: Path) -> ProjectResponse:
        """Copy current project to a new path and switch to it."""
        current_path = self._repo._db_path
        # Flush pending writes
        await self._repo.db.commit()
        await self._repo.close()
        shutil.copy2(current_path, path)
        await self._repo.reopen(path)
        return await self.get_current()

    def _stop_simulator(self) -> None:
        if self._simulator_adapter is not None and hasattr(
            self._simulator_adapter, "stop"
        ):
            self._simulator_adapter.stop()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/unit/test_project_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/application/project_service.py \
      tests/core/unit/test_project_service.py
git commit -m "feat(core): add ProjectService for project lifecycle orchestration"
```

---

### Task 5: Create project API routes

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/project.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py`
- Test: `tests/core/integration/test_api_project.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/core/integration/test_api_project.py
"""Tests for /project endpoints."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestProjectCurrent:
    @pytest.mark.asyncio
    async def test_get_current_project(
        self, client: AsyncClient, admin_headers: dict,
    ) -> None:
        resp = await client.get("/project/current", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "name" in data
        assert "path" in data
        assert "controller_count" in data


class TestProjectNew:
    @pytest.mark.asyncio
    async def test_create_new_project(
        self, client: AsyncClient, admin_headers: dict, tmp_path,
    ) -> None:
        new_path = str(tmp_path / "new_project.spid")
        resp = await client.post(
            "/project/new",
            json={"name": "Test Project", "path": new_path},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Test Project"
        assert data["path"] == new_path
        assert data["controller_count"] == 0


class TestProjectOpen:
    @pytest.mark.asyncio
    async def test_open_existing_project(
        self, client: AsyncClient, admin_headers: dict, api_deps, tmp_path,
    ) -> None:
        from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository

        # Create a project file to open
        project_path = tmp_path / "open_test.spid"
        temp_repo = SQLiteRepository(project_path)
        await temp_repo.initialize()
        await temp_repo.set_meta("nome", "Opened Project")
        await temp_repo.close()

        resp = await client.post(
            "/project/open",
            json={"path": str(project_path)},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Opened Project"

    @pytest.mark.asyncio
    async def test_open_nonexistent_returns_404(
        self, client: AsyncClient, admin_headers: dict,
    ) -> None:
        resp = await client.post(
            "/project/open",
            json={"path": "/nonexistent/path.spid"},
            headers=admin_headers,
        )
        assert resp.status_code == 404


class TestProjectSaveAs:
    @pytest.mark.asyncio
    async def test_save_as_copies_project(
        self, client: AsyncClient, admin_headers: dict, tmp_path,
    ) -> None:
        dest = str(tmp_path / "saved_copy.spid")
        resp = await client.post(
            "/project/save-as",
            json={"path": dest},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["path"] == dest
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/integration/test_api_project.py -v`
Expected: FAIL — 404 for all `/project/*` routes (router not registered).

- [ ] **Step 3: Create the project router**

```python
# packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/project.py
"""Project management API routes."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from smart_pid_domain.dtos.project import (
    ProjectCreate,
    ProjectOpen,
    ProjectResponse,
    ProjectSaveAs,
)

router = APIRouter()


@router.get("/current", response_model=ProjectResponse)
async def get_current_project(request: Request) -> ProjectResponse:
    """Return info about the currently active project."""
    project_service = request.app.state.project_service
    return await project_service.get_current()


@router.post("/new", response_model=ProjectResponse)
async def new_project(body: ProjectCreate, request: Request) -> ProjectResponse:
    """Create a new empty project and switch to it."""
    project_service = request.app.state.project_service
    path = Path(body.path)
    if path.exists():
        raise HTTPException(status_code=409, detail=f"File already exists: {path}")
    try:
        return await project_service.new_project(body.name, path)
    except OSError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/open", response_model=ProjectResponse)
async def open_project(body: ProjectOpen, request: Request) -> ProjectResponse:
    """Open an existing .spid project file."""
    project_service = request.app.state.project_service
    path = Path(body.path)
    try:
        return await project_service.open_project(path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except OSError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/save-as", response_model=ProjectResponse)
async def save_as_project(body: ProjectSaveAs, request: Request) -> ProjectResponse:
    """Copy current project to a new path and switch to it."""
    project_service = request.app.state.project_service
    path = Path(body.path)
    try:
        return await project_service.save_as(path)
    except OSError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
```

- [ ] **Step 4: Register router in `app.py` and wire ProjectService**

In `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py`:

Add import:
```python
from smart_pid_core.adapters.inbound.api.routers import (
    ...
    project,
)
```

Add `project_service` parameter to `create_app`:
```python
    project_service: ProjectService | None = None,
```

Add to TYPE_CHECKING:
```python
    from smart_pid_core.application.project_service import ProjectService
```

Add to app.state:
```python
    app.state.project_service = project_service
```

Register the router:
```python
    app.include_router(project.router, prefix="/project", tags=["project"])
```

- [ ] **Step 5: Wire ProjectService in main.py**

In `packages/smart_pid_core/src/smart_pid_core/main.py`, after creating the `loop_manager`, add:

```python
    from smart_pid_core.application.project_service import ProjectService
    project_service = ProjectService(
        repo=repo,
        loop_manager=loop_manager,
        simulator_adapter=simulator_adapter,
    )
```

Pass it to `create_app`:
```python
    app = create_app(
        ...
        project_service=project_service,
    )
```

- [ ] **Step 6: Update conftest.py fixtures to include ProjectService**

In `tests/conftest.py`, update the `api_deps` fixture to create a ProjectService:

```python
    from smart_pid_core.application.project_service import ProjectService
    project_service = ProjectService(repo=repo, loop_manager=loop_manager)
```

Add `"project_service": project_service` to the yield dict.

Update `app` fixture to pass it:
```python
    return create_app(
        ...
        project_service=api_deps["project_service"],
    )
```

- [ ] **Step 7: Run test to verify it passes**

Run: `uv run pytest tests/core/integration/test_api_project.py -v`
Expected: PASS

- [ ] **Step 8: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 9: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/project.py \
      packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py \
      packages/smart_pid_core/src/smart_pid_core/main.py \
      tests/conftest.py \
      tests/core/integration/test_api_project.py
git commit -m "feat(core): add /project REST API routes (new, open, save-as, current)"
```

---

### Task 6: Add `app_state_path` to HMISettings and create AppStateManager

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/config.py`
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/services/app_state.py`
- Test: `tests/hmi/test_app_state.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/hmi/test_app_state.py
"""Tests for AppStateManager — app.json read/write."""
from __future__ import annotations

import json

import pytest

from smart_pid_hmi.services.app_state import AppStateManager


class TestAppStateManager:
    def test_load_nonexistent_returns_defaults(self, tmp_path) -> None:
        path = tmp_path / "app.json"
        mgr = AppStateManager(path)
        assert mgr.last_project is None
        assert mgr.recent_projects == []

    def test_save_and_reload(self, tmp_path) -> None:
        path = tmp_path / "app.json"
        mgr = AppStateManager(path)
        mgr.set_last_project("/path/to/project.spid", "My Project", 3)
        mgr.save()

        mgr2 = AppStateManager(path)
        assert mgr2.last_project == "/path/to/project.spid"
        assert len(mgr2.recent_projects) == 1
        assert mgr2.recent_projects[0]["name"] == "My Project"
        assert mgr2.recent_projects[0]["controller_count"] == 3

    def test_recent_projects_fifo_limit_5(self, tmp_path) -> None:
        path = tmp_path / "app.json"
        mgr = AppStateManager(path)
        for i in range(7):
            mgr.set_last_project(f"/path/{i}.spid", f"Project {i}", i)
        mgr.save()

        mgr2 = AppStateManager(path)
        assert len(mgr2.recent_projects) == 5
        # Most recent should be first
        assert mgr2.recent_projects[0]["name"] == "Project 6"
        assert mgr2.recent_projects[4]["name"] == "Project 2"

    def test_duplicate_path_moves_to_front(self, tmp_path) -> None:
        path = tmp_path / "app.json"
        mgr = AppStateManager(path)
        mgr.set_last_project("/a.spid", "A", 1)
        mgr.set_last_project("/b.spid", "B", 2)
        mgr.set_last_project("/a.spid", "A Updated", 5)
        mgr.save()

        mgr2 = AppStateManager(path)
        assert len(mgr2.recent_projects) == 2
        assert mgr2.recent_projects[0]["path"] == "/a.spid"
        assert mgr2.recent_projects[0]["name"] == "A Updated"

    def test_prune_removes_nonexistent(self, tmp_path) -> None:
        path = tmp_path / "app.json"
        existing = tmp_path / "exists.spid"
        existing.touch()
        mgr = AppStateManager(path)
        mgr.set_last_project(str(existing), "Exists", 1)
        mgr.set_last_project("/nonexistent.spid", "Gone", 0)
        mgr.save()

        mgr2 = AppStateManager(path)
        mgr2.prune()
        assert len(mgr2.recent_projects) == 1
        assert mgr2.recent_projects[0]["name"] == "Exists"

    def test_creates_parent_dirs(self, tmp_path) -> None:
        path = tmp_path / "subdir" / "deep" / "app.json"
        mgr = AppStateManager(path)
        mgr.set_last_project("/a.spid", "A", 1)
        mgr.save()
        assert path.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/hmi/test_app_state.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement AppStateManager**

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/services/app_state.py
"""App-level state persistence — recent projects, last project, etc."""
from __future__ import annotations

import json
from pathlib import Path

_MAX_RECENT = 5


class AppStateManager:
    """Manages ~/.config/smart-pid/app.json for cross-session state."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (Path.home() / ".config" / "smart-pid" / "app.json")
        self._last_project: str | None = None
        self._recent: list[dict] = []
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._last_project = data.get("last_project")
            self._recent = data.get("recent_projects", [])
        except (json.JSONDecodeError, OSError):
            pass

    @property
    def last_project(self) -> str | None:
        return self._last_project

    @property
    def recent_projects(self) -> list[dict]:
        return list(self._recent)

    def set_last_project(
        self, path: str, name: str, controller_count: int,
    ) -> None:
        """Set the active project and add/update in recent list."""
        self._last_project = path
        # Remove existing entry with same path
        self._recent = [r for r in self._recent if r.get("path") != path]
        # Add to front
        self._recent.insert(0, {
            "name": name,
            "path": path,
            "controller_count": controller_count,
        })
        # Enforce limit
        self._recent = self._recent[:_MAX_RECENT]

    def prune(self) -> None:
        """Remove entries pointing to files that no longer exist."""
        self._recent = [
            r for r in self._recent if Path(r["path"]).exists()
        ]
        if self._last_project and not Path(self._last_project).exists():
            self._last_project = None

    def save(self) -> None:
        """Write state to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "last_project": self._last_project,
            "recent_projects": self._recent,
        }
        self._path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
```

- [ ] **Step 4: Add `app_state_path` to HMISettings**

In `packages/smart_pid_hmi/src/smart_pid_hmi/config.py`, add:

```python
from pathlib import Path
```

And the new field:

```python
    app_state_path: Path = Path.home() / ".config" / "smart-pid" / "app.json"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/hmi/test_app_state.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/services/app_state.py \
      packages/smart_pid_hmi/src/smart_pid_hmi/config.py \
      tests/hmi/test_app_state.py
git commit -m "feat(hmi): add AppStateManager for project recent list and app.json persistence"
```

---

### Task 7: Add project API methods to APIClientPort and APIClient

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/services/ports.py`
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py` (if it exists)
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/services/mock_service.py`

- [ ] **Step 1: Add project methods to APIClientPort**

In `packages/smart_pid_hmi/src/smart_pid_hmi/services/ports.py`, add to `APIClientPort`:

```python
    # Project management
    def get_current_project(self) -> dict: ...
    def new_project(self, name: str, path: str) -> dict: ...
    def open_project(self, path: str) -> dict: ...
    def save_as_project(self, path: str) -> dict: ...
```

- [ ] **Step 2: Add project methods to APIClient**

Read the existing `api_client.py` and add the four methods following the same httpx pattern used by existing methods. Each calls the corresponding `/project/*` endpoint and returns the JSON response dict.

```python
    def get_current_project(self) -> dict:
        resp = self._client.get("/project/current", headers=self._auth_headers())
        resp.raise_for_status()
        return resp.json()

    def new_project(self, name: str, path: str) -> dict:
        resp = self._client.post(
            "/project/new",
            json={"name": name, "path": path},
            headers=self._auth_headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def open_project(self, path: str) -> dict:
        resp = self._client.post(
            "/project/open",
            json={"path": path},
            headers=self._auth_headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def save_as_project(self, path: str) -> dict:
        resp = self._client.post(
            "/project/save-as",
            json={"path": path},
            headers=self._auth_headers(),
        )
        resp.raise_for_status()
        return resp.json()
```

- [ ] **Step 3: Add mock implementations**

In `packages/smart_pid_hmi/src/smart_pid_hmi/services/mock_service.py`, add to `MockAPIClient`:

```python
    def get_current_project(self) -> dict:
        return {"name": "Mock Project", "path": "/mock/project.spid", "controller_count": 2}

    def new_project(self, name: str, path: str) -> dict:
        return {"name": name, "path": path, "controller_count": 0}

    def open_project(self, path: str) -> dict:
        return {"name": "Opened", "path": path, "controller_count": 0}

    def save_as_project(self, path: str) -> dict:
        return {"name": "Copy", "path": path, "controller_count": 0}
```

- [ ] **Step 4: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/services/ports.py \
      packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py \
      packages/smart_pid_hmi/src/smart_pid_hmi/services/mock_service.py
git commit -m "feat(hmi): add project management methods to APIClientPort and implementations"
```

---

### Task 8: Add Apply/Cancel pattern to SettingsPage

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/pages/settings_page.py`
- Test: `tests/hmi/test_settings_apply_cancel.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/hmi/test_settings_apply_cancel.py
"""Tests for Settings page Apply/Cancel pattern."""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from smart_pid_hmi.pages.settings_page import SettingsPage
from smart_pid_hmi.themes import ISA101Theme, MD3DarkTheme, ThemeManager


@pytest.fixture
def theme_manager():
    tm = ThemeManager()
    tm.register(ISA101Theme())
    tm.register(MD3DarkTheme())
    tm.set_theme("isa101")
    return tm


@pytest.fixture
def page(theme_manager):
    return SettingsPage(theme_manager=theme_manager)


class TestApplyCancelButtons:
    def test_apply_button_exists(self, page) -> None:
        btn = page.findChild(type(page._apply_btn), "apply_btn")
        assert btn is not None

    def test_cancel_button_exists(self, page) -> None:
        btn = page.findChild(type(page._cancel_btn), "cancel_btn")
        assert btn is not None

    def test_buttons_disabled_initially(self, page) -> None:
        assert not page._apply_btn.isEnabled()
        assert not page._cancel_btn.isEnabled()

    def test_editing_theme_enables_buttons(self, page) -> None:
        page._theme_combo.setCurrentIndex(1)
        assert page._apply_btn.isEnabled()
        assert page._cancel_btn.isEnabled()

    def test_cancel_reverts_theme(self, page) -> None:
        original_idx = page._theme_combo.currentIndex()
        page._theme_combo.setCurrentIndex(1)
        page._cancel_btn.click()
        assert page._theme_combo.currentIndex() == original_idx
        assert not page._apply_btn.isEnabled()

    def test_apply_emits_and_disables(self, page, qtbot) -> None:
        page._theme_combo.setCurrentIndex(1)
        with qtbot.waitSignal(page.theme_changed):
            page._apply_btn.click()
        assert not page._apply_btn.isEnabled()

    def test_has_unsaved_changes(self, page) -> None:
        assert not page.has_unsaved_changes()
        page._theme_combo.setCurrentIndex(1)
        assert page.has_unsaved_changes()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/hmi/test_settings_apply_cancel.py -v`
Expected: FAIL — `_apply_btn` attribute doesn't exist.

- [ ] **Step 3: Refactor SettingsPage to add Apply/Cancel**

Modify `packages/smart_pid_hmi/src/smart_pid_hmi/pages/settings_page.py`:

Key changes:
1. Remove the direct `currentTextChanged.connect(self._on_theme_changed)` on the theme combo — changes are now buffered.
2. Remove the direct `valueChanged.connect(self.refresh_rate_changed)` on the refresh spinbox.
3. Store "committed" values as `_committed_theme_idx`, `_committed_refresh`, `_committed_opcua_url`.
4. Connect all editable fields to a `_on_field_changed` method that enables/disables Apply/Cancel.
5. Add Apply and Cancel buttons at the bottom, right-aligned.
6. `_on_apply()` reads current values, emits signals (`theme_changed`, `refresh_rate_changed`, `opcua_reconnect_requested`), updates committed values, disables buttons.
7. `_on_cancel()` reverts all fields to committed values, disables buttons.
8. Add `has_unsaved_changes() -> bool` method.

The full implementation should:
- Store `_committed_theme_idx = self._theme_combo.currentIndex()` etc. after init
- Connect `_theme_combo.currentIndexChanged`, `_refresh_spin.valueChanged`, `_opcua_endpoint.textChanged` to `_on_field_changed`
- `_on_field_changed` compares current values to committed and enables/disables buttons
- Apply button: object name `"apply_btn"`, Cancel button: object name `"cancel_btn"`
- Remove the `addStretch()` at the end, add button row then stretch

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/hmi/test_settings_apply_cancel.py -v`
Expected: PASS

- [ ] **Step 5: Run all HMI tests**

Run: `uv run pytest tests/hmi/ -v`
Expected: ALL PASS (update any existing tests that relied on immediate signal emission)

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/pages/settings_page.py \
      tests/hmi/test_settings_apply_cancel.py
git commit -m "feat(hmi): add Apply/Cancel pattern to SettingsPage"
```

---

### Task 9: Add Project group box to SettingsPage

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/pages/settings_page.py`
- Test: `tests/hmi/test_settings_project_group.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/hmi/test_settings_project_group.py
"""Tests for Settings page Project group box."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QGroupBox, QLabel, QPushButton

from smart_pid_hmi.pages.settings_page import SettingsPage
from smart_pid_hmi.themes import ISA101Theme, ThemeManager


@pytest.fixture
def theme_manager():
    tm = ThemeManager()
    tm.register(ISA101Theme())
    tm.set_theme("isa101")
    return tm


@pytest.fixture
def page(theme_manager):
    return SettingsPage(theme_manager=theme_manager)


class TestProjectGroupBox:
    def test_project_group_exists(self, page) -> None:
        group = page.findChild(QGroupBox, "project_group")
        assert group is not None

    def test_project_name_label(self, page) -> None:
        label = page.findChild(QLabel, "project_name")
        assert label is not None

    def test_project_path_label(self, page) -> None:
        label = page.findChild(QLabel, "project_path")
        assert label is not None

    def test_project_count_label(self, page) -> None:
        label = page.findChild(QLabel, "project_count")
        assert label is not None

    def test_new_button(self, page) -> None:
        btn = page.findChild(QPushButton, "project_new_btn")
        assert btn is not None

    def test_open_button(self, page) -> None:
        btn = page.findChild(QPushButton, "project_open_btn")
        assert btn is not None

    def test_save_as_button(self, page) -> None:
        btn = page.findChild(QPushButton, "project_save_as_btn")
        assert btn is not None

    def test_project_changed_signal_exists(self, page) -> None:
        assert hasattr(page, "project_changed")

    def test_update_project_info(self, page) -> None:
        page.update_project_info("My Project", "/path/to/my.spid", 5)
        assert page._project_name.text() == "My Project"
        assert page._project_path.text() == "/path/to/my.spid"
        assert page._project_count.text() == "5"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/hmi/test_settings_project_group.py -v`
Expected: FAIL — no `project_group` widget.

- [ ] **Step 3: Add Project group box to SettingsPage**

In `packages/smart_pid_hmi/src/smart_pid_hmi/pages/settings_page.py`, add:

1. New signal: `project_changed = Signal(str, str)` (name, path)
2. New signals: `project_new_requested = Signal(str, str)` (name, path), `project_open_requested = Signal(str)` (path), `project_save_as_requested = Signal(str)` (path)
3. Build the Project group box at the top of the layout (before Appearance), with:
   - `_project_name` QLabel (objectName `"project_name"`)
   - `_project_path` QLabel (objectName `"project_path"`)
   - `_project_count` QLabel (objectName `"project_count"`)
   - New, Open, Save As QPushButtons with objectNames `"project_new_btn"`, `"project_open_btn"`, `"project_save_as_btn"`
4. Method `update_project_info(name, path, count)` to update labels
5. Buttons are **immediate actions** — not part of Apply/Cancel

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/hmi/test_settings_project_group.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/pages/settings_page.py \
      tests/hmi/test_settings_project_group.py
git commit -m "feat(hmi): add Project group box to SettingsPage (New/Open/Save As)"
```

---

### Task 10: Add Apply/Cancel pattern to SimulatorPage

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/pages/simulator_page.py`
- Test: `tests/hmi/test_simulator_apply_cancel.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/hmi/test_simulator_apply_cancel.py
"""Tests for Simulator page Apply/Cancel pattern."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QPushButton

from smart_pid_hmi.pages.simulator_page import SimulatorPage
from smart_pid_hmi.themes import ISA101Theme


@pytest.fixture
def page():
    return SimulatorPage(theme=ISA101Theme())


class TestSimulatorApplyCancel:
    def test_apply_button_exists(self, page) -> None:
        btn = page.findChild(QPushButton, "sim_apply_btn")
        assert btn is not None

    def test_cancel_button_exists(self, page) -> None:
        btn = page.findChild(QPushButton, "sim_cancel_btn")
        assert btn is not None

    def test_buttons_disabled_initially(self, page) -> None:
        assert not page._sim_apply_btn.isEnabled()
        assert not page._sim_cancel_btn.isEnabled()

    def test_changing_gain_enables_buttons(self, page) -> None:
        page._gain_slider.setValue(5.0)
        assert page._sim_apply_btn.isEnabled()
        assert page._sim_cancel_btn.isEnabled()

    def test_cancel_reverts_gain(self, page) -> None:
        original = page._gain_slider.value()
        page._gain_slider.setValue(5.0)
        page._sim_cancel_btn.click()
        assert page._gain_slider.value() == original
        assert not page._sim_apply_btn.isEnabled()

    def test_old_apply_buttons_removed(self, page) -> None:
        """The old per-group Apply buttons should no longer exist."""
        assert page.findChild(QPushButton, "pid_apply_btn") is None

    def test_has_unsaved_changes(self, page) -> None:
        assert not page.has_unsaved_changes()
        page._gain_slider.setValue(5.0)
        assert page.has_unsaved_changes()

    def test_disturbance_buttons_still_immediate(self, page) -> None:
        """Disturbance buttons should still work immediately, not buffered."""
        step_btn = None
        for btn in page.findChildren(QPushButton):
            if btn.text() == "Inject Step":
                step_btn = btn
                break
        assert step_btn is not None
        assert step_btn.isEnabled()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/hmi/test_simulator_apply_cancel.py -v`
Expected: FAIL — `sim_apply_btn` doesn't exist.

- [ ] **Step 3: Refactor SimulatorPage for Apply/Cancel**

Modify `packages/smart_pid_hmi/src/smart_pid_hmi/pages/simulator_page.py`:

Key changes:
1. Remove the old "Apply Parameters" and "Apply PID Parameters" buttons (remove `pid_apply_btn` objectName).
2. Store committed values for: preset, gain, tau1, tau2, dead_time, pid_enable, pid_mode, kp, ti, td.
3. Connect all buffered field changes to `_on_field_changed` which enables/disables Apply/Cancel.
4. Add `_sim_apply_btn` (objectName `"sim_apply_btn"`) and `_sim_cancel_btn` (objectName `"sim_cancel_btn"`) at the bottom, before the status label.
5. `_on_sim_apply()` emits `preset_changed`, `parameters_changed`, `pid_enabled_changed`, `pid_params_changed`, `pid_mode_changed` as appropriate for changed values, then updates committed state.
6. `_on_sim_cancel()` reverts all fields to committed values.
7. Disturbance buttons remain immediate — untouched.
8. Add `has_unsaved_changes() -> bool`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/hmi/test_simulator_apply_cancel.py -v`
Expected: PASS

- [ ] **Step 5: Run all HMI tests**

Run: `uv run pytest tests/hmi/ -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/pages/simulator_page.py \
      tests/hmi/test_simulator_apply_cancel.py
git commit -m "feat(hmi): add Apply/Cancel pattern to SimulatorPage"
```

---

### Task 11: Create WelcomeDialog

**Files:**
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/dialogs/welcome_dialog.py`
- Test: `tests/hmi/test_welcome_dialog.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/hmi/test_welcome_dialog.py
"""Tests for WelcomeDialog — first-run project selection."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QListWidget, QPushButton

from smart_pid_hmi.dialogs.welcome_dialog import WelcomeDialog


@pytest.fixture
def dialog():
    return WelcomeDialog(recent_projects=[
        {"name": "Project A", "path": "/a.spid", "controller_count": 3},
        {"name": "Project B", "path": "/b.spid", "controller_count": 1},
    ])


class TestWelcomeDialog:
    def test_new_button_exists(self, dialog) -> None:
        btn = dialog.findChild(QPushButton, "welcome_new_btn")
        assert btn is not None

    def test_open_button_exists(self, dialog) -> None:
        btn = dialog.findChild(QPushButton, "welcome_open_btn")
        assert btn is not None

    def test_recent_list_populated(self, dialog) -> None:
        lst = dialog.findChild(QListWidget, "recent_list")
        assert lst is not None
        assert lst.count() == 2

    def test_empty_recent_list(self) -> None:
        d = WelcomeDialog(recent_projects=[])
        lst = d.findChild(QListWidget, "recent_list")
        assert lst.count() == 0

    def test_result_defaults_none(self, dialog) -> None:
        assert dialog.result_action is None
        assert dialog.result_path is None
        assert dialog.result_name is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/hmi/test_welcome_dialog.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Create the dialogs directory and WelcomeDialog**

```bash
ls packages/smart_pid_hmi/src/smart_pid_hmi/dialogs/
```

If it doesn't exist, create `__init__.py`.

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/dialogs/__init__.py
```

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/dialogs/welcome_dialog.py
"""WelcomeDialog — shown on first run or when last project is unavailable."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class WelcomeDialog(QDialog):
    """Modal dialog for project selection on startup."""

    def __init__(
        self,
        recent_projects: list[dict] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Smart PID Edge Optimizer")
        self.setModal(True)
        self.setMinimumSize(420, 400)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        self.result_action: str | None = None  # "new" or "open"
        self.result_path: str | None = None
        self.result_name: str | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Title
        title = QLabel("\u2699 Smart PID Edge Optimizer")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        subtitle = QLabel("Project Management")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 13px; color: #888;")
        layout.addWidget(subtitle)

        # Buttons
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(8)

        new_btn = QPushButton("New Project")
        new_btn.setObjectName("welcome_new_btn")
        new_btn.setMinimumHeight(40)
        new_btn.clicked.connect(self._on_new)
        btn_layout.addWidget(new_btn)

        open_btn = QPushButton("Open Project")
        open_btn.setObjectName("welcome_open_btn")
        open_btn.setMinimumHeight(40)
        open_btn.clicked.connect(self._on_open)
        btn_layout.addWidget(open_btn)

        layout.addLayout(btn_layout)

        # Recent projects
        recent_label = QLabel("RECENT PROJECTS")
        recent_label.setStyleSheet(
            "font-size: 11px; color: #888; letter-spacing: 1px;"
        )
        layout.addWidget(recent_label)

        self._recent_list = QListWidget()
        self._recent_list.setObjectName("recent_list")
        self._recent_list.itemDoubleClicked.connect(self._on_recent_selected)
        recent = recent_projects or []
        for proj in recent:
            item = QListWidgetItem(
                f"{proj['name']}  ({proj.get('controller_count', 0)} loops)\n"
                f"{proj['path']}"
            )
            item.setData(Qt.ItemDataRole.UserRole, proj["path"])
            self._recent_list.addItem(item)
        layout.addWidget(self._recent_list)

    def _on_new(self) -> None:
        name, ok = QInputDialog.getText(self, "New Project", "Project name:")
        if not ok or not name.strip():
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save New Project", "", "Smart PID Project (*.spid)",
        )
        if not path:
            return
        if not path.endswith(".spid"):
            path += ".spid"
        self.result_action = "new"
        self.result_name = name.strip()
        self.result_path = path
        self.accept()

    def _on_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", "Smart PID Project (*.spid)",
        )
        if not path:
            return
        self.result_action = "open"
        self.result_path = path
        self.accept()

    def _on_recent_selected(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.result_action = "open"
            self.result_path = path
            self.accept()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/hmi/test_welcome_dialog.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/dialogs/__init__.py \
      packages/smart_pid_hmi/src/smart_pid_hmi/dialogs/welcome_dialog.py \
      tests/hmi/test_welcome_dialog.py
git commit -m "feat(hmi): add WelcomeDialog for project selection on startup"
```

---

### Task 12: Wire project management into MainWindow

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/main.py`

- [ ] **Step 1: Import AppStateManager and WelcomeDialog**

In `packages/smart_pid_hmi/src/smart_pid_hmi/main.py`, add imports:

```python
from smart_pid_hmi.dialogs.welcome_dialog import WelcomeDialog
from smart_pid_hmi.services.app_state import AppStateManager
```

- [ ] **Step 2: Add project signal and AppStateManager to MainWindow**

In the class-level signal declarations, add:

```python
    _project_loaded_signal = Signal(dict)  # ProjectResponse from background thread
```

Connect it in `__init__` after the other signal connections:

```python
        self._project_loaded_signal.connect(self._on_project_loaded)
```

Add the handler:

```python
    @Slot(dict)
    def _on_project_loaded(self, result: dict) -> None:
        """Update Settings page with project info from background thread."""
        self._settings_page.update_project_info(
            result["name"], result["path"], result["controller_count"],
        )
```

After `self._settings = settings`, add:

```python
        self._app_state = AppStateManager(settings.app_state_path)
        self._app_state.prune()
```

- [ ] **Step 3: Wire SettingsPage project signals in MainWindow**

After the existing `self._settings_page.refresh_rate_changed.connect(...)`, add:

```python
        self._settings_page.project_new_requested.connect(self._on_project_new)
        self._settings_page.project_open_requested.connect(self._on_project_open)
        self._settings_page.project_save_as_requested.connect(self._on_project_save_as)
```

- [ ] **Step 4: Add project action handlers to MainWindow**

```python
    def _on_project_new(self, name: str, path: str) -> None:
        """Handle new project from Settings page."""
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "New Project",
            "This will stop all running loops. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        def do_new():
            try:
                result = self._api_client.new_project(name, path)
                self._app_state.set_last_project(
                    result["path"], result["name"], result["controller_count"],
                )
                self._app_state.save()
                self._project_loaded_signal.emit(result)
                self._load_dashboard()
            except Exception as e:
                self._api_error_signal.emit(str(e))

        threading.Thread(target=do_new, daemon=True).start()

    def _on_project_open(self, path: str) -> None:
        """Handle open project from Settings page or welcome dialog."""
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "Open Project",
            "This will stop all running loops. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._do_open_project(path)

    def _do_open_project(self, path: str) -> None:
        """Open project without confirmation (used by welcome dialog)."""
        def do_open():
            try:
                result = self._api_client.open_project(path)
                self._app_state.set_last_project(
                    result["path"], result["name"], result["controller_count"],
                )
                self._app_state.save()
                self._project_loaded_signal.emit(result)
                self._load_dashboard()
            except Exception as e:
                self._api_error_signal.emit(str(e))

        threading.Thread(target=do_open, daemon=True).start()

    def _on_project_save_as(self, path: str) -> None:
        """Handle save-as from Settings page."""
        def do_save():
            try:
                result = self._api_client.save_as_project(path)
                self._app_state.set_last_project(
                    result["path"], result["name"], result["controller_count"],
                )
                self._app_state.save()
                self._project_loaded_signal.emit(result)
            except Exception as e:
                self._api_error_signal.emit(str(e))

        threading.Thread(target=do_save, daemon=True).start()
```

- [ ] **Step 5: Add unsaved-changes guard on page navigation**

In the nav button click lambda, check for unsaved changes before switching:

Override the nav click connection to check `has_unsaved_changes()` on the current page (Settings or Simulator). If changes exist, show QMessageBox "You have unsaved changes. Discard?" — if Yes, call cancel and switch; if No, stay.

- [ ] **Step 6: Update `main()` to show WelcomeDialog on startup**

In the `main()` function, after creating `window` but before `window.show()`:

```python
    # Project management: open last project or show welcome dialog
    app_state = AppStateManager(settings.app_state_path)
    app_state.prune()

    if app_state.last_project and Path(app_state.last_project).exists():
        # Auto-open last project (will happen after login)
        window._pending_project_path = app_state.last_project
    else:
        # Show welcome dialog
        dialog = WelcomeDialog(recent_projects=app_state.recent_projects)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if dialog.result_action == "new":
                window._pending_project_action = "new"
                window._pending_project_name = dialog.result_name
                window._pending_project_path = dialog.result_path
            elif dialog.result_action == "open":
                window._pending_project_action = "open"
                window._pending_project_path = dialog.result_path
        else:
            sys.exit(0)  # User closed dialog without choosing
```

Then in `_login_success()`, after existing code, add:

```python
        # Open pending project after login
        if hasattr(self, "_pending_project_path") and self._pending_project_path:
            action = getattr(self, "_pending_project_action", "open")
            if action == "new" and hasattr(self, "_pending_project_name"):
                self._on_project_new(self._pending_project_name, self._pending_project_path)
            else:
                self._do_open_project(self._pending_project_path)
```

- [ ] **Step 7: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/main.py
git commit -m "feat(hmi): wire project management into MainWindow with welcome dialog"
```

---

### Task 13: User migration from .spid to users.db

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/main.py`
- Test: `tests/core/integration/test_user_migration.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/core/integration/test_user_migration.py
"""Tests for automatic user migration from .spid to users.db."""
from __future__ import annotations

import aiosqlite
import pytest

from smart_pid_core.main import _migrate_users_if_needed


class TestUserMigration:
    @pytest.mark.asyncio
    async def test_migrates_users_from_spid(self, tmp_path) -> None:
        # Create a .spid with Usuarios table and a user
        spid_path = tmp_path / "project.spid"
        async with aiosqlite.connect(spid_path) as db:
            await db.executescript("""
                CREATE TABLE Usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL UNIQUE,
                    senha_hash TEXT NOT NULL,
                    perfil TEXT NOT NULL DEFAULT 'OPERATOR',
                    ativo INTEGER NOT NULL DEFAULT 1,
                    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
                );
            """)
            await db.execute(
                "INSERT INTO Usuarios (nome, senha_hash, perfil) VALUES (?, ?, ?)",
                ("admin", "hash123", "ADMIN"),
            )
            await db.commit()

        users_db_path = tmp_path / "users.db"
        await _migrate_users_if_needed(spid_path, users_db_path)

        # Verify users.db has the user
        from smart_pid_core.adapters.outbound.user_repo import UserRepository
        repo = UserRepository(users_db_path)
        await repo.initialize()
        users = await repo.list_all()
        assert len(users) == 1
        assert users[0].username == "admin"
        await repo.close()

    @pytest.mark.asyncio
    async def test_skips_if_users_db_exists(self, tmp_path) -> None:
        spid_path = tmp_path / "project.spid"
        spid_path.touch()
        users_db_path = tmp_path / "users.db"
        users_db_path.touch()  # Already exists

        # Should not raise, should skip
        await _migrate_users_if_needed(spid_path, users_db_path)

    @pytest.mark.asyncio
    async def test_skips_if_no_usuarios_table(self, tmp_path) -> None:
        spid_path = tmp_path / "project.spid"
        async with aiosqlite.connect(spid_path) as db:
            await db.execute("CREATE TABLE dummy (id INTEGER)")
            await db.commit()

        users_db_path = tmp_path / "users.db"
        await _migrate_users_if_needed(spid_path, users_db_path)
        assert not users_db_path.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/integration/test_user_migration.py -v`
Expected: FAIL — `_migrate_users_if_needed` doesn't exist.

- [ ] **Step 3: Implement migration function**

In `packages/smart_pid_core/src/smart_pid_core/main.py`, add:

```python
async def _migrate_users_if_needed(spid_path: Path, users_db_path: Path) -> None:
    """Auto-migrate users from .spid to standalone users.db if needed."""
    if users_db_path.exists():
        return  # Already migrated
    if not spid_path.exists():
        return

    import aiosqlite

    # Check if .spid has a Usuarios table
    async with aiosqlite.connect(spid_path) as db:
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='Usuarios'"
        ) as cur:
            if await cur.fetchone() is None:
                return  # No Usuarios table

        # Read all users
        async with db.execute(
            "SELECT nome, senha_hash, perfil, ativo, criado_em FROM Usuarios"
        ) as cur:
            rows = await cur.fetchall()

    if not rows:
        return

    # Write to users.db
    user_repo = UserRepository(users_db_path)
    await user_repo.initialize()
    for row in rows:
        try:
            await user_repo.db.execute(
                "INSERT INTO Usuarios (nome, senha_hash, perfil, ativo, criado_em)"
                " VALUES (?, ?, ?, ?, ?)",
                (row[0], row[1], row[2], row[3], row[4]),
            )
        except Exception:
            pass  # Skip duplicates
    await user_repo.db.commit()
    await user_repo.close()
    logger.info("migrated_users", count=len(rows), from_=str(spid_path), to=str(users_db_path))
```

Add the `Path` import at the top if not already present.

Call it in `run_daemon`, before user_repo init:

```python
    await _migrate_users_if_needed(settings.db_path, settings.users_db_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/integration/test_user_migration.py -v`
Expected: PASS

- [ ] **Step 5: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/main.py \
      tests/core/integration/test_user_migration.py
git commit -m "feat(core): auto-migrate users from .spid to standalone users.db"
```

---

### Task 14: Update spec documents

**Files:**
- Modify: `docs/smartPIDv2.md` or relevant spec documents

- [ ] **Step 1: Update the V2 spec with project management section**

Add a section describing the project management feature: Settings page Project group, Welcome dialog, `.spid` as project file, app.json for recent projects.

- [ ] **Step 2: Update CLAUDE.md if needed**

If any new environment variables or paths need to be documented, update CLAUDE.md.

- [ ] **Step 3: Commit**

```bash
git add docs/
git commit -m "docs: add project management feature to specs"
```

---

### Task 15: Final integration test and lint

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: Run linter**

Run: `uv run --with ruff ruff check .`
Expected: No errors (fix any that appear)

- [ ] **Step 3: Run type checker**

Run: `uv run mypy packages/`
Expected: No new errors

- [ ] **Step 4: Final commit if any fixes**

```bash
git add -A
git commit -m "chore: fix lint and type issues from project management feature"
```
