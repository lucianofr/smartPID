# Phase 2: REST API + Auth + Telemetry Publisher — Design Spec

**Date:** 2026-04-03
**Status:** Draft
**Depends on:** Phase 1 (Foundation + Domain + PID Core) ✅

---

## 1. Overview

Phase 2 adds three components to the existing backend:

1. **FastAPI REST API** — HTTP endpoints for controller CRUD, history queries, and commands
2. **Auth (JWT + bcrypt)** — User authentication and basic RBAC (admin vs user)
3. **Telemetry Publisher** — Bridge from internal EventBus (inproc://) to external ZMQ PUB (tcp://5555)

No HMI in this phase. The backend becomes a fully functional server that any HTTP client can interact with and any ZMQ SUB client can receive live telemetry from.

### Scope boundaries

- **In scope:** FastAPI app, auth, CRUD, history, commands, telemetry publisher, DTOs, tests
- **Out of scope:** HMI (Phase 3), OPC-UA (Phase 3), alarms, project management, export, fine-grained RBAC

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────┐
│  main.py (asyncio event loop)                       │
│                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │ LoopManager   │  │ EventBus     │  │ SQLite    │ │
│  │ (Phase 1) ✅  │  │ (Phase 1) ✅ │  │(Phase 1)✅│ │
│  └──────┬───────┘  └──────┬───────┘  └─────┬─────┘ │
│         │                 │                 │       │
│  ┌──────┴─────────────────┴─────────────────┴─────┐ │
│  │              DI Container (dependencies.py)     │ │
│  └──────┬─────────────────┬─────────────────┬─────┘ │
│         │                 │                 │       │
│  ┌──────▼───────┐  ┌─────▼──────┐  ┌──────▼─────┐ │
│  │ FastAPI       │  │ Auth       │  │ Telemetry  │ │
│  │ Routers      │  │ Middleware │  │ Publisher  │ │
│  │ (NEW Phase 2)│  │(NEW Ph. 2) │  │(NEW Ph. 2) │ │
│  └──────────────┘  └────────────┘  └────────────┘ │
│         │                                    │      │
│    port 8000                          tcp://5555    │
│    (HTTP REST)                        (ZMQ PUB)     │
└─────────────────────────────────────────────────────┘
```

### Lifecycle in `main.py`

1. Initialize SQLite repo + EventBus + LoopManager (existing)
2. Create UserRepository, seed admin user if table empty
3. Create FastAPI app via `create_app()` factory, inject dependencies
4. Start Telemetry Publisher (asyncio task)
5. Start uvicorn.Server embedded in the same asyncio loop
6. Graceful shutdown: stop uvicorn → stop telemetry publisher → stop workers → stop bus

### Uvicorn Integration

Uvicorn runs embedded via `uvicorn.Server(config).serve()` as an asyncio task. Single event loop for the entire backend. No separate process or thread.

---

## 3. FastAPI REST API

### 3.1 App Factory (`adapters/inbound/api/app.py`)

```python
def create_app(
    repo: SQLiteRepository,
    historian: SQLiteHistorian,
    user_repo: UserRepository,
    loop_manager: LoopManager,
    settings: CoreSettings,
) -> FastAPI:
```

Uses `lifespan` context manager. Dependencies stored in `app.state` and exposed via `dependencies.py`.

### 3.2 Routers and Endpoints

| Router | Endpoint | Method | Auth | Description |
|--------|----------|--------|------|-------------|
| `auth` | `/auth/login` | POST | No | Returns JWT token |
| `auth` | `/auth/register` | POST | Admin | Creates user |
| `controllers` | `/config/controllers` | GET | Yes | List all controllers |
| `controllers` | `/config/controllers` | POST | Admin | Create controller |
| `controllers` | `/config/controllers/{id}` | GET | Yes | Controller detail |
| `controllers` | `/config/controllers/{id}` | PUT | Admin | Update controller |
| `controllers` | `/config/controllers/{id}` | DELETE | Admin | Delete controller |
| `history` | `/history/{controller_id}` | GET | Yes | Query params: `start`, `end`, `limit` |
| `commands` | `/command/setpoint` | POST | Yes | Body: `{controller_id, value}` |
| `commands` | `/command/mode` | POST | Yes | Body: `{controller_id, mode}` |
| `commands` | `/command/output` | POST | Yes | Body: `{controller_id, value}` — MAN mode only |
| `system` | `/system/status` | GET | No | Health check |

### 3.3 Dependency Injection (`dependencies.py`)

Functions that read from `request.app.state`:
- `get_repo() → SQLiteRepository`
- `get_historian() → SQLiteHistorian`
- `get_user_repo() → UserRepository`
- `get_loop_manager() → LoopManager`
- `get_settings() → CoreSettings`
- `get_current_user() → UserClaims` (decodes JWT from `Authorization: Bearer <token>`)
- `require_admin() → UserClaims` (calls `get_current_user()`, checks `role == "admin"`)

### 3.4 Error Handling

Global exception handlers map domain exceptions to HTTP status codes:
- `ControllerNotFoundError` → 404
- `DomainError` → 400
- `AuthError` → 401/403
- Unhandled → 500

---

## 4. Auth (JWT + bcrypt)

### 4.1 Users Table

Already in Phase 1 DDL. Schema:

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `username` | TEXT UNIQUE | Login name |
| `password_hash` | TEXT | bcrypt hash |
| `role` | TEXT | "admin" or "user" |
| `created_at` | TEXT | ISO timestamp |

### 4.2 Login Flow

```
POST /auth/login {username, password}
  → bcrypt.checkpw(password, stored_hash)
  → JWT payload: {sub: user_id, username, role, exp}
  → Response: {access_token, token_type: "bearer"}
```

### 4.3 JWT Middleware

Dependency `get_current_user()`:
1. Extract token from `Authorization: Bearer <token>` header
2. Decode with PyJWT using `settings.jwt_secret`
3. Return `UserClaims(user_id, username, role)`
4. Expired or invalid token → 401

Dependency `require_admin()`:
1. Calls `get_current_user()`
2. If `role != "admin"` → 403 Forbidden

### 4.4 RBAC Level

Phase 2 implements **admin vs non-admin** only. Fine-grained operator/engineer distinction deferred to Phase 6.

### 4.5 User Repository

New `UserRepository` in SQLite adapter:
- `create(username: str, password_hash: str, role: str) → User`
- `get_by_username(username: str) → User | None`
- `list_all() → list[User]`

### 4.6 Seed Admin

On backend startup, if `users` table is empty, create default admin:
- username: `admin`, password: `admin` (bcrypt hashed)
- Log warning urging password change

---

## 5. Telemetry Publisher

### 5.1 Responsibility

Unidirectional bridge: subscribes to internal EventBus (`inproc://`) and republishes on ZMQ PUB socket (`tcp://0.0.0.0:5555`). Only component that exposes internal data to the network.

### 5.2 Topics (Phase 2)

| Internal topic | External topic | Payload |
|----------------|----------------|---------|
| `STATUS.{id}` | `STATUS.{id}` | Enriched telemetry (msgpack) |
| `ACTION.CTRL.{id}` | `ACTION.CTRL.{id}` | ControlAction (msgpack) |

Future topics (`EVENT.ALARM.*`, `LOG.AI.*`, `SYS.STATE`) added in corresponding phases.

### 5.3 Implementation

```python
class TelemetryPublisher:
    def __init__(self, bus: EventBus, publish_port: int = 5555): ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
```

- Runs as **asyncio task** on the main loop (not a separate thread)
- Uses `zmq.asyncio.Context` for event loop integration
- Subscribe patterns: `b"STATUS."`, `b"ACTION.CTRL."`
- Shutdown: `linger=0` to avoid blocking (same pattern as Phase 1)

### 5.4 Location

`packages/smart_pid_core/src/smart_pid_core/application/telemetry_publisher.py`

---

## 6. Commands — REST → LoopManager Integration

### 6.1 Command Flow

```
POST /command/setpoint {controller_id: 1, value: 55.0}
  → Router validates DTO + auth
  → LoopManager.get_controller(id) → Controller
  → Modifies controller.sp (respecting sp_limits)
  → LoopManager.update_controller(id, controller)
  → PID Worker uses new SP on next scan cycle
  → Response: 200 {ok: true, controller_id, detail}
```

### 6.2 New LoopManager Methods

| Method | Description |
|--------|-------------|
| `get_controller(id) → Controller` | Returns current controller state |
| `update_controller(id, controller) → Controller` | Updates state, worker picks up next cycle |
| `set_setpoint(id, value)` | Validates sp_limits, updates sp |
| `set_mode(id, mode)` | Delegates to ModeManager, validates transition |
| `set_output(id, value)` | MAN mode only, validates out_limits |

### 6.3 Validation Rules

| Command | Validation |
|---------|------------|
| `setpoint` | `sp_lo <= value <= sp_hi` (SP is stored; PID uses it when in Auto/Cas) |
| `mode` | ModeManager validates permitted transition, returns error if invalid |
| `output` | Controller must be in MAN mode, `out_lo <= value <= out_hi` |

---

## 7. DTOs (`smart_pid_domain`)

All API request/response schemas live in `smart_pid_domain/dtos/` so the HMI can reuse them.

### 7.1 Auth DTOs (`dtos/auth.py`)

```python
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

### 7.2 Command DTOs (`dtos/commands.py`)

```python
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

### 7.3 Controller DTOs (`dtos/controllers.py`)

```python
class ControllerCreate(BaseModel):
    tag_name: str
    description: str = ""
    # PID params, limits — optional fields with defaults

class ControllerUpdate(BaseModel):
    # All fields optional for partial update
    tag_name: str | None = None
    description: str | None = None
    ...

class ControllerResponse(BaseModel):
    id: int
    tag_name: str
    description: str
    mode: str
    pv: float
    sp: float
    co: float
    # Relevant fields from Controller model
```

### 7.4 History DTOs (`dtos/history.py`)

```python
class HistoryQuery(BaseModel):
    start: datetime | None = None   # default: 1h ago
    end: datetime | None = None     # default: now
    limit: int = 1000

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

### 7.5 System DTOs (`dtos/system.py`)

```python
class SystemStatusResponse(BaseModel):
    status: str             # "running"
    uptime_s: float
    active_controllers: int
    bus_active: bool
    api_version: str
```

### 7.6 DTO Organization

```
smart_pid_domain/
├── dtos/
│   ├── __init__.py       # Re-exports all DTOs
│   ├── auth.py
│   ├── commands.py
│   ├── controllers.py
│   ├── history.py
│   └── system.py
```

---

## 8. File Structure

### 8.1 New Files

```
packages/smart_pid_domain/src/smart_pid_domain/
├── dtos/
│   ├── __init__.py
│   ├── auth.py
│   ├── commands.py
│   ├── controllers.py
│   ├── history.py
│   └── system.py

packages/smart_pid_core/src/smart_pid_core/
├── adapters/inbound/
│   ├── __init__.py
│   └── api/
│       ├── __init__.py
│       ├── app.py
│       ├── dependencies.py
│       ├── auth.py
│       └── routers/
│           ├── __init__.py
│           ├── auth.py
│           ├── controllers.py
│           ├── history.py
│           ├── commands.py
│           └── system.py
├── adapters/outbound/
│   └── user_repo.py
├── application/
│   └── telemetry_publisher.py

tests/
├── core/integration/
│   ├── test_api_auth.py
│   ├── test_api_controllers.py
│   ├── test_api_history.py
│   ├── test_api_commands.py
│   ├── test_api_system.py
│   └── test_telemetry_publisher.py
```

### 8.2 Modified Files

| File | Change |
|------|--------|
| `main.py` | Add FastAPI app creation, TelemetryPublisher, embedded uvicorn |
| `loop_manager.py` | Add `get_controller()`, `update_controller()`, `set_setpoint()`, `set_mode()`, `set_output()` |
| `sqlite_repo.py` | Add users table DDL (if not already present) |

### 8.3 New Dependencies (`smart_pid_core/pyproject.toml`)

```toml
dependencies = [
    # Existing: pyzmq, msgpack, aiosqlite, pydantic-settings, structlog
    # New Phase 2:
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "pyjwt>=2.9",
    "bcrypt>=4.2",
]

[project.optional-dependencies]
dev = [
    # Existing: pytest, pytest-asyncio, pytest-mock, ruff, mypy
    # New Phase 2:
    "httpx>=0.28",
]
```

---

## 9. Testing Strategy

All tests use **httpx.AsyncClient** with pytest-asyncio, consistent with Phase 1 patterns.

### 9.1 Test Plan

| Test file | Coverage |
|-----------|----------|
| `test_api_auth.py` | Login success/failure, register, JWT validation, expired token, missing header |
| `test_api_controllers.py` | CRUD operations, validation errors, not found, admin-only enforcement |
| `test_api_history.py` | Query with time range, empty results, limit |
| `test_api_commands.py` | Setpoint/mode/output commands, validation (limits, mode restrictions), unauthorized |
| `test_api_system.py` | Health check response format |
| `test_telemetry_publisher.py` | Publish on internal bus → receive on tcp SUB socket |

### 9.2 Test Fixtures

Shared `conftest.py` with:
- `app` — FastAPI app with real SQLite (tmp_path), seeded admin user
- `client` — `httpx.AsyncClient(transport=ASGITransport(app))`
- `auth_headers` — Pre-authenticated JWT headers for convenience
- `admin_headers` — Admin JWT headers

---

## 10. Decisions Summary

| Decision | Choice | Reason |
|----------|--------|--------|
| Phase 2 scope | V2 Spec (no HMI) | Backend-first, solid foundation |
| Auth | Real JWT + bcrypt | Infrastructure ready from day one |
| RBAC granularity | admin vs user | Fine-grained deferred to Phase 6 |
| Commands | Local effect (no OPC-UA) | LoopManager + ModeManager already exist |
| DTOs location | `smart_pid_domain` | Shared between core and future HMI |
| API structure | Layered routers | Idiomatic FastAPI, clean separation |
| Uvicorn | Embedded in main loop | Single event loop, simple DI and shutdown |
| Tests | httpx.AsyncClient | Consistent with pytest-asyncio pattern |
