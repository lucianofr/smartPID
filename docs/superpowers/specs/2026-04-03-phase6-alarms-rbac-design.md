# Phase 6: Alarms + RBAC Enforcement — Design Spec

**Date:** 2026-04-03
**Status:** Approved
**Depends on:** Phase 2 (auth/JWT), Phase 3a (HMI desktop)
**Parallel with:** Phase 5 (AI), Phase 3b (OPC-UA) — no direct dependency

---

## 1. Overview

Phase 6 adds two major subsystems to the Smart PID Edge Platform:

1. **Alarm Engine** — real-time process alarm detection with ISA-18.2 ACK workflow
2. **RBAC Enforcement + Audit Trail** — role-based access on all API endpoints, user management, and compliance-grade audit logging

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Alarm detection | Separate AlarmWorker | Consistent with hexagonal arch; decoupled from PID engine |
| ACK workflow | ISA-18.2 simplified (4 states) | Industry standard for process control |
| RBAC model | Fixed role-based (3 roles, hardcoded) | YAGNI — 3 roles sufficient, no permission table |
| Audit trail | Complete (all write actions) | Industrial compliance requirement |
| HMI alarms | AlarmBar (evolved) + AlarmPanel (new page) | Quick notification + full management |

---

## 2. Alarm Engine

### 2.1 AlarmEngine (Domain Service)

Pure domain service, no I/O. Located at `packages/smart_pid_core/src/smart_pid_core/domain/services/alarm_engine.py`.

**Interface:**

```python
class AlarmEngine:
    def evaluate(
        self,
        controller_id: int,
        pv: float,
        sp: float,
        alarm_config: AlarmConfig,
        sp_ramping: bool,
    ) -> list[AlarmTransition]: ...
```

**AlarmConfig** (dataclass, from controller alarm settings):

```python
@dataclass(frozen=True)
class AlarmConfig:
    hihi_enabled: bool
    hihi_value: float
    hihi_priority: AlarmPriority
    hi_enabled: bool
    hi_value: float
    hi_priority: AlarmPriority
    lo_enabled: bool
    lo_value: float
    lo_priority: AlarmPriority
    lolo_enabled: bool
    lolo_value: float
    lolo_priority: AlarmPriority
    dv_hi_enabled: bool
    dv_hi_value: float
    dv_hi_priority: AlarmPriority
    dv_lo_enabled: bool
    dv_lo_value: float
    dv_lo_priority: AlarmPriority
    deadband_percent: float  # 0.0-50.0, % of alarm limit
```

**Detection logic:**

- Process alarms (HIHI/HI/LO/LOLO): compare PV vs limit
  - HIHI/HI trigger when `PV >= limit`, clear when `PV < (limit - deadband)`
  - LO/LOLO trigger when `PV <= limit`, clear when `PV > (limit + deadband)`
- Deviation alarms (DV_HI/DV_LO): compare `abs(PV - SP)` vs limit
  - DV_HI triggers when `(PV - SP) >= dv_hi_value`
  - DV_LO triggers when `(SP - PV) >= dv_lo_value`
  - **Suppressed** when `sp_ramping=True` (SP ramp active from PID engine)

**State tracking:**

AlarmEngine maintains internal state per `(controller_id, alarm_type)`:

```python
@dataclass
class _AlarmState:
    active: bool = False
    last_value: float = 0.0
    triggered_at: datetime | None = None
```

**AlarmTransition** (return value):

```python
@dataclass(frozen=True)
class AlarmTransition:
    controller_id: int
    alarm_type: AlarmType
    priority: AlarmPriority
    transition: Literal["TRIGGERED", "CLEARED"]
    value: float
    limit: float
    timestamp: datetime
```

### 2.2 AlarmWorker (Application Layer)

Located at `packages/smart_pid_core/src/smart_pid_core/application/workers/alarm_worker.py`.

Daemon thread, same pattern as PIDWorker/DBWorker:

