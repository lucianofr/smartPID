# Smart PID Edge Platform — Architecture Design Spec V2

**Date:** 2026-04-02
**Status:** Approved
**Supersedes:** `2026-04-02-smart-pid-architecture-design.md` (V1 monolithic)
**Pattern:** Hexagonal + Event-Driven, Distributed Client-Server
**Python:** 3.13+
**Package Manager:** uv (workspaces)
**Code Language:** English (100%)

---

## 1. Overview

The Smart PID Edge Platform is an industrial system for PID loop optimization using AI (Fuzzy Logic and Reinforcement Learning). It dynamically adjusts the integral parameter (Ki/Ti) for stability and zero steady-state error across different process dynamics.

The system is split into two independent deployables:

- **Backend (Core Engine):** Headless daemon designed for Linux (systemd). Sole owner of OPC-UA communication, PID computation, AI inference, alarm detection, and SQLite database. Exposes data via ZeroMQ (real-time telemetry) and FastAPI REST (commands/history).
- **Frontend (HMI Desktop):** PySide6 desktop application for operators and engineers. Pure network client — no direct access to hardware, database, or internal bus. Consumes data via httpx (REST) and pyzmq (ZeroMQ SUB).

A shared domain package provides the single source of truth for models, events, enums, and DTOs used by both sides.

### Key Decisions

- Architecture: Hexagonal + Event-Driven with distributed client-server topology
- Repository: Monorepo with 3 packages via uv workspaces (domain, core, hmi)
- Existing domain code (PID engine, mode manager, models): kept and migrated
- Dual ZeroMQ bus: `inproc://` internal (Backend threads) + `tcp://` external (Backend -> HMI)
- REST for commands/history, ZeroMQ for real-time telemetry (one-way PUB -> SUB)
- Qt binding: PySide6 (LGPL)
- Target platform: Linux-first (systemd daemon)
- Auth deferred to Phase 6 skeleton, but API contract includes JWT from Phase 2
- Simulation: scipy.signal + python-control for transfer function models

---

## 2. Technology Stack

| Layer | Backend (`smart_pid_core`) | HMI (`smart_pid_hmi`) | Shared (`smart_pid_domain`) |
|---|---|---|---|
| Runtime | Python 3.13+ | Python 3.13+ | Python 3.13+ |
| Core | FastAPI, uvicorn | PySide6, pyqtgraph | pydantic |
| Network | pyzmq (inproc + tcp PUB) | pyzmq (tcp SUB), httpx | — |
| Serialization | msgpack | msgpack | msgpack |
| OPC-UA | asyncua | — | — |
| AI | scikit-fuzzy, stable-baselines3 | — | — |
| Math | numpy, scipy, python-control | numpy (charts only) | — |
| Database | aiosqlite (SQLite WAL) | — | — |
| Auth | bcrypt, PyJWT | — | — |
| Export | openpyxl, reportlab | — | — |
| Config | pydantic-settings | pydantic-settings | — |
| Logging | structlog | structlog | — |
| Testing | pytest, pytest-asyncio, pytest-mock | pytest, pytest-qt, pytest-mock | pytest |
| Tooling | ruff, mypy (strict), uv + hatchling | same | same |

---

## 3. Repository Structure

