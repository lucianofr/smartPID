# Phase 2: REST API + Auth + Telemetry Publisher — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a FastAPI REST API with JWT auth, controller CRUD, commands, history queries, and a ZMQ telemetry publisher bridge to the existing headless backend.

**Architecture:** FastAPI app embedded via uvicorn in the existing asyncio event loop. JWT+bcrypt auth with admin/user RBAC. Telemetry publisher bridges internal EventBus (inproc://) to external ZMQ PUB (tcp://5555). DTOs live in smart_pid_domain for HMI reuse.

**Tech Stack:** FastAPI, uvicorn, PyJWT, bcrypt, httpx (test), ZMQ asyncio

---

## File Structure

### New files

```
packages/smart_pid_domain/src/smart_pid_domain/
├── dtos/
│   ├── __init__.py           # Re-exports all DTOs
│   ├── auth.py               # LoginRequest, TokenResponse, UserCreate, UserClaims
│   ├── commands.py           # SetpointCommand, ModeCommand, OutputCommand, CommandResponse
│   ├── controllers.py        # ControllerCreate, ControllerUpdate, ControllerResponse
│   ├── history.py            # HistoryQuery, TelemetryFrameDTO, HistoryResponse
│   └── system.py             # SystemStatusResponse

packages/smart_pid_core/src/smart_pid_core/
├── adapters/
│   ├── inbound/
│   │   ├── __init__.py
│   │   └── api/
│   │       ├── __init__.py
│   │       ├── app.py              # create_app() factory
│   │       ├── dependencies.py     # FastAPI Depends functions
│   │       ├── auth.py             # JWT encode/decode + password utils
│   │       ├── error_handlers.py   # Exception → HTTP mapping
│   │       └── routers/
│   │           ├── __init__.py
│   │           ├── auth.py
│   │           ├── controllers.py
│   │           ├── history.py
│   │           ├── commands.py
│   │           └── system.py
│   └── outbound/
│       └── user_repo.py            # UserRepository (Usuarios table)
├── application/
│   └── telemetry_publisher.py      # ZMQ inproc→tcp bridge

tests/
├── conftest.py                     # Add shared API fixtures
├── core/integration/
│   ├── test_user_repo.py
│   ├── test_api_system.py
│   ├── test_api_auth.py
│   ├── test_api_controllers.py
│   ├── test_api_commands.py
│   ├── test_api_history.py
│   └── test_telemetry_publisher.py
├── domain/
│   └── test_dtos.py
```

### Modified files

| File | Change |
|------|--------|
| `packages/smart_pid_core/pyproject.toml` | Add fastapi, uvicorn, pyjwt, bcrypt; add httpx to dev |
| `packages/smart_pid_domain/src/smart_pid_domain/__init__.py` | Export dtos subpackage |
| `packages/smart_pid_domain/src/smart_pid_domain/exceptions.py` | Add ControllerNotFoundError |
| `packages/smart_pid_core/src/smart_pid_core/application/loop_manager.py` | Add get_controller, set_setpoint, set_mode, set_output |
| `packages/smart_pid_core/src/smart_pid_core/main.py` | Embed FastAPI+uvicorn, TelemetryPublisher, UserRepo, seed admin |

---

## Task 1: Add Phase 2 Dependencies

**Files:**
- Modify: `packages/smart_pid_core/pyproject.toml`

- [ ] **Step 1: Add new dependencies to core pyproject.toml**

In `packages/smart_pid_core/pyproject.toml`, add to the `dependencies` list:

```toml
dependencies = [
    "smart-pid-domain",
    "pyzmq>=26.0",
    "msgpack>=1.0",
    "aiosqlite>=0.20",
    "pydantic-settings>=2.3",
    "structlog>=24.0",
    "numpy>=2.0",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "pyjwt>=2.9",
    "bcrypt>=4.2",
]
```

And add httpx to the dev dependencies:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-mock>=3.14",
    "mypy>=1.10",
    "ruff>=0.4",
    "coverage>=7.5",
    "httpx>=0.28",
]
```

- [ ] **Step 2: Sync workspace**

Run: `uv sync --all-packages`
Expected: All new packages installed without errors.

- [ ] **Step 3: Commit**

```bash
git add packages/smart_pid_core/pyproject.toml uv.lock
git commit -m "chore(core): add Phase 2 deps (fastapi, uvicorn, pyjwt, bcrypt, httpx)"
```

---

## Task 2: Domain DTOs

**Files:**
- Create: `packages/smart_pid_domain/src/smart_pid_domain/dtos/__init__.py`
- Create: `packages/smart_pid_domain/src/smart_pid_domain/dtos/auth.py`
- Create: `packages/smart_pid_domain/src/smart_pid_domain/dtos/commands.py`
- Create: `packages/smart_pid_domain/src/smart_pid_domain/dtos/controllers.py`
- Create: `packages/smart_pid_domain/src/smart_pid_domain/dtos/history.py`
- Create: `packages/smart_pid_domain/src/smart_pid_domain/dtos/system.py`
- Test: `tests/domain/test_dtos.py`

- [ ] **Step 1: Write DTO tests**

Create `tests/domain/test_dtos.py`:

```python
"""Tests for Phase 2 DTOs."""
from __future__ import annotations

from datetime import datetime, timezone

from smart_pid_domain.dtos.auth import LoginRequest, TokenResponse, UserClaims, UserCreate
from smart_pid_domain.dtos.commands import (
    CommandResponse,
    ModeCommand,
    OutputCommand,
    SetpointCommand,
)
from smart_pid_domain.dtos.controllers import (
    ControllerCreate,
    ControllerResponse,
    ControllerUpdate,
)
from smart_pid_domain.dtos.history import HistoryResponse, TelemetryFrameDTO
from smart_pid_domain.dtos.system import SystemStatusResponse
from smart_pid_domain.enums import ControllerMode


class TestAuthDTOs:
    def test_login_request(self) -> None:
        req = LoginRequest(username="admin", password="secret")
        assert req.username == "admin"
        assert req.password == "secret"

    def test_token_response_default(self) -> None:
        resp = TokenResponse(access_token="tok123")
        assert resp.token_type == "bearer"

    def test_user_create_default_role(self) -> None:
        u = UserCreate(username="bob", password="pass")
        assert u.role == "user"

    def test_user_claims(self) -> None:
        c = UserClaims(user_id=1, username="admin", role="admin")
        assert c.user_id == 1


class TestCommandDTOs:
    def test_setpoint_command(self) -> None:
        cmd = SetpointCommand(controller_id=1, value=55.0)
        assert cmd.controller_id == 1
        assert cmd.value == 55.0

    def test_mode_command(self) -> None:
        cmd = ModeCommand(controller_id=1, mode=ControllerMode.AUTO)
        assert cmd.mode == ControllerMode.AUTO

    def test_output_command(self) -> None:
        cmd = OutputCommand(controller_id=1, value=75.0)
        assert cmd.value == 75.0

    def test_command_response(self) -> None:
        resp = CommandResponse(ok=True, controller_id=1, detail="SP set to 55.0")
        assert resp.ok is True


class TestControllerDTOs:
    def test_controller_create_defaults(self) -> None:
        c = ControllerCreate(name="TIC-101")
        assert c.description == ""
        assert c.scan_rate_ms == 1000

    def test_controller_update_all_optional(self) -> None:
        u = ControllerUpdate()
        assert u.name is None
        assert u.description is None

    def test_controller_response(self) -> None:
        r = ControllerResponse(
            id=1, name="TIC-101", description="Temp", mode="AUTO",
            pv=50.0, sp=50.0, co=25.0,
        )
        assert r.id == 1


class TestHistoryDTOs:
    def test_telemetry_frame_dto(self) -> None:
        now = datetime.now(tz=timezone.utc)
        f = TelemetryFrameDTO(
            timestamp=now, pv=50.0, sp=50.0, co=25.0, mode="AUTO", status="GOOD",
        )
        assert f.pv == 50.0

    def test_history_response(self) -> None:
        r = HistoryResponse(controller_id=1, frames=[], count=0)
        assert r.count == 0