1. Subscribes to `TELEMETRY.*` on ZMQ inproc bus
2. For each TelemetryFrame:
   - Looks up AlarmConfig for the controller (from in-memory cache, refreshed on config change)
   - Calls `AlarmEngine.evaluate(controller_id, pv, sp, config, sp_ramping)`
   - For each AlarmTransition returned:
     - Publishes `ALARM.{controller_id}` on the bus (msgpack serialized)
     - Enqueues for DB persistence via DBWorker
3. Lifecycle managed by LoopManager (start/stop with other workers)

### 2.3 Domain Events

Three new frozen dataclasses in `events.py`:

```python
@dataclass(frozen=True)
class AlarmTriggered:
    controller_id: int
    alarm_type: AlarmType
    priority: AlarmPriority
    value: float
    limit: float
    timestamp: datetime
    event_id: UUID = field(default_factory=uuid4)

@dataclass(frozen=True)
class AlarmCleared:
    controller_id: int
    alarm_type: AlarmType
    value: float
    timestamp: datetime
    event_id: UUID = field(default_factory=uuid4)

@dataclass(frozen=True)
class AlarmAcknowledged:
    controller_id: int
    alarm_type: AlarmType
    user_id: int
    username: str
    timestamp: datetime
    event_id: UUID = field(default_factory=uuid4)
```

### 2.4 AlarmState Enum

New enum in `enums.py`:

```python
class AlarmState(StrEnum):
    UNACKNOWLEDGED = "UNACKNOWLEDGED"   # Active + not ACK'd (red blinking)
    ACKNOWLEDGED = "ACKNOWLEDGED"       # Active + ACK'd (red solid)
    CLEARED_UNACK = "CLEARED_UNACK"     # Cleared + not ACK'd (yellow)
    # CLEARED + ACK'd = removed from active list
```

---

## 3. Alarm Persistence

### 3.1 Database Table: `Log_Alarmes`

```sql
CREATE TABLE IF NOT EXISTS Log_Alarmes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    controller_id INTEGER NOT NULL,
    alarm_type TEXT NOT NULL CHECK(alarm_type IN ('HIHI','HI','LO','LOLO','DV_HI','DV_LO')),
    priority TEXT NOT NULL CHECK(priority IN ('CRITICAL','WARNING','ADVISORY','LOG')),
    value REAL NOT NULL,
    limit_value REAL NOT NULL,
    triggered_at TEXT NOT NULL,
    cleared_at TEXT,
    acknowledged INTEGER NOT NULL DEFAULT 0,
    ack_by_user TEXT,
    ack_at TEXT,
    FOREIGN KEY (controller_id) REFERENCES Controladores(id)
);

CREATE INDEX IF NOT EXISTS idx_alarmes_controller ON Log_Alarmes(controller_id);
CREATE INDEX IF NOT EXISTS idx_alarmes_triggered ON Log_Alarmes(triggered_at);
CREATE INDEX IF NOT EXISTS idx_alarmes_active ON Log_Alarmes(cleared_at, acknowledged);
```

### 3.2 AlarmRepository (Outbound Adapter)

Located at `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/alarm_repo.py`.

```python
class AlarmRepository:
    async def insert_alarm(self, alarm: AlarmTransition) -> int: ...
    async def mark_cleared(self, controller_id: int, alarm_type: AlarmType, cleared_at: datetime) -> None: ...
    async def acknowledge(self, alarm_id: int, username: str, ack_at: datetime) -> None: ...
    async def acknowledge_all(self, username: str, ack_at: datetime) -> int: ...
    async def get_active(self, controller_id: int | None = None, priority: AlarmPriority | None = None) -> list[dict]: ...
    async def get_history(self, start: datetime, end: datetime, controller_id: int | None = None, limit: int = 100, offset: int = 0) -> list[dict]: ...
```