```
smart-pid/
├── pyproject.toml                          # uv workspace root
├── packages/
│   ├── smart_pid_domain/                   # Shared pure domain
│   │   ├── pyproject.toml
│   │   └── src/smart_pid_domain/
│   │       ├── __init__.py
│   │       ├── models/
│   │       │   ├── __init__.py
│   │       │   ├── controller.py           # Controller, PIDParams, ScaleConfig
│   │       │   ├── telemetry.py            # TelemetryFrame, ControlAction
│   │       │   ├── alarm.py                # AlarmConfig, AlarmEvent, AlarmState
│   │       │   ├── ai.py                   # AIConfig, FuzzyResult, RLAction
│   │       │   ├── user.py                 # User, Role (Admin/Supervisor/Operator)
│   │       │   └── project.py              # Project metadata
│   │       ├── events.py                   # Frozen domain events
│   │       ├── enums.py                    # All shared enums (modes, priorities, etc.)
│   │       ├── dto.py                      # API data transfer objects (request/response)
│   │       └── exceptions.py               # Typed exception hierarchy
│   │
│   ├── smart_pid_core/                     # Backend daemon
│   │   ├── pyproject.toml                  # depends on smart_pid_domain
│   │   └── src/smart_pid_core/
│   │       ├── __init__.py
│   │       ├── main.py                     # Entry point: bootstrap daemon
│   │       ├── config.py                   # pydantic-settings (SPID_ prefix)
│   │       │
│   │       ├── domain/                     # Backend-only domain services
│   │       │   ├── __init__.py
│   │       │   ├── ports/
│   │       │   │   ├── __init__.py
│   │       │   │   ├── inbound.py          # TelemetrySource, TagBrowser
│   │       │   │   └── outbound.py         # ControllerRepo, HistorianWriter, etc.
│   │       │   └── services/
│   │       │       ├── __init__.py
│   │       │       ├── pid_engine.py       # PID velocity form
│   │       │       ├── pid_mode_manager.py # 8-mode state machine
│   │       │       ├── fuzzy_engine.py     # 3 rule matrices, CoG
│   │       │       ├── rl_engine.py        # SAC/PPO interface
│   │       │       ├── alarm_engine.py     # HIHI/HI/LO/LOLO + deadband
│   │       │       └── statistics.py       # IAE, MSE, ITAE, TV, sigma
│   │       │
│   │       ├── application/                # Orchestration
│   │       │   ├── __init__.py
│   │       │   ├── event_bus.py            # ZeroMQ inproc:// XPUB/XSUB proxy
│   │       │   ├── telemetry_publisher.py  # ZeroMQ tcp:// PUB for HMI
│   │       │   ├── workers/
│   │       │   │   ├── __init__.py
│   │       │   │   ├── pid_worker.py       # High priority, scan rate loop
│   │       │   │   ├── ai_worker.py        # Low priority, dead_time * 3
│   │       │   │   ├── io_worker.py        # Async OPC-UA read/write
│   │       │   │   └── db_worker.py        # Batch insert SQLite
│   │       │   ├── loop_manager.py         # Lifecycle per control loop
│   │       │   └── project_manager.py      # .spid file lifecycle
│   │       │
│   │       ├── api/                        # FastAPI REST layer
│   │       │   ├── __init__.py
│   │       │   ├── app.py                  # FastAPI app factory
│   │       │   ├── auth.py                 # JWT middleware, bcrypt
│   │       │   ├── dependencies.py         # Dependency injection
│   │       │   └── routes/
│   │       │       ├── __init__.py
│   │       │       ├── history.py          # GET /history/{tag_id}
│   │       │       ├── commands.py         # POST /command/setpoint, mode, output
│   │       │       ├── config.py           # PUT /config/pid, controllers CRUD
│   │       │       ├── alarms.py           # GET /alarms, PUT /alarms/ack
│   │       │       ├── opcua.py            # GET /opcua/browse
│   │       │       ├── project.py          # POST /project/new, open, save, save-as
│   │       │       └── export.py           # POST /export, GET /export/{id}/download
│   │       │
│   │       └── adapters/                   # Concrete implementations
│   │           ├── __init__.py
│   │           ├── adapter_factory.py      # Centralized DI
│   │           ├── inbound/
│   │           │   ├── __init__.py
│   │           │   ├── opcua_client.py     # asyncua read
│   │           │   └── simulator_adapter.py # Local OPC-UA server + process models
│   │           └── outbound/
│   │               ├── __init__.py
│   │               ├── opcua_writer.py     # asyncua write + watchdog
│   │               ├── sqlite_repo.py      # SQLite WAL
│   │               ├── historian.py        # Batch insert Log_Processo
│   │               └── export_service.py   # CSV, XLSX, PDF
│   │
│   └── smart_pid_hmi/                      # Desktop HMI client
│       ├── pyproject.toml                  # depends on smart_pid_domain
│       └── src/smart_pid_hmi/
│           ├── __init__.py
│           ├── main.py                     # Entry point: QApplication
│           ├── config.py                   # HMI settings (server IP, theme, etc.)
│           │
│           ├── services/                   # Network client layer
│           │   ├── __init__.py
│           │   ├── api_client.py           # httpx async client (REST calls)
│           │   ├── telemetry_sub.py        # ZeroMQ tcp:// SUB (real-time feed)
│           │   └── session.py              # JWT token management, login
│           │
│           ├── bus_bridge.py               # QTimer polls ZMQ SUB -> Qt Signals
│           │
│           ├── themes/
│           │   ├── __init__.py
│           │   ├── base.py                 # ThemeBase(Protocol)
│           │   ├── dark.py
│           │   ├── material.py
│           │   └── isa101.py
│           │
│           ├── main_window.py              # QMainWindow + QStackedWidget
│           ├── pages/
│           │   ├── __init__.py
│           │   ├── connection.py           # Login/Connect to Edge Server
│           │   ├── dashboard_executive.py
│           │   ├── dashboard_operational.py
│           │   ├── multi_trend.py
│           │   ├── alarm_panel.py
│           │   └── settings_panel.py
│           │
│           ├── widgets/
│           │   ├── __init__.py
│           │   ├── controller_card.py
│           │   ├── faceplate.py
│           │   ├── trend_chart.py
│           │   ├── ai_log_box.py
│           │   ├── alarm_bar.py
│           │   ├── opcua_browser.py
│           │   └── controller_config.py
│           │
│           └── resources/
│               └── svg/
│
├── tests/
│   ├── domain/                             # Tests for shared domain
│   ├── core/                               # Tests for backend
│   └── hmi/                                # Tests for HMI
│
└── docs/
```

**Dependency rule:** `smart_pid_domain` depends only on `pydantic` (and stdlib). Both `smart_pid_core` and `smart_pid_hmi` depend on `smart_pid_domain`, but never on each other. Within `smart_pid_core`, arrows point inward: `api/` and `adapters/` -> `application/` -> `domain/` -> `smart_pid_domain`.

---

## 4. Communication Architecture

Two distinct channels matching spec Modules 2.1 and 2.2.

### 4.1 Internal Bus — ZeroMQ `inproc://`

Lives entirely inside the Backend process. XPUB/XSUB proxy for many-to-many routing. Serialization via msgpack.

| Topic | Producer | Consumers | Payload |
|---|---|---|---|
| `TELEMETRY.{id}` | I/O Worker | PID Worker, AI Worker, DB Worker, Telemetry Publisher | `TelemetryFrame` |
| `ACTION.CTRL.{id}` | PID Worker | I/O Worker | `ControlAction(co, integral_val)` |
| `ACTION.AI.{id}` | AI Worker | PID Worker | `AIAction(new_ki, gamma, justification)` |
| `EVENT.ALARM.{id}` | Alarm Engine | DB Worker, Telemetry Publisher | `AlarmEvent` |
| `LOG.AI.{id}` | AI Worker | DB Worker, Telemetry Publisher | `AILogEntry` |
| `SYS.STATE` | Loop Manager | All workers, Telemetry Publisher | `SystemState` |