class TestSystemDTOs:
    def test_system_status(self) -> None:
        s = SystemStatusResponse(
            status="running", uptime_s=123.4, active_controllers=2,
            bus_active=True, api_version="2.0.0",
        )
        assert s.status == "running"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/domain/test_dtos.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'smart_pid_domain.dtos'`

- [ ] **Step 3: Create auth DTOs**

Create `packages/smart_pid_domain/src/smart_pid_domain/dtos/auth.py`:

```python
"""Auth-related DTOs for login, registration, and JWT claims."""
from __future__ import annotations

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "user"


class UserClaims(BaseModel):
    user_id: int
    username: str
    role: str
```

- [ ] **Step 4: Create command DTOs**

Create `packages/smart_pid_domain/src/smart_pid_domain/dtos/commands.py`:

```python
"""Command DTOs for setpoint, mode, and output changes."""
from __future__ import annotations

from pydantic import BaseModel

from smart_pid_domain.enums import ControllerMode


class SetpointCommand(BaseModel):
    controller_id: int
    value: float


class ModeCommand(BaseModel):
    controller_id: int
    mode: ControllerMode


class OutputCommand(BaseModel):
    controller_id: int
    value: float


class CommandResponse(BaseModel):
    ok: bool
    controller_id: int
    detail: str | None = None
```

- [ ] **Step 5: Create controller DTOs**

Create `packages/smart_pid_domain/src/smart_pid_domain/dtos/controllers.py`:

```python
"""Controller CRUD DTOs."""
from __future__ import annotations

from pydantic import BaseModel


class ControllerCreate(BaseModel):
    name: str
    description: str = ""
    scan_rate_ms: int = 1000
    gain: float = 1.0
    reset: float = 10.0
    rate: float = 0.0
    sp_hi_lim: float = 100.0
    sp_lo_lim: float = 0.0
    out_hi_lim: float = 100.0
    out_lo_lim: float = 0.0


class ControllerUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    scan_rate_ms: int | None = None
    gain: float | None = None
    reset: float | None = None
    rate: float | None = None
    sp_hi_lim: float | None = None
    sp_lo_lim: float | None = None
    out_hi_lim: float | None = None
    out_lo_lim: float | None = None


class ControllerResponse(BaseModel):
    id: int
    name: str
    description: str
    mode: str
    pv: float
    sp: float
    co: float
    scan_rate_ms: int = 1000
    gain: float = 1.0
    reset: float = 10.0
    rate: float = 0.0
    sp_hi_lim: float = 100.0
    sp_lo_lim: float = 0.0
    out_hi_lim: float = 100.0
    out_lo_lim: float = 0.0
```

- [ ] **Step 6: Create history DTOs**

Create `packages/smart_pid_domain/src/smart_pid_domain/dtos/history.py`:

```python
"""History query DTOs."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TelemetryFrameDTO(BaseModel):
    timestamp: datetime
    pv: float
    sp: float
    co: float
    mode: str
    status: str


class HistoryResponse(BaseModel):
    controller_id: int
    frames: list[TelemetryFrameDTO]
    count: int
```

- [ ] **Step 7: Create system DTOs**

Create `packages/smart_pid_domain/src/smart_pid_domain/dtos/system.py`:

```python
"""System status DTOs."""
from __future__ import annotations

from pydantic import BaseModel


class SystemStatusResponse(BaseModel):
    status: str
    uptime_s: float
    active_controllers: int
    bus_active: bool
    api_version: str
```

- [ ] **Step 8: Create dtos/__init__.py re-exports**

Create `packages/smart_pid_domain/src/smart_pid_domain/dtos/__init__.py`:

```python
"""Phase 2 DTOs — shared between core and HMI."""
from smart_pid_domain.dtos.auth import LoginRequest, TokenResponse, UserClaims, UserCreate
from smart_pid_domain.dtos.commands import (
    CommandResponse,
    ModeCommand,
    OutputCommand,
    SetpointCommand,
)
from smart_pid_domain.dtos.controllers import (
    ControllerCreate,
    ControllerResponse,
    ControllerUpdate,
)
from smart_pid_domain.dtos.history import HistoryResponse, TelemetryFrameDTO
from smart_pid_domain.dtos.system import SystemStatusResponse

__all__ = [
    "CommandResponse",
    "ControllerCreate",
    "ControllerResponse",
    "ControllerUpdate",
    "HistoryResponse",
    "LoginRequest",
    "ModeCommand",
    "OutputCommand",
    "SetpointCommand",
    "SystemStatusResponse",
    "TelemetryFrameDTO",
    "TokenResponse",
    "UserClaims",
    "UserCreate",
]
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `uv run pytest tests/domain/test_dtos.py -v`
Expected: All 12 tests PASS.

- [ ] **Step 10: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/dtos/ tests/domain/test_dtos.py
git commit -m "feat(domain): add Phase 2 DTOs (auth, commands, controllers, history, system)"
```

---

## Task 3: Add ControllerNotFoundError

**Files:**
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/exceptions.py`
- Modify: `tests/domain/test_models.py`

- [ ] **Step 1: Add test for ControllerNotFoundError**

In `tests/domain/test_models.py`, add to the existing test class:

```python
from smart_pid_domain.exceptions import ControllerNotFoundError, DomainError

class TestControllerNotFoundError:
    def test_is_domain_error(self) -> None:
        err = ControllerNotFoundError(42)
        assert isinstance(err, DomainError)

    def test_stores_controller_id(self) -> None:
        err = ControllerNotFoundError(42)
        assert err.controller_id == 42

    def test_message(self) -> None:
        err = ControllerNotFoundError(42)
        assert "42" in str(err)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/domain/test_models.py::TestControllerNotFoundError -v`
Expected: FAIL — `ImportError: cannot import name 'ControllerNotFoundError'`

- [ ] **Step 3: Implement ControllerNotFoundError**

In `packages/smart_pid_domain/src/smart_pid_domain/exceptions.py`, add after `AlarmConfigError`:

```python
class ControllerNotFoundError(DomainError):
    def __init__(self, controller_id: int) -> None:
        self.controller_id = controller_id
        super().__init__(f"Controller {controller_id} not found")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/domain/test_models.py::TestControllerNotFoundError -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/exceptions.py tests/domain/test_models.py
git commit -m "feat(domain): add ControllerNotFoundError exception"
```

---

## Task 4: UserRepository

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/user_repo.py`
- Create: `tests/core/integration/test_user_repo.py`

- [ ] **Step 1: Write UserRepository tests**

Create `tests/core/integration/test_user_repo.py`:

```python
"""Tests for UserRepository (Usuarios table)."""
from __future__ import annotations

import pytest

from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.adapters.outbound.user_repo import User, UserRepository


@pytest.fixture
async def user_repo(tmp_path) -> UserRepository:
    db_path = tmp_path / "test.spid"
    repo = SQLiteRepository(db_path)
    await repo.initialize()
    return UserRepository(repo.db)


class TestUserRepository:
    @pytest.mark.asyncio
    async def test_create_and_get_by_username(self, user_repo: UserRepository) -> None:
        user = await user_repo.create("alice", "hashed_pw", "admin")
        assert user.id > 0
        assert user.username == "alice"
        assert user.role == "admin"

        loaded = await user_repo.get_by_username("alice")
        assert loaded is not None
        assert loaded.id == user.id
        assert loaded.password_hash == "hashed_pw"

    @pytest.mark.asyncio
    async def test_get_by_username_not_found(self, user_repo: UserRepository) -> None:
        result = await user_repo.get_by_username("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_all(self, user_repo: UserRepository) -> None:
        await user_repo.create("alice", "h1", "admin")
        await user_repo.create("bob", "h2", "user")
        users = await user_repo.list_all()
        assert len(users) == 2
        names = {u.username for u in users}
        assert names == {"alice", "bob"}

    @pytest.mark.asyncio
    async def test_create_duplicate_username_raises(self, user_repo: UserRepository) -> None:
        await user_repo.create("alice", "h1", "admin")
        with pytest.raises(Exception):
            await user_repo.create("alice", "h2", "user")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/integration/test_user_repo.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement UserRepository**

Create `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/user_repo.py`:

```python
"""User repository backed by the Usuarios SQLite table."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite


@dataclass
class User:
    """Lightweight user record from DB."""

    id: int
    username: str
    password_hash: str
    role: str
    created_at: str


class UserRepository:
    """CRUD operations on the Usuarios table."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def create(self, username: str, password_hash: str, role: str) -> User:
        """Insert a new user. Raises on duplicate username."""
        async with self._db.execute(
            "INSERT INTO Usuarios (nome, senha_hash, perfil) VALUES (?, ?, ?)",
            (username, password_hash, role),
        ) as cur:
            new_id = cur.lastrowid
        await self._db.commit()
        return User(
            id=new_id or 0,
            username=username,
            password_hash=password_hash,
            role=role,
            created_at="",
        )

    async def get_by_username(self, username: str) -> User | None:
        """Return user or None if not found."""
        async with self._db.execute(
            "SELECT id, nome, senha_hash, perfil, criado_em FROM Usuarios WHERE nome = ?",
            (username,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return User(
            id=row[0],
            username=row[1],
            password_hash=row[2],
            role=row[3],
            created_at=row[4],
        )

    async def list_all(self) -> list[User]:
        """Return all users."""
        async with self._db.execute(
            "SELECT id, nome, senha_hash, perfil, criado_em FROM Usuarios ORDER BY id"
        ) as cur:
            rows = await cur.fetchall()
        return [
            User(id=r[0], username=r[1], password_hash=r[2], role=r[3], created_at=r[4])
            for r in rows
        ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/integration/test_user_repo.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/outbound/user_repo.py tests/core/integration/test_user_repo.py
git commit -m "feat(core): add UserRepository for Usuarios table"
```

---

## Task 5: Auth Utilities (JWT + bcrypt)

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/__init__.py`
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/__init__.py`
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/auth.py`
- Create: `tests/core/unit/test_auth_utils.py`

- [ ] **Step 1: Write auth utility tests**

Create `tests/core/unit/test_auth_utils.py`:

```python
"""Tests for JWT and password utility functions."""
from __future__ import annotations

import pytest

from smart_pid_core.adapters.inbound.api.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class TestPasswordUtils:
    def test_hash_and_verify(self) -> None:
        pw_hash = hash_password("mysecret")
        assert pw_hash != "mysecret"
        assert verify_password("mysecret", pw_hash) is True

    def test_verify_wrong_password(self) -> None:
        pw_hash = hash_password("mysecret")
        assert verify_password("wrong", pw_hash) is False


class TestJWT:
    def test_create_and_decode_token(self) -> None:
        token = create_access_token(
            user_id=1, username="admin", role="admin",
            secret="testsecret", expiry_hours=1,
        )
        claims = decode_access_token(token, secret="testsecret")
        assert claims["sub"] == 1
        assert claims["username"] == "admin"
        assert claims["role"] == "admin"

    def test_decode_invalid_token(self) -> None:
        with pytest.raises(Exception):
            decode_access_token("not.a.token", secret="testsecret")

    def test_decode_wrong_secret(self) -> None:
        token = create_access_token(
            user_id=1, username="admin", role="admin",
            secret="correct", expiry_hours=1,
        )
        with pytest.raises(Exception):
            decode_access_token(token, secret="wrong")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/unit/test_auth_utils.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create directory structure**

```bash
mkdir -p packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers
touch packages/smart_pid_core/src/smart_pid_core/adapters/inbound/__init__.py
touch packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/__init__.py
touch packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/__init__.py
```

- [ ] **Step 4: Implement auth utilities**

Create `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/auth.py`:

```python
"""JWT token and password hashing utilities."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt


def hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a bcrypt hash."""
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_access_token(
    *,
    user_id: int,
    username: str,
    role: str,
    secret: str,
    expiry_hours: int = 8,
) -> str:
    """Create a JWT access token."""
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": datetime.now(tz=UTC) + timedelta(hours=expiry_hours),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_access_token(token: str, *, secret: str) -> dict:
    """Decode and validate a JWT access token. Raises jwt.PyJWTError on failure."""
    return jwt.decode(token, secret, algorithms=["HS256"])
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/core/unit/test_auth_utils.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/ tests/core/unit/test_auth_utils.py
git commit -m "feat(core): add JWT and bcrypt auth utilities"
```

---

## Task 6: LoopManager Command Methods

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/application/loop_manager.py`
- Create: `tests/core/unit/test_loop_manager_commands.py`

- [ ] **Step 1: Write tests for new LoopManager methods**

Create `tests/core/unit/test_loop_manager_commands.py`:

```python
"""Tests for LoopManager command methods (get/set operations)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from smart_pid_core.application.loop_manager import LoopManager
from smart_pid_domain.enums import ControllerMode
from smart_pid_domain.exceptions import ControllerNotFoundError, DomainError
from smart_pid_domain.models.controller import Controller, PIDParams


@pytest.fixture
def bus() -> MagicMock:
    return MagicMock()


@pytest.fixture
def manager(bus: MagicMock) -> LoopManager:
    return LoopManager(bus=bus)


@pytest.fixture
def controller() -> Controller:
    return Controller(
        id=1,
        name="TIC-101",
        pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
        sp_hi_lim=100.0,
        sp_lo_lim=0.0,
        out_hi_lim=100.0,
        out_lo_lim=0.0,
    )


class TestGetController:
    def test_get_existing_controller(
        self, manager: LoopManager, controller: Controller
    ) -> None:
        manager.start_loop(controller)
        result = manager.get_controller(1)
        assert result.name == "TIC-101"
        manager.stop_all()

    def test_get_nonexistent_raises(self, manager: LoopManager) -> None:
        with pytest.raises(ControllerNotFoundError):
            manager.get_controller(999)


class TestSetSetpoint:
    def test_set_valid_setpoint(
        self, manager: LoopManager, controller: Controller
    ) -> None:
        manager.start_loop(controller)
        manager.set_setpoint(1, 55.0)
        c = manager.get_controller(1)
        assert c.sp_hi_lim >= 55.0  # SP is within limits
        manager.stop_all()

    def test_set_setpoint_above_limit_raises(
        self, manager: LoopManager, controller: Controller
    ) -> None:
        manager.start_loop(controller)
        with pytest.raises(DomainError, match="above"):
            manager.set_setpoint(1, 150.0)
        manager.stop_all()

    def test_set_setpoint_below_limit_raises(
        self, manager: LoopManager, controller: Controller
    ) -> None:
        manager.start_loop(controller)
        with pytest.raises(DomainError, match="below"):
            manager.set_setpoint(1, -10.0)
        manager.stop_all()

    def test_set_setpoint_unknown_controller_raises(
        self, manager: LoopManager
    ) -> None:
        with pytest.raises(ControllerNotFoundError):
            manager.set_setpoint(999, 50.0)


class TestSetMode:
    def test_set_valid_mode(
        self, manager: LoopManager, controller: Controller
    ) -> None:
        manager.start_loop(controller)
        manager.set_mode(1, ControllerMode.MAN)
        manager.stop_all()

    def test_set_invalid_mode_raises(
        self, manager: LoopManager, controller: Controller
    ) -> None:
        manager.start_loop(controller)
        with pytest.raises(DomainError):
            manager.set_mode(1, ControllerMode.CAS)  # Not in permitted_modes
        manager.stop_all()