### 3.3 ACK Workflow (ISA-18.2 Simplified)

State machine per alarm instance:

```
TRIGGERED ──────────────────► UNACKNOWLEDGED
    │                              │
    │ (ACK before clear)           │ (clear before ACK)
    │                              ▼
    │                        CLEARED_UNACK
    │                              │
    ▼                              │ (ACK)
ACKNOWLEDGED ──── (clear) ────► REMOVED (from active list)
    │                              ▲
    └──────────────────────────────┘
```

- An alarm is **active** if `cleared_at IS NULL`
- An alarm is **visible in active list** if `cleared_at IS NULL OR acknowledged = 0`
- An alarm is **removed from active** only when `cleared_at IS NOT NULL AND acknowledged = 1`

---

## 4. RBAC Enforcement

### 4.1 Role Hierarchy

Uses existing `UserRole` enum (ADMIN > SUPERVISOR > OPERATOR):

```python
ROLE_HIERARCHY = {
    UserRole.OPERATOR: 0,
    UserRole.SUPERVISOR: 1,
    UserRole.ADMIN: 2,
}
```

### 4.2 FastAPI Dependencies

Located at `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py`.

```python
def require_authenticated() -> UserClaims: ...   # existing
def require_operator() -> UserClaims: ...         # role >= OPERATOR (all roles)
def require_supervisor() -> UserClaims: ...       # role >= SUPERVISOR
def require_admin() -> UserClaims: ...            # existing, role == ADMIN
```

`require_operator` and `require_supervisor` validate JWT and check role hierarchy. On failure, raise `HTTPException(403)`.

### 4.3 Endpoint Permission Matrix

| Router | Endpoint | Method | Min Role |
|--------|----------|--------|----------|
| `/auth` | `/login` | POST | (none) |
| `/auth` | `/register` | POST | ADMIN |
| `/system` | `/status` | GET | OPERATOR |
| `/config/controllers` | `/` | GET | OPERATOR |
| `/config/controllers` | `/{id}` | GET | OPERATOR |
| `/config/controllers` | `/` | POST | SUPERVISOR |
| `/config/controllers` | `/{id}` | PUT | SUPERVISOR |
| `/config/controllers` | `/{id}` | DELETE | ADMIN |
| `/command` | `/setpoint` | POST | OPERATOR |
| `/command` | `/mode` | POST | OPERATOR |
| `/history` | `/{id}` | GET | OPERATOR |
| `/alarms` | `/active` | GET | OPERATOR |
| `/alarms` | `/history` | GET | OPERATOR |
| `/alarms` | `/{id}/ack` | POST | OPERATOR |
| `/alarms` | `/ack-all` | POST | OPERATOR |
| `/controllers/{id}/ai` | `/` | GET | OPERATOR |
| `/controllers/{id}/ai` | `/` | PUT | SUPERVISOR |
| `/controllers/{id}/stats` | `/` | GET | OPERATOR |
| `/simulator` | `*` | ALL | SUPERVISOR |
| `/opcua` | `*` | ALL | ADMIN |
| `/users` | `*` | ALL | ADMIN |
| `/audit` | `/` | GET | SUPERVISOR |

### 4.4 User Management

**REST Router** at `/users` (ADMIN only):

- `GET /users` — list all users (id, username, role, created_at, active)
- `GET /users/{id}` — user detail
- `PUT /users/{id}` — update role and/or password
- `DELETE /users/{id}` — soft delete (set `active=0`)

**Schema changes to `Usuarios` table:**

```sql
ALTER TABLE Usuarios ADD COLUMN active INTEGER NOT NULL DEFAULT 1;
ALTER TABLE Usuarios ADD COLUMN created_at TEXT NOT NULL DEFAULT (datetime('now'));
```

UserRepository gains: `list_users()`, `get_user(id)`, `update_user(id, role, password_hash)`, `deactivate_user(id)`.

---

## 5. Audit Trail