`ACTION.CTRL` and `ACTION.AI` stay internal — never exposed to the network.

### 4.2 External Bus — ZeroMQ `tcp://` (PUB only)

The Telemetry Publisher bridges selected internal topics to the network. It subscribes to the internal bus and re-publishes to `tcp://0.0.0.0:5555`. The HMI connects as SUB. One-way only — HMI never writes to ZeroMQ.

| Topic | Direction | Payload |
|---|---|---|
| `TELEMETRY.{id}` | Backend -> HMI | `TelemetryFrame` |
| `EVENT.ALARM.{id}` | Backend -> HMI | `AlarmEvent` |
| `ALARM.RECENT` | Backend -> HMI | `list[AlarmEvent]` (last 10) |
| `LOG.AI.{id}` | Backend -> HMI | `AILogEntry` |
| `SYS.STATE` | Backend -> HMI | `SystemState` |

### 4.3 REST Channel — FastAPI (port 8000)

All HMI-to-Backend commands, queries, and configuration flow through HTTP. JWT token required on every request (except login).

| Endpoint | Method | Purpose |
|---|---|---|
| `/auth/login` | POST | Authenticate, receive JWT |
| `/history/{controller_id}` | GET | Query process data (time range) |
| `/command/setpoint` | POST | Write new SP |
| `/command/mode` | POST | Change controller mode |
| `/command/output` | POST | Write CO (manual mode) |
| `/config/controllers` | GET/POST | List/create controllers |
| `/config/controllers/{id}` | GET/PUT/DELETE | Controller CRUD |
| `/config/pid/{id}` | PUT | Update PID tuning params |
| `/config/alarms/{id}` | PUT | Update alarm limits |
| `/alarms` | GET | Query alarm history |
| `/alarms/ack` | PUT | Acknowledge alarm |
| `/opcua/browse` | GET | Browse OPC-UA tag tree |
| `/project/new` | POST | Create new .spid |
| `/project/open` | POST | Open existing .spid |
| `/project/save` | POST | Save current state |
| `/project/save-as` | POST | Clone .spid |
| `/export` | POST | Request export (CSV/XLSX/PDF) |
| `/export/{id}/download` | GET | Download generated file |
| `/system/status` | GET | Backend health check |

### 4.4 HMI Data Flow

```
Backend                                    HMI
┌──────────────────┐                ┌──────────────────┐
│  Internal Bus     │                │                  │
│  (inproc://)      │                │  api_client.py   │──── httpx ────── FastAPI
│       │           │                │  (REST commands)  │      (port 8000)
│       ▼           │                │                  │
│  Telemetry        │   tcp://5555   │  telemetry_sub.py│
│  Publisher   ────────ZMQ PUB/SUB──────▶ (ZMQ SUB)    │
│                   │                │       │          │
│  FastAPI          │                │       ▼          │
│  (port 8000) ◀────── HTTP ────────│  bus_bridge.py   │
│                   │                │  (QTimer 33ms)   │
└──────────────────┘                │       │          │
                                    │       ▼          │
                                    │  Qt Signals      │
                                    │  → Widgets       │
                                    └──────────────────┘
```

---

## 5. Threading Model

### 5.1 Backend Threads

| Thread | Priority | Responsibility | Rate | Lifecycle |
|---|---|---|---|---|
| **Main** | Normal | asyncio event loop: FastAPI (uvicorn), ZeroMQ proxy, Telemetry Publisher | — | Process lifetime |
| **I/O Worker** | Normal | OPC-UA async read/write, watchdog heartbeat, connection state machine | Controller scan rate | Per controller |
| **PID Worker** | High | PID equation, alarm detection, publishes ACTION.CTRL | Controller scan rate | Per controller |
| **AI Worker** | Low | Fuzzy/RL inference, publishes ACTION.AI + LOG.AI | dead_time_L * 3 | Per controller |
| **DB Worker** | Low | SQLite batch insert (TELEMETRY, ALARM, AI LOG), retention cleanup | Flush every 5-10s | Shared singleton |

FastAPI and the ZeroMQ proxy run on the main asyncio event loop. DB Worker is its own thread because SQLite writes are blocking.

### 5.2 HMI Threads

| Thread | Purpose | Rate |
|---|---|---|
| **Main (Qt)** | PySide6 event loop, widget rendering, user interaction | — |
| **Telemetry Receiver** | ZeroMQ SUB socket, pushes frames into thread-safe queue | Continuous |
| **BusBridge** | QTimer on main thread, drains queue -> emits Qt Signals | 33ms (~30 FPS) |

### 5.3 Resilience Rules

| Failure | Behavior |
|---|---|
| AI Worker crash | PID Worker continues with last valid Ki. SYS.STATE updated. |
| I/O Worker connection loss | State -> RECONNECTING, exponential backoff. Bumpless transfer on reconnect. PID Worker pauses output. |
| DB Worker delay | Data buffered in RAM deque, no impact on control loop. |
| HMI disconnect | Zero impact on Backend. Control continues. HMI reconnects and resumes. |
| FastAPI unresponsive | HMI commands fail with timeout. Telemetry stream (ZeroMQ) unaffected. |
| Backend process crash | PLC detects via watchdog heartbeat timeout. HMI shows connection lost. |