class TestSetOutput:
    def test_set_output_in_man_mode(
        self, manager: LoopManager, controller: Controller
    ) -> None:
        manager.start_loop(controller)
        manager.set_mode(1, ControllerMode.MAN)
        manager.set_output(1, 50.0)
        manager.stop_all()

    def test_set_output_not_in_man_raises(
        self, manager: LoopManager, controller: Controller
    ) -> None:
        manager.start_loop(controller)
        # Default permitted modes are MAN, AUTO — start in AUTO
        with pytest.raises(DomainError, match="MAN"):
            manager.set_output(1, 50.0)
        manager.stop_all()

    def test_set_output_above_limit_raises(
        self, manager: LoopManager, controller: Controller
    ) -> None:
        manager.start_loop(controller)
        manager.set_mode(1, ControllerMode.MAN)
        with pytest.raises(DomainError, match="above"):
            manager.set_output(1, 150.0)
        manager.stop_all()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/unit/test_loop_manager_commands.py -v`
Expected: FAIL — `AttributeError: 'LoopManager' object has no attribute 'get_controller'`

- [ ] **Step 3: Implement LoopManager command methods**

In `packages/smart_pid_core/src/smart_pid_core/application/loop_manager.py`, add the import:

```python
from smart_pid_domain.exceptions import ControllerNotFoundError, DomainError
```

Add these methods to the `LoopManager` class after `get_context()`:

```python
    def get_controller(self, controller_id: int) -> Controller:
        """Return controller config. Raises ControllerNotFoundError if not found."""
        ctx = self._loops.get(controller_id)
        if ctx is None:
            raise ControllerNotFoundError(controller_id)
        return ctx.controller

    def set_setpoint(self, controller_id: int, value: float) -> None:
        """Set SP value. Validates against sp_limits."""
        ctx = self._loops.get(controller_id)
        if ctx is None:
            raise ControllerNotFoundError(controller_id)
        c = ctx.controller
        if value > c.sp_hi_lim:
            raise DomainError(f"SP {value} above high limit {c.sp_hi_lim}")
        if value < c.sp_lo_lim:
            raise DomainError(f"SP {value} below low limit {c.sp_lo_lim}")
        ctx.pid_worker.set_sp(value)

    def set_mode(self, controller_id: int, mode: ControllerMode) -> None:
        """Request mode transition. Raises DomainError if rejected."""
        ctx = self._loops.get(controller_id)
        if ctx is None:
            raise ControllerNotFoundError(controller_id)
        from smart_pid_core.domain.services.pid_mode_manager import BlockStatus

        transition = ctx.mode_manager.request_mode(
            current=ctx.pid_worker.current_mode,
            target=mode,
            permitted=ctx.controller.permitted_modes,
            block_status=BlockStatus(),
        )
        if not transition.accepted:
            raise DomainError(transition.rejection_reason)
        ctx.pid_worker.set_mode(mode)

    def set_output(self, controller_id: int, value: float) -> None:
        """Set CO value in MAN mode only. Validates against out_limits."""
        ctx = self._loops.get(controller_id)
        if ctx is None:
            raise ControllerNotFoundError(controller_id)
        if ctx.pid_worker.current_mode != ControllerMode.MAN:
            raise DomainError("Output can only be set in MAN mode")
        c = ctx.controller
        if value > c.out_hi_lim:
            raise DomainError(f"Output {value} above high limit {c.out_hi_lim}")
        if value < c.out_lo_lim:
            raise DomainError(f"Output {value} below low limit {c.out_lo_lim}")
        ctx.pid_worker.set_output(value)
```

Note: This requires `PIDWorker` to have `set_sp()`, `set_output()`, and `current_mode` property. Check if these exist — if not, add them:

In `packages/smart_pid_core/src/smart_pid_core/application/workers/pid_worker.py`, add:

```python
    @property
    def current_mode(self) -> ControllerMode:
        """Return the current operating mode."""
        return self._mode

    def set_sp(self, value: float) -> None:
        """Update the setpoint. Thread-safe (GIL)."""
        self._controller.sp_hi_lim  # validate controller exists
        # SP is stored on the controller for use in next compute cycle
        self._sp_override = value

    def set_output(self, value: float) -> None:
        """Set manual output value. Only effective in MAN mode."""
        self._co_override = value
```

**Important:** Review the actual PIDWorker implementation to confirm which attributes exist and how SP/CO overrides work. The PIDWorker uses `self._controller` and processes SP from telemetry messages. Add `_sp_override` and `_co_override` fields to PIDWorker.__init__ if needed, and apply them in the `_run()` loop.

If PIDWorker already has `set_mode()` and internal `_mode` attribute, `current_mode` just wraps it. If not, adapt the attribute name to match the existing implementation.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/unit/test_loop_manager_commands.py -v`
Expected: All tests PASS (some tests use MagicMock bus so PIDWorker threads may need handling — adjust mocking if thread start fails).

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/application/loop_manager.py packages/smart_pid_core/src/smart_pid_core/application/workers/pid_worker.py tests/core/unit/test_loop_manager_commands.py
git commit -m "feat(core): add LoopManager command methods (get/set SP, mode, output)"
```

---

## Task 7: FastAPI App Factory + Dependencies + Error Handlers

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py`
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py`
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/error_handlers.py`

- [ ] **Step 1: Create the app factory**

Create `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py`:

```python
"""FastAPI application factory."""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncIterator

from fastapi import FastAPI

from smart_pid_core.adapters.inbound.api.error_handlers import register_error_handlers
from smart_pid_core.adapters.inbound.api.routers import (
    auth,
    commands,
    controllers,
    history,
    system,
)

if TYPE_CHECKING:
    from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
    from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
    from smart_pid_core.adapters.outbound.user_repo import UserRepository
    from smart_pid_core.application.loop_manager import LoopManager
    from smart_pid_core.config import CoreSettings


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.start_time = time.monotonic()
    yield


def create_app(
    *,
    repo: SQLiteRepository,
    historian: SQLiteHistorian,
    user_repo: UserRepository,
    loop_manager: LoopManager,
    settings: CoreSettings,
) -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(title="Smart PID API", version="2.0.0", lifespan=_lifespan)

    # Store dependencies on app.state for injection
    app.state.repo = repo
    app.state.historian = historian
    app.state.user_repo = user_repo
    app.state.loop_manager = loop_manager
    app.state.settings = settings

    # Register routers
    app.include_router(system.router, prefix="/system", tags=["system"])
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(controllers.router, prefix="/config/controllers", tags=["controllers"])
    app.include_router(commands.router, prefix="/command", tags=["commands"])
    app.include_router(history.router, prefix="/history", tags=["history"])

    register_error_handlers(app)

    return app
```

- [ ] **Step 2: Create the dependency injection module**

Create `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py`:

```python
"""FastAPI dependency injection functions."""
from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, HTTPException, Request, status

from smart_pid_core.adapters.inbound.api.auth import decode_access_token
from smart_pid_domain.dtos.auth import UserClaims

if TYPE_CHECKING:
    from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
    from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
    from smart_pid_core.adapters.outbound.user_repo import UserRepository
    from smart_pid_core.application.loop_manager import LoopManager
    from smart_pid_core.config import CoreSettings


def get_repo(request: Request) -> SQLiteRepository:
    return request.app.state.repo


def get_historian(request: Request) -> SQLiteHistorian:
    return request.app.state.historian


def get_user_repo(request: Request) -> UserRepository:
    return request.app.state.user_repo


def get_loop_manager(request: Request) -> LoopManager:
    return request.app.state.loop_manager


def get_settings(request: Request) -> CoreSettings:
    return request.app.state.settings


def get_current_user(request: Request) -> UserClaims:
    """Extract and validate JWT from Authorization header."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    token = auth_header.removeprefix("Bearer ")
    settings: CoreSettings = request.app.state.settings
    try:
        payload = decode_access_token(token, secret=settings.jwt_secret)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return UserClaims(
        user_id=payload["sub"],
        username=payload["username"],
        role=payload["role"],
    )


def require_admin(
    user: Annotated[UserClaims, Depends(get_current_user)],
) -> UserClaims:
    """Verify the current user has admin role."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
```

- [ ] **Step 3: Create error handlers**

Create `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/error_handlers.py`:

```python
"""Global exception handlers mapping domain exceptions to HTTP status codes."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from smart_pid_domain.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ControllerNotFoundError,
    DomainError,
)


def register_error_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app."""

    @app.exception_handler(ControllerNotFoundError)
    async def _controller_not_found(
        request: Request, exc: ControllerNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(DomainError)
    async def _domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(AuthenticationError)
    async def _auth_error(request: Request, exc: AuthenticationError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    @app.exception_handler(AuthorizationError)
    async def _authz_error(request: Request, exc: AuthorizationError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})
```