### 5.1 Database Table: `Log_Auditoria`

```sql
CREATE TABLE IF NOT EXISTS Log_Auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    user_id INTEGER,
    username TEXT NOT NULL,
    action TEXT NOT NULL,
    resource TEXT,
    detail TEXT,
    FOREIGN KEY (user_id) REFERENCES Usuarios(id)
);

CREATE INDEX IF NOT EXISTS idx_auditoria_timestamp ON Log_Auditoria(timestamp);
CREATE INDEX IF NOT EXISTS idx_auditoria_user ON Log_Auditoria(user_id);
CREATE INDEX IF NOT EXISTS idx_auditoria_action ON Log_Auditoria(action);
```

### 5.2 Action Types

```python
class AuditAction(StrEnum):
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    SP_CHANGE = "SP_CHANGE"
    MODE_CHANGE = "MODE_CHANGE"
    ACK_ALARM = "ACK_ALARM"
    ACK_ALARM_ALL = "ACK_ALARM_ALL"
    TUNE_PID = "TUNE_PID"
    CONFIG_AI = "CONFIG_AI"
    CONFIG_ALARM = "CONFIG_ALARM"
    CREATE_CONTROLLER = "CREATE_CONTROLLER"
    UPDATE_CONTROLLER = "UPDATE_CONTROLLER"
    DELETE_CONTROLLER = "DELETE_CONTROLLER"
    CREATE_USER = "CREATE_USER"
    UPDATE_USER = "UPDATE_USER"
    DEACTIVATE_USER = "DEACTIVATE_USER"
    SIMULATOR_CONFIG = "SIMULATOR_CONFIG"
    OPCUA_CONFIG = "OPCUA_CONFIG"
```

### 5.3 AuditRepository (Outbound Adapter)

Located at `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/audit_repo.py`.

```python
class AuditRepository:
    async def record(self, user_id: int, username: str, action: AuditAction, resource: str | None, detail: str | None) -> None: ...
    async def get_history(self, start: datetime, end: datetime, user_id: int | None = None, action: AuditAction | None = None, limit: int = 100, offset: int = 0) -> list[dict]: ...
```

### 5.4 Implementation Strategy

Two approaches combined:

1. **Explicit calls in handlers** — for actions with meaningful context (login, ACK, SP change). The handler calls `audit_repo.record(...)` directly with structured detail (JSON with old/new values).

2. **Utility function** — `audit_log(request, action, resource, detail)` helper that extracts UserClaims from the request and calls the repository. Used in route handlers, not as middleware (middleware would lack semantic context about what action was performed).

### 5.5 REST Endpoint

`GET /audit` (SUPERVISOR+):
- Query params: `start`, `end`, `user_id`, `action`, `limit`, `offset`
- Returns paginated list of audit entries

---

## 6. HMI Changes

### 6.1 AlarmBar (Evolution)

File: `packages/smart_pid_hmi/src/smart_pid_hmi/widgets/alarm_bar.py` (exists).

Changes:
- Add priority counters display: `CRITICAL: N | WARNING: N | ADVISORY: N`
- Blink animation when UNACKNOWLEDGED alarms exist
- Click handler opens dropdown with last 5 active alarms
- "Open Alarm Panel" button in dropdown
- Receives alarm transitions via BusBridge (ZMQ SUB `ALARM.*`)

### 6.2 AlarmPanel (New Page)

File: `packages/smart_pid_hmi/src/smart_pid_hmi/pages/alarm_panel.py` (new).

Layout:
- **Top section**: Active alarms table (QTableWidget)
  - Columns: Controller, Type, Priority, Value, Limit, Triggered At, Status
  - Row colors per ISA-101: CRITICAL=red, WARNING=yellow, ADVISORY=blue, LOG=gray
  - UNACKNOWLEDGED rows blink
  - Selection + "ACK Selected" / "ACK All" buttons