### 5.4 Scan Rate Determinism

PID Worker uses `time.monotonic()` for timing. Configurable scan rates per controller: 100ms, 500ms, 1s, 2s, 5s, 10s, 30s, 60s.

---

## 6. Domain Models (smart_pid_domain)

### 6.1 Core Models

- **`Controller`**: Full configuration of a control loop (PID params, scales, mode, AI config, tag bindings, alarm config)
- **`PIDParams`**: gain, reset (Ti), rate (Td), alpha (derivative filter), deadband
- **`ScaleConfig`**: eu_min, eu_max, unit
- **`TelemetryFrame`**: Frozen dataclass with pv, sp, co, integral_val, timestamp, status
- **`ControlAction`**: co, integral_val
- **`AIConfig`**: engine (NONE/FUZZY/RL), objective, process_speed, dead_time_l, limits
- **`AlarmConfig`**: HIHI/HI/LO/LOLO values and priorities, deadband_percent
- **`AlarmEvent`**: controller_id, type, priority, timestamp, value
- **`User`**: username, password_hash, role (Admin/Supervisor/Operator)
- **`Project`**: metadata for .spid file

### 6.2 Domain Events (frozen dataclasses)

- `TelemetryReceived`, `ControlActionComputed`, `AIActionApplied`
- `AlarmTriggered`, `AlarmCleared`, `AlarmAcknowledged`
- `SystemStateChanged`

### 6.3 Enums

- `ControllerMode`: OOS, IMan, LO, Man, Auto, Cas, RCas, ROut
- `ExecutionMode`: SUPERVISORY, DDC
- `PIDStructure`: ISA, PARALLEL, SERIES
- `IntegralType`: GAIN_KI, TIME_TI
- `AIEngine`: NONE, FUZZY, RL
- `ControlObjective`: SP_TRACKING, DISTURBANCE_REJECTION, SURGE_LEVEL
- `ProcessSpeed`: SLOW, MEDIUM, FAST
- `AlarmPriority`: CRITICAL, WARNING, ADVISORY, LOG
- `AlarmType`: HIHI, HI, LO, LOLO, DV_HI, DV_LO
- `ConnectionState`: OFFLINE, ONLINE, RECONNECTING
- `OptimizerState`: RUN, PAUSE, STOP
- `UserRole`: ADMIN, SUPERVISOR, OPERATOR

### 6.4 DTOs (API Data Transfer Objects)

Request/response models for the REST API. Defined in `smart_pid_domain` so both Backend (serialization) and HMI (deserialization) share the same contract.

### 6.5 Exception Hierarchy

```
SmartPIDError
├── DomainError
│   ├── PIDComputationError
│   ├── AIInferenceError
│   ├── AlarmConfigError
│   └── InvalidModeTransition
├── InfrastructureError
│   ├── OPCUAConnectionError
│   ├── OPCUAReadError
│   ├── OPCUAWriteError
│   ├── DatabaseError
│   └── ExportError
├── CommunicationError
│   ├── APIConnectionError
│   ├── APIAuthError
│   ├── APITimeoutError
│   └── TelemetryStreamError
├── ProjectError
│   ├── ProjectNotFoundError
│   └── ProjectCorruptedError
├── AuthenticationError
└── AuthorizationError
```

---

## 7. Domain Services (smart_pid_core)

### 7.1 PID Engine

As specified in `bloco_pid.md`:

- Velocity form equation (derivative on PV) to avoid derivative kick:
  `delta_cv = Gain * [(e_n - e_{n-1}) + (dt/Reset) * e_n - Rate * (PV_n - 2*PV_{n-1} + PV_{n-2}) / dt]`
  `CV_new = CV_current + delta_cv`
- `PIDState` passed and returned explicitly — no hidden state
- Anti-windup: pauses integral accumulation when CO hits ARW_HI_LIM / ARW_LO_LIM, with 16x faster reset recovery
- Bumpless transfer: recalculates integral term on mode transitions
- SP ramp: SP_RATE_UP / SP_RATE_DN applied to produce SP_WRK
- Derivative filter: configurable ALPHA (default 0.125, range 0.05-1.0)
- PV filter: first-order filter with PV_FTIME
- Feedforward: FF_VAL * FF_GAIN added to output when FF_ENABLE is true
- Integral deadband (IDEADBAND): integral action pauses when error enters deadband
- Direct/Reverse acting via CONTROL_OPTS
- Increase-to-Close output inversion via IO_OPTS
- Output limits: OUT_HI_LIM / OUT_LO_LIM with 10% over-range allowance
- Low cutoff: PV forced to 0.0 when below LOW_CUT (for flow meters)

### 7.2 PID Mode Manager

8-mode state machine:
- OOS, IMan, LO, Man, Auto, Cas, RCas, ROut
- Validates transitions against permitted modes
- Forced transitions: Bad PV -> Man, TRK_IN_D -> LO, shed timeout -> configured mode
- CONTROL_OPTS: Track Enable, Track in Manual, Direct Acting, SP-PV Track in Man/LO/ROut, Bypass Enable, No OUT Limits in Manual, Obey SP Limits if Cas/RCas
- IO_OPTS: Low Cutoff, Fault State behavior, Increase to Close, Target to Man if Fault
- SP tracking behavior per mode (SP follows PV when configured)