- [ ] **Step 4: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/
git commit -m "feat(core): add FastAPI app factory, DI, and error handlers"
```

---

## Task 8: API Test Fixtures

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: Add shared API fixtures to conftest**

Append to `tests/conftest.py`:

```python
import httpx
from smart_pid_core.adapters.inbound.api.app import create_app
from smart_pid_core.adapters.inbound.api.auth import create_access_token, hash_password
from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.adapters.outbound.user_repo import UserRepository
from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.loop_manager import LoopManager
from smart_pid_core.config import CoreSettings


@pytest.fixture
async def api_deps(tmp_path):
    """Create all Phase 2 dependencies for API testing."""
    db_path = tmp_path / "test.spid"
    repo = SQLiteRepository(db_path)
    await repo.initialize()
    historian = SQLiteHistorian(repo.db)
    user_repo = UserRepository(repo.db)
    bus = EventBus()
    bus.start()
    loop_manager = LoopManager(bus=bus)
    settings = CoreSettings(jwt_secret="test-secret-key")  # type: ignore[call-arg]

    # Seed admin user
    admin_hash = hash_password("admin")
    await user_repo.create("admin", admin_hash, "admin")

    yield {
        "repo": repo,
        "historian": historian,
        "user_repo": user_repo,
        "loop_manager": loop_manager,
        "settings": settings,
        "bus": bus,
    }
    loop_manager.stop_all()
    bus.stop()


@pytest.fixture
async def app(api_deps):
    """Create FastAPI app with all dependencies."""
    return create_app(
        repo=api_deps["repo"],
        historian=api_deps["historian"],
        user_repo=api_deps["user_repo"],
        loop_manager=api_deps["loop_manager"],
        settings=api_deps["settings"],
    )