- **Bottom section**: Alarm history table
  - Same columns + Cleared At, ACK By, ACK At
  - Filter bar: controller combo, priority combo, date range pickers
- Auto-refresh via BusBridge timer (same pattern as DashboardPage)

### 6.3 Toolbar Navigation

MainWindow toolbar updated: **Dashboard | Simulator | Alarms**

### 6.4 HMI Permission Awareness

After login, UserClaims (with role) stored in app state. Used to:
- Show/hide or grey out buttons based on role
- Only visual enforcement — backend enforces actual permissions

---

## 7. Bus Topics

New ZMQ topic:
- `ALARM.{controller_id}` — AlarmTransition serialized via msgpack

Published by AlarmWorker, consumed by:
- DBWorker (persistence)
- BusBridge in HMI (real-time display)

---

## 8. Testing Strategy

### Unit Tests
- AlarmEngine: trigger/clear all 6 alarm types, hysteresis, deviation suppression during ramp
- RBAC dependencies: role hierarchy validation, 403 on insufficient role
- AlarmRepository: CRUD operations
- AuditRepository: record and query
- AlarmState transitions: ISA-18.2 state machine

### Integration Tests
- AlarmWorker: receives telemetry, produces alarm transitions
- Alarm REST endpoints: CRUD + ACK with role enforcement
- User management: CRUD with admin-only enforcement
- Audit trail: verify actions are logged on API calls
- Full alarm lifecycle: trigger → persist → ACK → clear → verify history

### HMI Tests
- AlarmPanel: table population, ACK button behavior
- AlarmBar: counter updates, blink state
- Permission-based UI: button visibility per role

---

## 9. Files Created/Modified Summary

### New Files
| File | Layer | Purpose |
|------|-------|---------|
| `core/domain/services/alarm_engine.py` | Domain | Alarm detection + hysteresis |
| `core/application/workers/alarm_worker.py` | Application | Bus subscriber, alarm evaluation |
| `core/adapters/outbound/alarm_repo.py` | Outbound | Log_Alarmes persistence |
| `core/adapters/outbound/audit_repo.py` | Outbound | Log_Auditoria persistence |
| `core/adapters/inbound/api/routers/alarms.py` | Inbound | Alarm REST endpoints |
| `core/adapters/inbound/api/routers/users.py` | Inbound | User management CRUD |
| `core/adapters/inbound/api/routers/audit.py` | Inbound | Audit trail endpoint |
| `hmi/pages/alarm_panel.py` | HMI | Alarm management page |
| `domain/models/alarm_config.py` | Domain | AlarmConfig dataclass |

### Modified Files
| File | Change |
|------|--------|
| `domain/enums.py` | Add AlarmState, AuditAction enums |
| `domain/events.py` | Add AlarmTriggered, AlarmCleared, AlarmAcknowledged |
| `core/adapters/outbound/sqlite_repo.py` | Add Log_Alarmes, Log_Auditoria tables to schema init |
| `core/adapters/outbound/user_repo.py` | Add list/get/update/deactivate methods, active/created_at columns |
| `core/adapters/inbound/api/dependencies.py` | Add require_operator(), require_supervisor() |
| `core/adapters/inbound/api/app.py` | Register alarm, user, audit routers |
| `core/adapters/inbound/api/routers/*.py` | Add RBAC dependencies to all existing endpoints |
| `core/main.py` | Wire AlarmWorker lifecycle |
| `hmi/widgets/alarm_bar.py` | Priority counters, blink, dropdown |
| `hmi/main_window.py` | Add Alarms toolbar button, AlarmPanel navigation |
| `hmi/bus_bridge.py` | Subscribe to ALARM.* topic |

---

## 10. Out of Scope

- Granular permission tables (YAGNI for 3 fixed roles)
- Alarm shelving/suppression management
- External notifications (email, SMS, push)
- Row-level security (all users see all controllers)
- Alarm rationalization tooling