### 7.3 Fuzzy Engine

- Input normalization: error and delta_error to -100%..+100% of span
- 7 linguistic levels: NB, NM, NS, ZO, PS, PM, PB
- Membership functions: triangular (center) + trapezoidal (extremes), 50% overlap
- 3 rule matrices loaded by objective: SP Tracking, Disturbance Rejection, Surge Level (as defined in spec Module 4.2)
- Defuzzification: Center of Gravity (CoG) -> gamma in [-1.0, +1.0]
- Ki update: `Ki_new = Ki_current * (1 + gamma * Sv)`, clamped to ai_limit_min/max
- Speed factor Sv: SLOW=0.30, MEDIUM=0.15, FAST=0.05
- Cycle time: `T_cycle = dead_time_L * 3`

### 7.4 RL Engine

- SAC/PPO agent via stable-baselines3 (lazy import to avoid loading when unused)
- Online learning: continuous training during operation
- Observation: error, delta_error, CO, integral_val (normalized)
- Action: gamma [-1.0, +1.0] — same interface as Fuzzy output
- Reward functions per objective:
  - SP Tracking / Disturbance Rejection: minimize IAE/ITAE, penalize TV (valve chattering)
  - Surge Level: reward valve stability, only penalize IAE outside deadband
- Same guardrails (Ki limits) and cadence (T_cycle) as Fuzzy

### 7.5 Alarm Engine

- Process alarms: HIHI, HI, LO, LOLO compared against PV
- Deviation alarms: DV_HI, DV_LO compared against (PV - SP), suppressed during SP changes
- Hysteresis: ALARM_HYS (up to 50% of scale) — alarm clears only after PV returns within limit minus hysteresis
- Priorities: CRITICAL, WARNING, ADVISORY, LOG

### 7.6 Statistics Calculator

- Sliding window via `collections.deque` (configurable, e.g. 30 min)
- Metrics: IAE, MSE, ISE, ITAE, standard deviation
- Variability: SP-based (`2*sigma/SP`) and range-based (`2*sigma/Span`)
- Total Variation (CO chattering)
- Computed in Backend, only results sent to HMI

---

## 8. Application Layer (smart_pid_core)

### 8.1 Event Bus (Internal)

ZeroMQ XPUB/XSUB proxy running on the main asyncio event loop as a background task. `BusPublisher` and `BusSubscriber` classes encapsulate `inproc://` socket creation and msgpack serialization. Workers receive instances at creation.

### 8.2 Telemetry Publisher (Internal -> External Bridge)

Subscribes to internal bus topics (`TELEMETRY.*`, `EVENT.ALARM.*`, `LOG.AI.*`, `ALARM.RECENT`, `SYS.STATE`). Re-publishes to `tcp://0.0.0.0:5555` via a PUB socket. Runs as an asyncio task on the main loop. Only component that bridges internal and external buses.

### 8.3 Workers

- **PIDWorker**: One per controller. High-priority daemon thread. Scan rate loop via `time.monotonic()`. Subscribes to `TELEMETRY.{id}` and `ACTION.AI.{id}`, publishes `ACTION.CTRL.{id}`. Runs AlarmEngine on each scan.
- **AIWorker**: One per controller. Low-priority daemon thread. Cadence = dead_time_L * 3. Accumulates telemetry in deque. Runs Fuzzy or RL inference. Publishes `ACTION.AI.{id}` + `LOG.AI.{id}`. State: RUN/PAUSE/STOP independent from PID mode.
- **IOWorker**: One per controller. Runs own asyncio event loop. OPC-UA read/write cycle. Connection state machine (OFFLINE/ONLINE/RECONNECTING) with exponential backoff. Watchdog heartbeat (WD_HEART_BEAT / WD_HEART_BEAT_NOT toggle).
- **DBWorker**: Shared singleton. Subscribes to `TELEMETRY.*`, `EVENT.ALARM.*`, `LOG.AI.*`. Batch insert via `executemany()` every flush_interval (5-10s). Periodic cleanup: 7 days process data, 30 days alarms.

### 8.4 Loop Manager

Manages lifecycle of all controller loops. `start_loop(controller_id)` instantiates domain services, creates adapters via AdapterFactory, spawns workers. `stop_loop(controller_id)` signals workers, flushes DB, publishes SYS.STATE. Maintains `LoopContext` per controller.

### 8.5 Project Manager

Handles `.spid` file lifecycle (all local to Backend):
- **New**: Create SQLite file with full DDL schema
- **Open**: Stop running loops, switch DB connection, load controllers, restart loops
- **Save**: Flush pending state to current `.spid`
- **Save As**: Clone file. Option "Template Only" strips Log_Processo and Log_Alarmes

### 8.6 FastAPI REST Layer

`app.py` creates the FastAPI instance and mounts all routers. `dependencies.py` provides DI — routes receive LoopManager, ProjectManager, and repository instances via `Depends()`. `auth.py` provides JWT middleware (decode token, extract role, enforce RBAC).

---

## 9. Adapters (smart_pid_core)

### 9.1 Inbound

- **OPCUAClient**: asyncua-based. Implements `TelemetrySource` + `TagBrowser`. Batch read for efficiency. Tag NodeIDs from Controller config.
- **SimulatorAdapter**: Implements `TelemetrySource`. 4 presets (Flow/Level/Pressure/Temperature via `scipy.signal`) + Custom SOPTD (`python-control`). Dead time via Pade approximation. Embedded `asyncua.Server` on localhost. Noise and load step disturbance injection.