@pytest.fixture
async def client(app):
    """httpx AsyncClient with ASGI transport."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def admin_headers(api_deps) -> dict[str, str]:
    """Pre-authenticated admin JWT headers."""
    token = create_access_token(
        user_id=1, username="admin", role="admin",
        secret=api_deps["settings"].jwt_secret,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_headers(api_deps) -> dict[str, str]:
    """Pre-authenticated non-admin JWT headers."""
    token = create_access_token(
        user_id=2, username="operator", role="user",
        secret=api_deps["settings"].jwt_secret,
    )
    return {"Authorization": f"Bearer {token}"}
```

- [ ] **Step 2: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add shared API fixtures (app, client, auth headers)"
```

---

## Task 9: System Router

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/system.py`
- Create: `tests/core/integration/test_api_system.py`

- [ ] **Step 1: Write system router test**

Create `tests/core/integration/test_api_system.py`:

```python
"""Tests for /system endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestSystemStatus:
    @pytest.mark.asyncio
    async def test_status_returns_running(self, client: AsyncClient) -> None:
        resp = await client.get("/system/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["api_version"] == "2.0.0"
        assert "uptime_s" in data
        assert "active_controllers" in data
        assert "bus_active" in data

    @pytest.mark.asyncio
    async def test_status_no_auth_required(self, client: AsyncClient) -> None:
        # No Authorization header — should still work
        resp = await client.get("/system/status")
        assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/integration/test_api_system.py -v`
Expected: FAIL (router not implemented yet)

- [ ] **Step 3: Implement system router**

Create `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/system.py`:

```python
"""System health-check router."""
from __future__ import annotations

import time

from fastapi import APIRouter, Request

from smart_pid_domain.dtos.system import SystemStatusResponse

router = APIRouter()


@router.get("/status", response_model=SystemStatusResponse)
async def system_status(request: Request) -> SystemStatusResponse:
    """Health check — no auth required."""
    start_time = getattr(request.app.state, "start_time", time.monotonic())
    loop_manager = request.app.state.loop_manager
    return SystemStatusResponse(
        status="running",
        uptime_s=round(time.monotonic() - start_time, 1),
        active_controllers=len(loop_manager._loops),
        bus_active=True,
        api_version="2.0.0",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/integration/test_api_system.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/system.py tests/core/integration/test_api_system.py
git commit -m "feat(api): add /system/status health-check endpoint"
```

---

## Task 10: Auth Router

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/auth.py`
- Create: `tests/core/integration/test_api_auth.py`

- [ ] **Step 1: Write auth router tests**

Create `tests/core/integration/test_api_auth.py`:

```python
"""Tests for /auth endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/auth/login", json={"username": "admin", "password": "admin"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/auth/login", json={"username": "admin", "password": "wrong"}
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_unknown_user(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/auth/login", json={"username": "nobody", "password": "x"}
        )
        assert resp.status_code == 401


class TestRegister:
    @pytest.mark.asyncio
    async def test_register_as_admin(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/auth/register",
            json={"username": "newuser", "password": "pass123", "role": "user"},
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "newuser"
        assert data["role"] == "user"

    @pytest.mark.asyncio
    async def test_register_without_auth_fails(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/auth/register",
            json={"username": "hacker", "password": "x"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_register_non_admin_fails(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/auth/register",
            json={"username": "hacker", "password": "x"},
            headers=user_headers,
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_register_duplicate_fails(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/auth/register",
            json={"username": "admin", "password": "x"},
            headers=admin_headers,
        )
        assert resp.status_code == 409


class TestJWTValidation:
    @pytest.mark.asyncio
    async def test_missing_auth_header(self, client: AsyncClient) -> None:
        resp = await client.get("/config/controllers")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/config/controllers", headers={"Authorization": "Bearer invalid.token.here"}
        )
        assert resp.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/integration/test_api_auth.py -v`
Expected: FAIL

- [ ] **Step 3: Implement auth router**

Create `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/auth.py`:

```python
"""Auth router — login and user registration."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from smart_pid_core.adapters.inbound.api.auth import (
    create_access_token,
    hash_password,
    verify_password,
)
from smart_pid_core.adapters.inbound.api.dependencies import (
    get_settings,
    get_user_repo,
    require_admin,
)
from smart_pid_core.adapters.outbound.user_repo import UserRepository
from smart_pid_core.config import CoreSettings
from smart_pid_domain.dtos.auth import (
    LoginRequest,
    TokenResponse,
    UserClaims,
    UserCreate,
)

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    settings: Annotated[CoreSettings, Depends(get_settings)],
) -> TokenResponse:
    user = await user_repo.get_by_username(body.username)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
        secret=settings.jwt_secret,
        expiry_hours=settings.jwt_expiry_hours,
    )
    return TokenResponse(access_token=token)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    body: UserCreate,
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    _admin: Annotated[UserClaims, Depends(require_admin)],
) -> dict:
    existing = await user_repo.get_by_username(body.username)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{body.username}' already exists",
        )
    pw_hash = hash_password(body.password)
    user = await user_repo.create(body.username, pw_hash, body.role)
    return {"id": user.id, "username": user.username, "role": user.role}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/integration/test_api_auth.py -v`
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/auth.py tests/core/integration/test_api_auth.py
git commit -m "feat(api): add /auth/login and /auth/register endpoints"
```

---

## Task 11: Controllers Router

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/controllers.py`
- Create: `tests/core/integration/test_api_controllers.py`

- [ ] **Step 1: Write controllers router tests**

Create `tests/core/integration/test_api_controllers.py`:

```python
"""Tests for /config/controllers CRUD endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestListControllers:
    @pytest.mark.asyncio
    async def test_list_empty(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.get("/config/controllers", headers=user_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/config/controllers")
        assert resp.status_code == 401


class TestCreateController:
    @pytest.mark.asyncio
    async def test_create_as_admin(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/config/controllers",
            json={"name": "TIC-101", "description": "Temperature loop"},
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "TIC-101"
        assert data["id"] > 0

    @pytest.mark.asyncio
    async def test_create_non_admin_forbidden(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/config/controllers",
            json={"name": "TIC-101"},
            headers=user_headers,
        )
        assert resp.status_code == 403


class TestGetController:
    @pytest.mark.asyncio
    async def test_get_existing(
        self, client: AsyncClient, admin_headers: dict[str, str], user_headers: dict[str, str]
    ) -> None:
        create_resp = await client.post(
            "/config/controllers",
            json={"name": "TIC-101"},
            headers=admin_headers,
        )
        cid = create_resp.json()["id"]
        resp = await client.get(f"/config/controllers/{cid}", headers=user_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "TIC-101"

    @pytest.mark.asyncio
    async def test_get_not_found(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.get("/config/controllers/9999", headers=user_headers)
        assert resp.status_code == 404


class TestUpdateController:
    @pytest.mark.asyncio
    async def test_update_as_admin(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        create_resp = await client.post(
            "/config/controllers",
            json={"name": "TIC-101"},
            headers=admin_headers,
        )
        cid = create_resp.json()["id"]
        resp = await client.put(
            f"/config/controllers/{cid}",
            json={"description": "Updated"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "Updated"


class TestDeleteController:
    @pytest.mark.asyncio
    async def test_delete_as_admin(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        create_resp = await client.post(
            "/config/controllers",
            json={"name": "TIC-101"},
            headers=admin_headers,
        )
        cid = create_resp.json()["id"]
        resp = await client.delete(f"/config/controllers/{cid}", headers=admin_headers)
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_not_found(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.delete("/config/controllers/9999", headers=admin_headers)
        assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/integration/test_api_controllers.py -v`
Expected: FAIL

- [ ] **Step 3: Implement controllers router**

Create `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/controllers.py`:

```python
"""Controller CRUD router."""
from __future__ import annotations

from dataclasses import replace
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_repo,
    require_admin,
    get_current_user,
)
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_domain.dtos.auth import UserClaims
from smart_pid_domain.dtos.controllers import (
    ControllerCreate,
    ControllerResponse,
    ControllerUpdate,
)
from smart_pid_domain.exceptions import ControllerNotFoundError
from smart_pid_domain.models.controller import Controller, PIDParams

router = APIRouter()


def _to_response(c: Controller) -> ControllerResponse:
    """Convert domain Controller to API response DTO."""
    return ControllerResponse(
        id=c.id,
        name=c.name,
        description=c.description,
        mode=str(c.mode_normal),
        pv=0.0,
        sp=0.0,
        co=0.0,
        scan_rate_ms=c.scan_rate_ms,
        gain=c.pid_params.gain,
        reset=c.pid_params.reset,
        rate=c.pid_params.rate,
        sp_hi_lim=c.sp_hi_lim,
        sp_lo_lim=c.sp_lo_lim,
        out_hi_lim=c.out_hi_lim,
        out_lo_lim=c.out_lo_lim,
    )


@router.get("", response_model=list[ControllerResponse])
async def list_controllers(
    _user: Annotated[UserClaims, Depends(get_current_user)],
    repo: Annotated[SQLiteRepository, Depends(get_repo)],
) -> list[ControllerResponse]:
    controllers = await repo.list_all()
    return [_to_response(c) for c in controllers]


@router.post("", response_model=ControllerResponse, status_code=status.HTTP_201_CREATED)
async def create_controller(
    body: ControllerCreate,
    _admin: Annotated[UserClaims, Depends(require_admin)],
    repo: Annotated[SQLiteRepository, Depends(get_repo)],
) -> ControllerResponse:
    controller = Controller(
        id=0,
        name=body.name,
        description=body.description,
        scan_rate_ms=body.scan_rate_ms,
        pid_params=PIDParams(gain=body.gain, reset=body.reset, rate=body.rate),
        sp_hi_lim=body.sp_hi_lim,
        sp_lo_lim=body.sp_lo_lim,
        out_hi_lim=body.out_hi_lim,
        out_lo_lim=body.out_lo_lim,
    )
    saved = await repo.save(controller)
    return _to_response(saved)


@router.get("/{controller_id}", response_model=ControllerResponse)
async def get_controller(
    controller_id: int,
    _user: Annotated[UserClaims, Depends(get_current_user)],
    repo: Annotated[SQLiteRepository, Depends(get_repo)],
) -> ControllerResponse:
    try:
        controller = await repo.get(controller_id)
    except KeyError:
        raise ControllerNotFoundError(controller_id)
    return _to_response(controller)


@router.put("/{controller_id}", response_model=ControllerResponse)
async def update_controller(
    controller_id: int,
    body: ControllerUpdate,
    _admin: Annotated[UserClaims, Depends(require_admin)],
    repo: Annotated[SQLiteRepository, Depends(get_repo)],
) -> ControllerResponse:
    try:
        controller = await repo.get(controller_id)
    except KeyError:
        raise ControllerNotFoundError(controller_id)

    updates: dict = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.description is not None:
        updates["description"] = body.description
    if body.scan_rate_ms is not None:
        updates["scan_rate_ms"] = body.scan_rate_ms
    if body.sp_hi_lim is not None:
        updates["sp_hi_lim"] = body.sp_hi_lim
    if body.sp_lo_lim is not None:
        updates["sp_lo_lim"] = body.sp_lo_lim
    if body.out_hi_lim is not None:
        updates["out_hi_lim"] = body.out_hi_lim
    if body.out_lo_lim is not None:
        updates["out_lo_lim"] = body.out_lo_lim

    # Handle PID params updates
    pid_updates: dict = {}
    if body.gain is not None:
        pid_updates["gain"] = body.gain
    if body.reset is not None:
        pid_updates["reset"] = body.reset
    if body.rate is not None:
        pid_updates["rate"] = body.rate
    if pid_updates:
        updates["pid_params"] = replace(controller.pid_params, **pid_updates)

    if updates:
        controller = replace(controller, **updates)
        await repo.save(controller)

    return _to_response(controller)


@router.delete("/{controller_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_controller(
    controller_id: int,
    _admin: Annotated[UserClaims, Depends(require_admin)],
    repo: Annotated[SQLiteRepository, Depends(get_repo)],
) -> Response:
    try:
        await repo.delete(controller_id)
    except KeyError:
        raise ControllerNotFoundError(controller_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/integration/test_api_controllers.py -v`
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/controllers.py tests/core/integration/test_api_controllers.py
git commit -m "feat(api): add /config/controllers CRUD endpoints"
```

---

## Task 12: Commands Router

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/commands.py`
- Create: `tests/core/integration/test_api_commands.py`

- [ ] **Step 1: Write commands router tests**

Create `tests/core/integration/test_api_commands.py`:

```python
"""Tests for /command endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from smart_pid_domain.models.controller import Controller, PIDParams


async def _create_and_start_controller(api_deps: dict) -> int:
    """Helper: save controller to DB and start its loop."""
    repo = api_deps["repo"]
    ctrl = Controller(id=0, name="TIC-101", pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.0))
    saved = await repo.save(ctrl)
    api_deps["loop_manager"].start_loop(saved)
    return saved.id


class TestSetpointCommand:
    @pytest.mark.asyncio
    async def test_set_valid_setpoint(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        cid = await _create_and_start_controller(api_deps)
        resp = await client.post(
            "/command/setpoint",
            json={"controller_id": cid, "value": 55.0},
            headers=user_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    @pytest.mark.asyncio
    async def test_setpoint_above_limit(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        cid = await _create_and_start_controller(api_deps)
        resp = await client.post(
            "/command/setpoint",
            json={"controller_id": cid, "value": 150.0},
            headers=user_headers,
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_setpoint_unknown_controller(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/command/setpoint",
            json={"controller_id": 9999, "value": 50.0},
            headers=user_headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_setpoint_no_auth(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/command/setpoint",
            json={"controller_id": 1, "value": 50.0},
        )
        assert resp.status_code == 401


class TestModeCommand:
    @pytest.mark.asyncio
    async def test_set_valid_mode(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        cid = await _create_and_start_controller(api_deps)
        resp = await client.post(
            "/command/mode",
            json={"controller_id": cid, "mode": "MAN"},
            headers=user_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    @pytest.mark.asyncio
    async def test_set_invalid_mode(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        cid = await _create_and_start_controller(api_deps)
        resp = await client.post(
            "/command/mode",
            json={"controller_id": cid, "mode": "CAS"},
            headers=user_headers,
        )
        assert resp.status_code == 400


class TestOutputCommand:
    @pytest.mark.asyncio
    async def test_set_output_in_man_mode(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        cid = await _create_and_start_controller(api_deps)
        # First switch to MAN
        await client.post(
            "/command/mode",
            json={"controller_id": cid, "mode": "MAN"},
            headers=user_headers,
        )
        resp = await client.post(
            "/command/output",
            json={"controller_id": cid, "value": 50.0},
            headers=user_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    @pytest.mark.asyncio
    async def test_set_output_not_in_man_fails(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        cid = await _create_and_start_controller(api_deps)
        resp = await client.post(
            "/command/output",
            json={"controller_id": cid, "value": 50.0},
            headers=user_headers,
        )
        assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/integration/test_api_commands.py -v`
Expected: FAIL

- [ ] **Step 3: Implement commands router**

Create `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/commands.py`:

```python
"""Command router — setpoint, mode, and output changes."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_current_user,
    get_loop_manager,
)
from smart_pid_core.application.loop_manager import LoopManager
from smart_pid_domain.dtos.auth import UserClaims
from smart_pid_domain.dtos.commands import (
    CommandResponse,
    ModeCommand,
    OutputCommand,
    SetpointCommand,
)

router = APIRouter()


@router.post("/setpoint", response_model=CommandResponse)
async def set_setpoint(
    body: SetpointCommand,
    _user: Annotated[UserClaims, Depends(get_current_user)],
    lm: Annotated[LoopManager, Depends(get_loop_manager)],
) -> CommandResponse:
    lm.set_setpoint(body.controller_id, body.value)
    return CommandResponse(
        ok=True,
        controller_id=body.controller_id,
        detail=f"SP set to {body.value}",
    )


@router.post("/mode", response_model=CommandResponse)
async def set_mode(
    body: ModeCommand,
    _user: Annotated[UserClaims, Depends(get_current_user)],
    lm: Annotated[LoopManager, Depends(get_loop_manager)],
) -> CommandResponse:
    lm.set_mode(body.controller_id, body.mode)
    return CommandResponse(
        ok=True,
        controller_id=body.controller_id,
        detail=f"Mode set to {body.mode}",
    )


@router.post("/output", response_model=CommandResponse)
async def set_output(
    body: OutputCommand,
    _user: Annotated[UserClaims, Depends(get_current_user)],
    lm: Annotated[LoopManager, Depends(get_loop_manager)],
) -> CommandResponse:
    lm.set_output(body.controller_id, body.value)
    return CommandResponse(
        ok=True,
        controller_id=body.controller_id,
        detail=f"Output set to {body.value}",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/integration/test_api_commands.py -v`
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/commands.py tests/core/integration/test_api_commands.py
git commit -m "feat(api): add /command/setpoint, /command/mode, /command/output endpoints"
```

---

## Task 13: History Router

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/history.py`
- Create: `tests/core/integration/test_api_history.py`

- [ ] **Step 1: Write history router tests**

Create `tests/core/integration/test_api_history.py`:

```python
"""Tests for /history endpoints."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from smart_pid_domain.enums import SignalStatus
from smart_pid_domain.models.telemetry import TelemetryFrame


class TestHistory:
    @pytest.mark.asyncio
    async def test_query_with_data(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        historian = api_deps["historian"]
        now = datetime.now(tz=UTC)
        frames = [
            TelemetryFrame(
                controller_id=1, pv=50.0 + i, sp=50.0, co=25.0,
                integral_val=0.0, timestamp=now + timedelta(seconds=i),
                status=SignalStatus.GOOD,
            )
            for i in range(5)
        ]
        await historian.write_batch(frames)

        resp = await client.get(
            "/history/1",
            params={
                "start": (now - timedelta(minutes=1)).isoformat(),
                "end": (now + timedelta(minutes=1)).isoformat(),
            },
            headers=user_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["controller_id"] == 1
        assert data["count"] == 5
        assert len(data["frames"]) == 5

    @pytest.mark.asyncio
    async def test_query_empty(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.get(
            "/history/1",
            params={
                "start": "2020-01-01T00:00:00+00:00",
                "end": "2020-01-02T00:00:00+00:00",
            },
            headers=user_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["frames"] == []

    @pytest.mark.asyncio
    async def test_query_default_time_range(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.get("/history/1", headers=user_headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_query_with_limit(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        historian = api_deps["historian"]
        now = datetime.now(tz=UTC)
        frames = [
            TelemetryFrame(
                controller_id=2, pv=50.0, sp=50.0, co=25.0,
                integral_val=0.0, timestamp=now + timedelta(seconds=i),
                status=SignalStatus.GOOD,
            )
            for i in range(10)
        ]
        await historian.write_batch(frames)

        resp = await client.get(
            "/history/2",
            params={"limit": 3},
            headers=user_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["count"] == 3

    @pytest.mark.asyncio
    async def test_query_no_auth_fails(self, client: AsyncClient) -> None:
        resp = await client.get("/history/1")
        assert resp.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/integration/test_api_history.py -v`
Expected: FAIL

- [ ] **Step 3: Implement history router**

Create `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/history.py`:

```python
"""History query router."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from smart_pid_core.adapters.inbound.api.dependencies import get_current_user, get_historian
from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_domain.dtos.auth import UserClaims
from smart_pid_domain.dtos.history import HistoryResponse, TelemetryFrameDTO

router = APIRouter()


@router.get("/{controller_id}", response_model=HistoryResponse)
async def query_history(
    controller_id: int,
    _user: Annotated[UserClaims, Depends(get_current_user)],
    historian: Annotated[SQLiteHistorian, Depends(get_historian)],
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=10000),
) -> HistoryResponse:
    now = datetime.now(tz=UTC)
    if start is None:
        start = now - timedelta(hours=1)
    if end is None:
        end = now

    frames = await historian.query(controller_id, start, end)

    # Apply limit
    frames = frames[:limit]

    frame_dtos = [
        TelemetryFrameDTO(
            timestamp=f.timestamp,
            pv=f.pv,
            sp=f.sp,
            co=f.co,
            mode="AUTO",
            status=str(f.status),
        )
        for f in frames
    ]

    return HistoryResponse(
        controller_id=controller_id,
        frames=frame_dtos,
        count=len(frame_dtos),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/integration/test_api_history.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/history.py tests/core/integration/test_api_history.py
git commit -m "feat(api): add /history/{controller_id} query endpoint"
```

---

## Task 14: Telemetry Publisher

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/application/telemetry_publisher.py`
- Create: `tests/core/integration/test_telemetry_publisher.py`

- [ ] **Step 1: Write telemetry publisher tests**

Create `tests/core/integration/test_telemetry_publisher.py`:

```python
"""Tests for TelemetryPublisher — bridge from inproc EventBus to tcp ZMQ PUB."""
from __future__ import annotations

import asyncio
import time

import msgpack
import zmq
import zmq.asyncio

import pytest

from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.telemetry_publisher import TelemetryPublisher


class TestTelemetryPublisher:
    @pytest.mark.asyncio
    async def test_republishes_status_topic(self) -> None:
        bus = EventBus()
        bus.start()
        time.sleep(0.05)

        publisher = TelemetryPublisher(bus=bus, publish_port=15555)
        await publisher.start()

        # External SUB socket (simulates HMI client)
        ctx = zmq.asyncio.Context()
        sub = ctx.socket(zmq.SUB)
        sub.connect("tcp://127.0.0.1:15555")
        sub.subscribe(b"STATUS.")
        await asyncio.sleep(0.1)  # Allow subscription to propagate

        # Publish on internal bus
        internal_pub = bus.create_publisher()
        payload = msgpack.packb({"controller_id": 1, "pv": 50.0, "sp": 50.0})
        internal_pub.send(b"STATUS.1", payload)

        # Receive on external socket
        if sub.poll(timeout=2000):
            parts = await sub.recv_multipart()
            assert parts[0] == b"STATUS.1"
            data = msgpack.unpackb(parts[1])
            assert data["pv"] == 50.0
        else:
            pytest.fail("Did not receive republished message within timeout")

        await publisher.stop()
        sub.close()
        ctx.term()
        bus.stop()

    @pytest.mark.asyncio
    async def test_republishes_action_topic(self) -> None:
        bus = EventBus()
        bus.start()
        time.sleep(0.05)

        publisher = TelemetryPublisher(bus=bus, publish_port=15556)
        await publisher.start()

        ctx = zmq.asyncio.Context()
        sub = ctx.socket(zmq.SUB)
        sub.connect("tcp://127.0.0.1:15556")
        sub.subscribe(b"ACTION.CTRL.")
        await asyncio.sleep(0.1)

        internal_pub = bus.create_publisher()
        payload = msgpack.packb({"controller_id": 1, "co": 75.0})
        internal_pub.send(b"ACTION.CTRL.1", payload)

        if sub.poll(timeout=2000):
            parts = await sub.recv_multipart()
            assert parts[0] == b"ACTION.CTRL.1"
            data = msgpack.unpackb(parts[1])
            assert data["co"] == 75.0
        else:
            pytest.fail("Did not receive republished action within timeout")

        await publisher.stop()
        sub.close()
        ctx.term()
        bus.stop()

    @pytest.mark.asyncio
    async def test_stop_is_clean(self) -> None:
        bus = EventBus()
        bus.start()
        time.sleep(0.05)

        publisher = TelemetryPublisher(bus=bus, publish_port=15557)
        await publisher.start()
        await publisher.stop()
        bus.stop()
        # No assertion — just verifying no hang or exception
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/integration/test_telemetry_publisher.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement TelemetryPublisher**

Create `packages/smart_pid_core/src/smart_pid_core/application/telemetry_publisher.py`:

```python
"""Telemetry Publisher — bridge from internal EventBus to external ZMQ PUB socket."""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import zmq
import zmq.asyncio

import structlog

if TYPE_CHECKING:
    from smart_pid_core.application.event_bus import EventBus

logger = structlog.get_logger()

# Topics to bridge from internal bus to external PUB
_BRIDGE_TOPICS = [b"STATUS.", b"ACTION.CTRL."]


class TelemetryPublisher:
    """Unidirectional bridge: subscribes to internal EventBus (inproc://)
    and republishes on ZMQ PUB socket (tcp://0.0.0.0:{port}).
    """

    def __init__(self, bus: EventBus, publish_port: int = 5555) -> None:
        self._bus = bus
        self._port = publish_port
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        """Start the publisher as an asyncio task."""
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run())
        logger.info("telemetry_publisher_started", port=self._port)

    async def stop(self) -> None:
        """Signal stop and wait for the task to finish."""
        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("telemetry_publisher_stopped")

    async def _run(self) -> None:
        """Main loop: receive from internal bus subscribers, publish externally."""
        ctx = zmq.asyncio.Context()
        pub_socket = ctx.socket(zmq.PUB)
        pub_socket.bind(f"tcp://0.0.0.0:{self._port}")

        # Create internal subscribers for each topic prefix
        subscribers = []
        for topic in _BRIDGE_TOPICS:
            sub = self._bus.create_subscriber(topic)
            subscribers.append(sub)

        try:
            while not self._stop_event.is_set():
                for sub in subscribers:
                    result = sub.recv(timeout_ms=10)
                    if result is not None:
                        topic, payload = result
                        await pub_socket.send_multipart([topic, payload])
                await asyncio.sleep(0.001)
        except asyncio.CancelledError:
            pass
        finally:
            pub_socket.setsockopt(zmq.LINGER, 0)
            pub_socket.close()
            ctx.term()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/integration/test_telemetry_publisher.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/application/telemetry_publisher.py tests/core/integration/test_telemetry_publisher.py
git commit -m "feat(core): add TelemetryPublisher (inproc→tcp ZMQ bridge)"
```

---

## Task 15: Integrate into main.py

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/main.py`

- [ ] **Step 1: Update main.py to wire Phase 2 components**

Replace the contents of `packages/smart_pid_core/src/smart_pid_core/main.py` with:

```python
"""Smart PID Core Engine — backend daemon entry point."""
from __future__ import annotations

import asyncio
import logging
import signal
import sys

import structlog
import uvicorn

from smart_pid_core.adapters.inbound.api.app import create_app
from smart_pid_core.adapters.inbound.api.auth import hash_password
from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.adapters.outbound.user_repo import UserRepository
from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.loop_manager import LoopManager
from smart_pid_core.application.telemetry_publisher import TelemetryPublisher
from smart_pid_core.config import CoreSettings

logger = structlog.get_logger()


async def run_daemon(settings: CoreSettings) -> None:
    """Bootstrap and run the backend daemon until interrupted."""
    logger.info("starting_daemon", api_port=settings.api_port, zmq_port=settings.zmq_publish_port)

    # Phase 1 components
    repo = SQLiteRepository(settings.db_path)
    await repo.initialize()
    historian = SQLiteHistorian(repo.db)
    bus = EventBus()
    bus.start()
    loop_manager = LoopManager(bus=bus)
    logger.info("event_bus_started")

    # Phase 2: User repo + seed admin
    user_repo = UserRepository(repo.db)
    users = await user_repo.list_all()
    if not users:
        admin_hash = hash_password("admin")
        await user_repo.create("admin", admin_hash, "admin")
        logger.warning("seeded_default_admin", msg="Change default admin password!")

    # Phase 2: FastAPI
    app = create_app(
        repo=repo,
        historian=historian,
        user_repo=user_repo,
        loop_manager=loop_manager,
        settings=settings,
    )

    # Phase 2: Telemetry Publisher
    telemetry_pub = TelemetryPublisher(bus=bus, publish_port=settings.zmq_publish_port)
    await telemetry_pub.start()

    # Embedded uvicorn
    uv_config = uvicorn.Config(
        app=app,
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
    )
    server = uvicorn.Server(uv_config)

    stop_event = asyncio.Event()

    def handle_signal() -> None:
        logger.info("shutdown_signal_received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    # Run uvicorn and wait for shutdown signal concurrently
    server_task = asyncio.create_task(server.serve())
    logger.info("daemon_ready")

    await stop_event.wait()
    logger.info("shutting_down")

    # Graceful shutdown in correct order
    server.should_exit = True
    await server_task
    await telemetry_pub.stop()
    loop_manager.stop_all()
    bus.stop()
    logger.info("daemon_stopped")


def main() -> None:
    """CLI entry point."""
    try:
        settings = CoreSettings()  # type: ignore[call-arg]
    except Exception as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        print("Ensure SPID_JWT_SECRET is set in environment or .env file.", file=sys.stderr)
        sys.exit(1)

    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
    )
    asyncio.run(run_daemon(settings))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify import works**

Run: `uv run python -c "from smart_pid_core.main import main; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: ALL tests pass (Phase 1 + Phase 2).

- [ ] **Step 4: Run linter**

Run: `uv run --with ruff ruff check .`
Fix any issues that come up.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/main.py
git commit -m "feat(core): integrate FastAPI, auth, telemetry publisher into daemon"
```

---

## Summary

| Task | Component | Files | Tests |
|------|-----------|-------|-------|
| 1 | Dependencies | 1 modified | — |
| 2 | DTOs | 7 created | 12 tests |
| 3 | ControllerNotFoundError | 1 modified | 3 tests |
| 4 | UserRepository | 1 created | 4 tests |
| 5 | Auth utilities | 4 created | 4 tests |
| 6 | LoopManager commands | 1 modified | 8+ tests |
| 7 | App factory + DI + errors | 3 created | — |
| 8 | Test fixtures | 1 modified | — |
| 9 | System router | 1 created | 2 tests |
| 10 | Auth router | 1 created | 7 tests |
| 11 | Controllers router | 1 created | 7 tests |
| 12 | Commands router | 1 created | 7 tests |
| 13 | History router | 1 created | 5 tests |
| 14 | Telemetry Publisher | 1 created | 3 tests |
| 15 | main.py integration | 1 modified | — |

**Total: ~25 new files, 3 modified, ~62 tests**

### Parallelization Notes

Tasks that can be worked on in parallel by subagents:
- **Group A (domain, no deps):** Tasks 2, 3
- **Group B (core, independent):** Tasks 4, 5, 6
- **Group C (routers, after 7+8):** Tasks 9, 10, 11, 12, 13
- **Group D (independent):** Task 14

Tasks 1, 7, 8, 15 are sequential prerequisites/wiring.