### 9.2 Outbound

- **OPCUAWriter**: Implements `ControlWriter`. Shares asyncua.Client with OPCUAClient. Watchdog heartbeat toggle. Increase-to-Close inversion.
- **SQLiteRepository**: Implements `ControllerRepository`. aiosqlite with WAL mode. Full DDL from spec Module 6.
- **SQLiteHistorian**: Implements `HistorianWriter`. `executemany()` batch inserts. Retention cleanup (7 days process, 30 days alarms).
- **ExportService**: Implements `ExportWriter`. CSV, XLSX (openpyxl), PDF (reportlab). Runs in thread pool.

### 9.3 AdapterFactory

Centralized DI. Creates concrete adapters based on config. Only place that knows concrete classes. LoopManager asks for "a TelemetrySource" and gets OPCUAClient or SimulatorAdapter.

---

## 10. HMI Architecture (smart_pid_hmi)

### 10.1 Network Services Layer

- **`api_client.py`**: Async `httpx.AsyncClient` wrapper. JWT token injection, retry on 401, timeout handling. Methods map to API endpoints.
- **`telemetry_sub.py`**: ZeroMQ SUB socket connecting to `tcp://{server_ip}:5555`. Subscribes to topics based on visible controllers. Pushes frames into `queue.SimpleQueue`.
- **`session.py`**: Login flow, JWT token storage, exposes current user role for UI permission checks.

### 10.2 Bus Bridge (ZMQ -> Qt)

```
telemetry_sub.py (background thread)
    -> SimpleQueue
        -> BusBridge (QTimer 33ms on main thread)
            -> drains queue
                -> emits Qt Signals per topic
```

Widgets connect to typed Qt Signals. Widgets never touch the network layer directly.

### 10.3 Connection Screen

First screen on launch. User provides server IP, ports (REST + ZeroMQ), username, password. On success: session stores JWT, telemetry_sub connects, app navigates to Dashboard Operational.

### 10.4 Theme System

`ThemeBase(Protocol)` defines: colors, chart palette, fonts, sizes. Each theme implements `apply(app: QApplication)` via QSS stylesheet. Hot-switch without restart.

Three themes (detailed visual identity specs in dedicated documents):
- **Dark Mode**: Dark room style for mission-critical control rooms. Absolute black background, zero unnecessary light emission, monochromatic in normal state, color reserved exclusively for alarms. See [identidade_visual_Dark.md](../../identidade_visual_Dark.md).
- **Material Design 3**: Google MD3 neutral tones, surface container elevation hierarchy, Roboto typography. Dynamic Color system disabled — only neutral tones in normal state, M3 Error Tokens for alarms. See [identidade_visual_MD3.md](../../identidade_visual_MD3.md).
- **ISA-101**: ANSI/ISA-101.01 High Performance HMI. Gray tones, 100% flat design, no 3D elements. Colors reserved exclusively for abnormal conditions/alarms. See [identidade_visual_ISA101.md](../../identidade_visual_ISA101.md).

Each visual identity document defines the complete design system: color palette, typography, semantic alarm colors, and detailed widget specifications (AnalogBarWidget, ControllerCardWidget, FaceplateWidget, TrendChartWidget, AlarmFooterWidget). These documents are the authoritative source for theme implementation in Phase 7.

### 10.5 Pages

| Page | Description |
|---|---|
| **Connection** | Login + connect to Edge Server |
| **Dashboard Executive** | Global KPIs, Bad Actors (top 5 IAE), AI ROI, system health. REST polling. |
| **Dashboard Operational** | Grid of ControllerCards (top). TrendChart 70% + Faceplate 30% (bottom). AILogBox. AlarmBar footer. |
| **Multi-Trend** | 2x2 grid, Time-Sync (zoom/pan synchronized). |
| **Alarm Panel** | Table + filters (priority, type, time range). ACK via REST. |
| **Settings** | OPC-UA config (remote via REST), project management (via REST), theme selector. |

### 10.6 Key Widgets

- **TrendChart**: pyqtgraph PlotWidget. Y1 (PV/SP), Y2 (CO). Time window selector (value + unit dropdown). Auto-scale. Manual scale fields. AI action markers. CSV export. Downsampling.
- **Faceplate**: Bar graphs (PV/SP/CO), numeric inputs, stats (2sigma/Range, IAE), mode indicator, optimizer controls (RUN/PAUSE/STOP), config gear icon.
- **ControllerCard**: Name, mode badge, sparkline, PV/SP/CO, AI status. Border color = alarm state.
- **AILogBox**: Terminal-style, timestamps, color-coded (Fuzzy orange, RL cyan).
- **AlarmBar**: Fixed bottom, 10 most recent alarms across all controllers.
- **OPCUABrowser**: Modal, tree from `GET /opcua/browse`, search bar, double-click selects NodeID.
- **ControllerConfig**: Dialog for tag binding, PID params, AI config, alarm limits, scales. Changes via REST.

### 10.7 Permission-Based UI

- **Operator**: Monitoring, ACK alarms, SP, Man/Auto mode. Config grayed out.
- **Supervisor**: + PID tuning, AI config, alarm limits, optimizer RUN/PAUSE/STOP.
- **Admin**: Full access including user management, OPC-UA config, project management.

---

## 11. Database Schema

SQLite with WAL mode. File extension: `.spid`. Resides exclusively on Backend machine.

```sql
-- RBAC
CREATE TABLE Usuarios (
    id INTEGER PRIMARY KEY, username TEXT UNIQUE,
    password_hash TEXT, role TEXT CHECK(role IN ('ADMIN','SUPERVISOR','OPERATOR'))
);

-- Controller config (source of truth)
CREATE TABLE Controladores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT UNIQUE NOT NULL, descricao TEXT,
    modo_execucao TEXT CHECK(modo_execucao IN ('SUPERVISORY', 'DDC')),
    scan_rate_ms INTEGER DEFAULT 1000,
    node_id_pv TEXT, node_id_sp TEXT, node_id_co TEXT, node_id_integral TEXT,
    is_scaled BOOLEAN DEFAULT 0, pv_min REAL, pv_max REAL, co_min REAL, co_max REAL,
    pid_structure TEXT CHECK(pid_structure IN ('ISA', 'PARALLEL', 'SERIES')),
    integral_type TEXT CHECK(integral_type IN ('GAIN_KI', 'TIME_TI')),
    kp_manual REAL, kd_manual REAL, ki_inicial REAL,
    ai_engine TEXT DEFAULT 'NONE' CHECK(ai_engine IN ('NONE', 'FUZZY', 'RL')),
    ai_thread_status TEXT DEFAULT 'STOPPED',
    objetivo_controle TEXT DEFAULT 'DISTURBANCE_REJECTION',
    process_speed TEXT CHECK(process_speed IN ('SLOW', 'MEDIUM', 'FAST')),
    tempo_morto_l REAL, ai_limit_min REAL, ai_limit_max REAL
);

-- Alarm limits per controller
CREATE TABLE Configuracao_Alarmes (
    controlador_id INTEGER, deadband_percent REAL,
    hihi_val REAL, hihi_prioridade TEXT, hi_val REAL, hi_prioridade TEXT,
    lo_val REAL, lo_prioridade TEXT, lolo_val REAL, lolo_prioridade TEXT,
    FOREIGN KEY(controlador_id) REFERENCES Controladores(id) ON DELETE CASCADE
);

-- Process historian (indexed)
CREATE TABLE Log_Processo (
    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    controlador_id INTEGER, pv REAL, sp REAL, co REAL, integral_val REAL,
    FOREIGN KEY(controlador_id) REFERENCES Controladores(id)
);
CREATE INDEX idx_log_processo_time ON Log_Processo(timestamp, controlador_id);

-- AI tuning log
CREATE TABLE Log_Sintonia_IA (
    id INTEGER PRIMARY KEY, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    controlador_id INTEGER, valor_anterior REAL, valor_novo REAL, justificativa TEXT
);

-- Audit trail
CREATE TABLE Log_Auditoria (
    id INTEGER PRIMARY KEY, timestamp DATETIME,
    usuario_id INTEGER, acao TEXT, valor_antigo TEXT, valor_novo TEXT
);

-- Alarm history
CREATE TABLE Log_Alarmes (
    id INTEGER PRIMARY KEY, controlador_id INTEGER,
    tipo TEXT, prioridade TEXT,
    timestamp_in DATETIME, timestamp_out DATETIME,
    timestamp_ack DATETIME, usuario_ack_id INTEGER
);
```

### Retention Policy

| Table | Retention | Cleanup |
|---|---|---|
| `Log_Processo` | 7 days | Daily DELETE |
| `Log_Alarmes` | 30 days | Daily DELETE |
| `Log_Sintonia_IA` | 30 days | Daily DELETE |
| `Log_Auditoria` | No auto-delete | Manual |

---

## 12. Configuration

### 12.1 Backend Settings (pydantic-settings, SPID_ prefix)

| Setting | Env Var | Default |
|---|---|---|
| `opcua_endpoint` | `SPID_OPCUA_ENDPOINT` | `opc.tcp://localhost:4840` |
| `opcua_timeout_s` | `SPID_OPCUA_TIMEOUT` | `5` |
| `zmq_internal_url` | `SPID_ZMQ_INTERNAL` | `inproc://bus` |
| `zmq_publish_port` | `SPID_ZMQ_PUB_PORT` | `5555` |
| `api_port` | `SPID_API_PORT` | `8000` |
| `api_host` | `SPID_API_HOST` | `0.0.0.0` |
| `jwt_secret` | `SPID_JWT_SECRET` | (required) |
| `jwt_expiry_hours` | `SPID_JWT_EXPIRY` | `8` |
| `db_path` | `SPID_DB_PATH` | `./project.spid` |
| `db_flush_interval_s` | `SPID_DB_FLUSH` | `5` |
| `db_retention_days` | `SPID_DB_RETENTION` | `7` |
| `simulator_enabled` | `SPID_SIMULATOR` | `false` |
| `simulator_port` | `SPID_SIM_PORT` | `4841` |
| `log_level` | `SPID_LOG_LEVEL` | `INFO` |

### 12.2 HMI Settings (pydantic-settings, SPID_HMI_ prefix)

| Setting | Env Var | Default |
|---|---|---|
| `server_host` | `SPID_HMI_HOST` | `localhost` |
| `server_api_port` | `SPID_HMI_API_PORT` | `8000` |
| `server_zmq_port` | `SPID_HMI_ZMQ_PORT` | `5555` |
| `theme` | `SPID_HMI_THEME` | `dark` |
| `chart_fps` | `SPID_HMI_CHART_FPS` | `30` |
| `chart_max_points` | `SPID_HMI_MAX_POINTS` | `10000` |
| `log_level` | `SPID_HMI_LOG_LEVEL` | `INFO` |

---

## 13. Implementation Phases

### Phase 1: Foundation + Domain + PID Core

Restructure to monorepo with 3 packages. Migrate existing domain code to `smart_pid_domain`. Build core Backend infrastructure.

- Scaffold uv workspace with 3 packages (domain, core, hmi stubs)
- Migrate existing models, events, enums, exceptions to `smart_pid_domain`
- Migrate PID engine + mode manager to `smart_pid_core/domain/services/`
- Migrate ports to `smart_pid_core/domain/ports/`
- Implement internal event bus (ZeroMQ `inproc://` XPUB/XSUB proxy)
- Implement PID Worker (scan rate thread)
- Implement DB Worker (batch insert)
- Implement SQLite repository (full DDL, WAL mode)
- Implement SQLite historian (batch inserts, retention)
- Backend config.py and main.py entry point

**Tests:** Unit: PID equation, anti-windup, bumpless, mode transitions. Integration: event bus, SQLite repo, DB Worker, PID Worker with fake telemetry.

**Deliverable:** Backend daemon starts, PID executes, writes to SQLite.

### Phase 2: REST API + HMI Shell

Build the two communication channels and minimal HMI.

- FastAPI app factory, routes, DI, auth module (JWT + bcrypt)
- REST routes: `/auth/login`, `/config/controllers`, `/history/{id}`, `/system/status`
- Telemetry Publisher (internal -> tcp:// PUB)
- HMI: api_client, session, telemetry_sub, bus_bridge
- HMI: Connection screen, main window shell, navigation
- Dark theme

**Tests:** Integration: REST endpoints, JWT, telemetry round-trip. HMI: pytest-qt.

**Deliverable:** HMI connects, authenticates, receives live telemetry.

### Phase 3: Operational Dashboard + OPC-UA

Main working screen + real hardware connectivity.

- OPC-UA client + writer, I/O Worker, connection state machine
- REST routes: commands, opcua/browse
- Dashboard Operational (cards, trend, faceplate)
- TrendChart, Faceplate, ControllerCard, ControllerConfig, OPCUABrowser, AlarmBar widgets

**Tests:** Integration: OPC-UA mock, I/O Worker reconnect. HMI: dashboard renders.

**Deliverable:** Full operational dashboard with live OPC-UA data.

### Phase 4: Simulator

Digital twin for offline validation.

- 4 preset models + Custom SOPTD, embedded asyncua.Server
- SimulatorAdapter, disturbance injection
- Simulator UI panel, SVG overlay, "Export Dynamics to Loop"

**Tests:** Unit: transfer functions. Integration: simulator full loop.

**Deliverable:** App runs offline with simulated process.

### Phase 5: AI (Fuzzy + RL) + Statistics

Intelligence layer.

- Fuzzy engine (3 matrices), RL engine (SAC), AI Worker
- Statistics calculator, AI log, optimizer controls
- REST routes for AI config, trend markers, stats display

**Tests:** Unit: fuzzy inference, rewards, statistics. Integration: AI Worker cycle.

**Deliverable:** Fuzzy AI optimizing Ki, reasoning log visible.

### Phase 6: Alarms + RBAC Enforcement

Safety and access control.

- Alarm engine, alarm events/persistence, alarm panel + ACK
- RBAC enforcement in API, permission-based UI, audit trail
- User management

**Tests:** Unit: alarm detection, permissions. Integration: alarm lifecycle, audit.

**Deliverable:** Alarms functional, login enforced, role-based UI.

### Phase 7: Executive Dashboard + Multi-Trend + Export + Themes

Polish and completeness.

- Dashboard Executive, Multi-Trend (2x2, Time-Sync)
- Export (CSV/XLSX/PDF via REST)
- Material Design 3 + ISA-101 themes, theme selector
- Settings panel

**Tests:** Integration: export valid files. HMI: themes, multi-trend sync.

**Deliverable:** Complete application.

### Phase Dependency Graph

```
Phase 1 (Foundation + Domain + PID)
   └──> Phase 2 (REST API + HMI Shell)
           └──> Phase 3 (Operational Dashboard + OPC-UA)
                   ├──> Phase 4 (Simulator)          [parallel]
                   ├──> Phase 5 (AI + Stats)          [parallel]
                   └──> Phase 6 (Alarms + RBAC)       [parallel]
                           └──> Phase 7 (Executive + Export + Themes)
```

Phases 4, 5, and 6 can run in parallel after Phase 3.

---

## 14. References

- [docs/smartPIDv2.md](../../smartPIDv2.md) — Spec V2 (distributed architecture, 12 modules)
- [docs/bloco_pid.md](../../bloco_pid.md) — PID block function specification
- [docs/smartPID.md](../../smartPID.md) — Original spec V2.4 (superseded)
- [2026-04-02-smart-pid-architecture-design.md](./2026-04-02-smart-pid-architecture-design.md) — V1 architecture (superseded)
- [docs/identidade_visual_Dark.md](../../identidade_visual_Dark.md) — Visual identity: Dark Room theme (mission-critical control rooms)
- [docs/identidade_visual_ISA101.md](../../identidade_visual_ISA101.md) — Visual identity: ISA-101 High Performance HMI theme
- [docs/identidade_visual_MD3.md](../../identidade_visual_MD3.md) — Visual identity: Material Design 3 theme (neutral tones)
