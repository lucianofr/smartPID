# Smart PID Edge Optimizer — Architecture Design Spec

**Date:** 2026-04-02
**Status:** Approved
**Pattern:** Hexagonal + Event-Driven
**Python:** 3.13+
**Package Manager:** uv
**Code Language:** English (100%)

---

## 1. Overview

The Smart PID Edge Optimizer is an industrial desktop application for PID loop optimization using AI (Fuzzy Logic and Reinforcement Learning). It dynamically adjusts the integral parameter (Ki/Ti) for stability and zero steady-state error across different process dynamics.

The application functions as both an Edge Optimizer coupled to existing PLCs (via OPC-UA) and as a Historian/Analytical Performance Tool.

**Key decisions from brainstorming:**

- Architecture: Hexagonal + Event-Driven (domain at center, ZeroMQ event bus, ports/adapters at edges)
- Full system implementation across 6 incremental phases (Modules 1-12 from spec)
- Tests after implementation, rigorous on critical modules (PID, Fuzzy/RL, alarms, bus)
- Simulation libraries: scipy.signal + python-control for transfer function models (presets and Custom SOPTD). GEKKO/TCLab evaluated but deferred — scipy covers all spec requirements without extra complexity. Can be added later as additional preset models if needed.

---

## 2. Technology Stack

| Layer | Technology |
|---|---|
| Language | Python 3.13+ |
| UI Framework | PySide6 (Qt for Python) |
| Real-time Charts | pyqtgraph |
| OPC-UA | asyncua |
| Message Bus | pyzmq (ZeroMQ inproc://) |
| Serialization | msgpack |
| Fuzzy Logic | scikit-fuzzy |
| Reinforcement Learning | stable-baselines3 (SAC/PPO) |
| Math/Signal | numpy, scipy, python-control |
| Database | aiosqlite (SQLite WAL mode) |
| Config | pydantic-settings |
| Logging | structlog |
| Auth | bcrypt |
| Export | openpyxl (XLSX), reportlab (PDF) |
| Testing | pytest, pytest-asyncio, pytest-qt, pytest-mock |
| Linting/Types | ruff, mypy (strict) |
| Packaging | uv + hatchling |

---

## 3. Directory Structure

```
smart-pid/
├── src/
│   └── smart_pid/
│       ├── __init__.py
│       ├── main.py                        # Entry point - bootstrap and lifecycle
│       ├── config.py                      # pydantic-settings (Settings)
│       ├── exceptions.py                  # Typed exception hierarchy
│       │
│       ├── domain/                        # PURE CORE - zero external dependencies
│       │   ├── __init__.py
│       │   ├── models/
│       │   │   ├── __init__.py
│       │   │   ├── controller.py          # Controller, PIDParams, ScaleConfig
│       │   │   ├── alarm.py               # AlarmConfig, AlarmEvent, AlarmState
│       │   │   ├── telemetry.py           # TelemetryFrame (PV, SP, CO, integral)
│       │   │   ├── ai.py                  # AIConfig, FuzzyResult, RLAction
│       │   │   ├── project.py             # Project metadata (.spid)
│       │   │   └── user.py                # User, Role (Admin/Supervisor/Operator)
│       │   │
│       │   ├── events.py                  # Frozen dataclasses: TelemetryReceived,
│       │   │                              #   AlarmTriggered, AIActionApplied, etc.
│       │   │
│       │   ├── ports/
│       │   │   ├── __init__.py
│       │   │   ├── inbound.py             # TelemetrySource, TagBrowser
│       │   │   └── outbound.py            # ControllerRepo, HistorianWriter,
│       │   │                              #   ControlWriter, AlarmNotifier, ExportWriter
│       │   │
│       │   └── services/
│       │       ├── __init__.py
│       │       ├── pid_engine.py          # PID velocity form, anti-windup, bumpless
│       │       ├── pid_mode_manager.py    # Mode state machine (8 modes)
│       │       ├── fuzzy_engine.py        # 3 rule matrices, CoG defuzzification
│       │       ├── rl_engine.py           # RL interface + reward functions
│       │       ├── alarm_engine.py        # HIHI/HI/LO/LOLO + deadband
│       │       └── statistics.py          # IAE, MSE, ITAE, TV, sigma
│       │
│       ├── application/                   # ORCHESTRATION - coordinates domain + events
│       │   ├── __init__.py
│       │   ├── event_bus.py               # ZeroMQ PUB/SUB wrapper (inproc://)
│       │   ├── workers/
│       │   │   ├── __init__.py
│       │   │   ├── pid_worker.py          # High priority thread - scan rate loop
│       │   │   ├── ai_worker.py           # Low priority thread - dead_time * 3 cycle
│       │   │   ├── io_worker.py           # Async OPC-UA read/write thread
│       │   │   └── db_worker.py           # Batch insert SQLite thread
│       │   │
│       │   ├── loop_manager.py            # Lifecycle: start/stop/pause per-loop
│       │   └── project_manager.py         # New/Open/Save/SaveAs (.spid)
│       │
│       ├── adapters/                      # BOUNDARY - concrete implementations
│       │   ├── __init__.py                # AdapterFactory
│       │   ├── inbound/
│       │   │   ├── __init__.py
│       │   │   ├── opcua_client.py        # asyncua read (implements TelemetrySource, TagBrowser)
│       │   │   └── simulator_adapter.py   # Local OPC-UA server + process models
│       │   │
│       │   └── outbound/
│       │       ├── __init__.py
│       │       ├── opcua_writer.py        # asyncua write (implements ControlWriter)
│       │       ├── sqlite_repo.py         # SQLite WAL (implements ControllerRepository)
│       │       ├── historian.py           # Batch insert Log_Processo (implements HistorianWriter)
│       │       └── export_service.py      # CSV, XLSX, PDF generation (implements ExportWriter)
│       │
│       └── ui/                            # PRESENTATION - PySide6 + pyqtgraph
│           ├── __init__.py
│           ├── app.py                     # QApplication bootstrap, theme loader
│           ├── bus_bridge.py              # QTimer polls ZMQ bus -> emits Qt Signals
│           ├── themes/
│           │   ├── __init__.py
│           │   ├── base.py                # ThemeBase(Protocol)
│           │   ├── dark.py                # Dark Mode theme
│           │   ├── material.py            # Material Design 3 theme
│           │   └── isa101.py              # ISA-101 industrial theme
│           │
│           ├── main_window.py             # QMainWindow + QStackedWidget navigation
│           ├── pages/
│           │   ├── __init__.py
│           │   ├── dashboard_executive.py # KPIs, Bad Actors, AI ROI
│           │   ├── dashboard_operational.py # Grid Cards + Trend + Faceplate
│           │   ├── multi_trend.py         # 2x2 grid, Time-Sync
│           │   ├── alarm_panel.py         # Alarm table + filters
│           │   └── settings_panel.py      # OPC-UA config, project management
│           │
│           ├── widgets/
│           │   ├── __init__.py
│           │   ├── controller_card.py     # Summary card with analog bars + gear button
│           │   ├── faceplate.py           # Bar graphs, SP/PV/CO inputs
│           │   ├── trend_chart.py         # pyqtgraph high-res trend
│           │   ├── ai_log_box.py          # Terminal-style AI reasoning
│           │   ├── alarm_bar.py           # Bottom 10 recent alarms
│           │   ├── opcua_browser.py       # Tree View tag navigator
│           │   └── controller_config.py   # Controller settings dialog
│           │
│           └── resources/
│               └── svg/                   # Simulator SVG assets
│
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_pid_engine.py
│   │   ├── test_fuzzy_engine.py
│   │   ├── test_alarm_engine.py
│   │   └── test_statistics.py
│   └── integration/
│       ├── test_event_bus.py
│       ├── test_sqlite_repo.py
│       └── test_workers.py
│
├── docs/
│   ├── smartPID.md                        # Original spec V2.4
│   └── bloco_pid.md                       # PID block function spec
│
├── .env.example
├── pyproject.toml
└── .gitignore
```

**Dependency rule:** Arrows always point inward. `ui/` and `adapters/` import `application/`, which imports `domain/`. The `domain/` package imports only Python stdlib.

---

## 4. Event Bus and Threading Model

### 4.1 ZeroMQ Bus (inproc://)

Single `zmq.Context` shared across all threads. Uses XPUB/XSUB proxy for many-to-many routing. Serialization via msgpack.

**Topics:**

| Topic | Producer | Consumers | Payload |
|---|---|---|---|
| `TELEMETRY.{id}` | I/O Worker | UI, DB Worker, PID Worker | `TelemetryFrame` |
| `ACTION.CTRL.{id}` | PID Worker | I/O Worker | `ControlAction(co, integral_val)` |
| `ACTION.AI.{id}` | AI Worker | PID Worker | `AIAction(new_ki, gamma, justification)` |
| `EVENT.ALARM.{id}` | Alarm Engine | UI, DB Worker | `AlarmEvent` |
| `ALARM.RECENT` | Alarm Engine | UI (alarm bar) | `list[AlarmEvent]` (last 10) |
| `LOG.AI.{id}` | AI Worker | UI (log box), DB Worker | `AILogEntry` |
| `SYS.STATE` | Loop Manager | UI, all workers | `SystemState` |

### 4.2 Thread Model (per control loop)

| Thread | Priority | Responsibility | Scan Rate |
|---|---|---|---|
| GUI (Main) | Normal | PySide6 event loop, chart rendering | QTimer 33ms (~30 FPS) |
| I/O Worker | Normal | OPC-UA async read/write, watchdog | Controller scan rate |
| PID Worker | High | PID equation, alarm detection | Controller scan rate |
| AI Worker | Low | Fuzzy/RL inference | dead_time_L * 3 |
| DB Worker | Low (shared) | Batch insert SQLite | Every 5-10s |

**Resilience rules:**
- AI Worker failure: PID Worker continues with last valid Ki
- I/O Worker connection loss: `SYS.STATE=RECONNECTING`, bumpless transfer on reconnect
- DB Worker delay: data buffered in RAM deque, no impact on control
- GUI never blocks: only consumes events from bus via BusBridge

### 4.3 Bus Bridge (ZMQ -> Qt)

```
ZMQ Bus (threads) --poll--> BusBridge (QTimer 33ms) --Qt Signal--> Widgets
```

Widgets never touch the bus directly. They connect to Qt Signals emitted by BusBridge. This keeps all UI updates on the main thread (Qt requirement).

---

## 5. Domain Models

### 5.1 Core Models

- **`Controller`**: Full configuration of a control loop (PID params, scales, mode, AI config, tag bindings, alarm config)
- **`PIDParams`**: gain, reset (Ti), rate (Td), alpha (derivative filter), deadband
- **`ScaleConfig`**: eu_min, eu_max, unit
- **`TelemetryFrame`**: Frozen dataclass with pv, sp, co, integral_val, timestamp, status
- **`AIConfig`**: engine (NONE/FUZZY/RL), objective, process_speed, dead_time_l, limits
- **`AlarmConfig`**: HIHI/HI/LO/LOLO values and priorities, deadband_percent
- **`User`**: username, password_hash, role (Admin/Supervisor/Operator)
- **`Project`**: metadata for .spid file

### 5.2 Domain Events (frozen dataclasses)

- `TelemetryReceived`, `ControlActionComputed`, `AIActionApplied`
- `AlarmTriggered`, `AlarmCleared`, `AlarmAcknowledged`
- `SystemStateChanged`

### 5.3 Ports (Protocol classes)

**Inbound:**
- `TelemetrySource`: read_telemetry(), connect(), disconnect()
- `TagBrowser`: browse_children(), search()

**Outbound:**
- `ControlWriter`: write_output(), write_parameter()
- `ControllerRepository`: get(), list_all(), save(), delete()
- `HistorianWriter`: write_batch(), query(), cleanup_older_than()
- `AlarmNotifier`: notify()
- `ExportWriter`: export_csv(), export_xlsx(), export_pdf()

---

## 6. Domain Services

### 6.1 PID Engine

- Velocity form equation (derivative on PV) as specified in bloco_pid.md
- `PIDState` passed and returned explicitly (no hidden state)
- Anti-windup: pauses integral accumulation when CO hits limits
- Bumpless transfer: recalculates integral on mode change
- SP ramp: applies SP_RATE_UP / SP_RATE_DN
- Derivative filter: alpha = Rate / 8

### 6.2 PID Mode Manager

State machine for 8 operating modes: OOS, IMan, LO, Man, Auto, Cas, RCas, ROut.

- Validates transitions against permitted modes
- Forced transitions: Bad PV -> Man, TRK_IN_D -> LO, shed timeout -> configured mode
- CONTROL_OPTS and IO_OPTS as specified in bloco_pid.md

### 6.3 Fuzzy Engine

- Input normalization to -100%..+100% of span
- 7 linguistic levels: NB, NM, NS, ZO, PS, PM, PB
- Triangular MFs (center) + trapezoidal (extremes), 50% overlap
- 3 rule matrices: SP Tracking, Disturbance Rejection, Surge Level
- Defuzzification: Center of Gravity (CoG) -> gamma [-1.0, +1.0]
- Ki update: `Ki_new = Ki_current * (1 + gamma * Sv)`, clamped to limits
- Speed factor: SLOW=0.30, MEDIUM=0.15, FAST=0.05
- Cycle time: `T_cycle = dead_time_L * 3`

### 6.4 RL Engine

- SAC/PPO agent via stable-baselines3 (lazy import in application layer)
- Domain defines: observation space, reward functions, action mapping
- Reward functions per objective (IAE/ITAE minimization, TV penalty, deadband tolerance)
- Same guardrails (Ki limits) and cadence (T_cycle) as Fuzzy

### 6.5 Alarm Engine

- Levels: HIHI, HI, LO, LOLO with configurable deadband (hysteresis)
- Deviation alarms: DV_HI, DV_LO (suppressed during SP changes)
- Priorities: CRITICAL (red), WARNING (yellow), ADVISORY (purple), LOG (gray)

### 6.6 Statistics Calculator

- IAE, MSE, ISE, ITAE (sliding window via deque)
- Standard deviation, variability (SP-based and range-based)
- Total Variation (CO chattering)
- Saturation index (time at 0% or 100%)

---

## 7. Application Layer

### 7.1 Event Bus

ZeroMQ XPUB/XSUB proxy running in dedicated daemon thread. `BusPublisher` and `BusSubscriber` classes encapsulate socket creation and msgpack serialization.

### 7.2 Workers

- **PIDWorker**: One per controller. High-priority daemon thread. Scan rate loop using `time.monotonic()`. Consumes TELEMETRY, applies AI adjustments, publishes ACTION.CTRL. Runs AlarmEngine on each scan.
- **AIWorker**: One per controller. Low-priority daemon thread. Cadence = dead_time * 3. Accumulates telemetry in deque. Runs Fuzzy or RL inference. Publishes ACTION.AI + LOG.AI. State: RUN/PAUSE/STOP independent from PID mode.
- **IOWorker**: One per controller. Runs own asyncio event loop. OPC-UA read/write cycle. Connection state machine with exponential backoff reconnect. Watchdog heartbeat toggle.
- **DBWorker**: One shared instance. Subscribes to TELEMETRY.*, EVENT.ALARM.*, LOG.AI.*. Batch insert every flush_interval. Periodic cleanup by retention policy.

### 7.3 Loop Manager

Manages lifecycle of all controller loops. `start_loop()` instantiates domain services, creates adapters via AdapterFactory, spawns workers. `stop_loop()` signals workers, flushes DB, publishes SYS.STATE. Maintains `LoopContext` per controller.

### 7.4 Project Manager

Handles .spid file lifecycle: New (create schema), Open (stop loops, switch DB, reconnect), Save (flush state), Save As (clone with option to strip history).

---

## 8. Adapters

### 8.1 Inbound

- **OPCUAClient**: asyncua-based. Implements TelemetrySource + TagBrowser. Batch read for efficiency. Tag NodeIDs from Controller config.
- **SimulatorAdapter**: Implements TelemetrySource. 4 presets (Flow/Level/Pressure/Temperature via scipy.signal) + Custom SOPTD (python-control). Dead time via Pade approximation. Embedded asyncua.Server on localhost. Noise injection and load step disturbance.

### 8.2 Outbound

- **OPCUAWriter**: Implements ControlWriter. Shares asyncua.Client with OPCUAClient. Watchdog heartbeat (WD_HEART_BEAT_NOT). Increase-to-Close option.
- **SQLiteRepository**: Implements ControllerRepository. aiosqlite with WAL mode. Full DDL from spec Module 6.
- **SQLiteHistorian**: Implements HistorianWriter. executemany() batch inserts. Retention cleanup (7 days process, 30 days alarms).
- **ExportService**: Implements ExportWriter. CSV (csv module), XLSX (openpyxl), PDF (reportlab). Runs in background thread.

### 8.3 AdapterFactory

Centralized dependency injection. Creates concrete adapters based on configuration. Only place that knows which concrete classes exist. LoopManager asks for "a TelemetrySource" and gets either OPCUAClient or SimulatorAdapter.

---

## 9. UI Layer

### 9.1 Architecture

- PySide6 with QStackedWidget for page navigation
- BusBridge pattern: QTimer (33ms) polls ZMQ subscriber -> emits Qt Signals -> widgets update
- Widgets never touch the bus or adapters directly

### 9.2 Theme System

ThemeBase(Protocol) defines: colors (bg, fg, accent, alarm colors per ISA-101), chart colors, fonts, sizes. Each theme implements `apply(app: QApplication)` setting QSS stylesheet.

Three themes:
- **Dark Mode**: Dark room style
- **Material Design 3**: Google MD3 colors, elevation, Roboto typography
- **ISA-101**: Gray tones, soft process colors, primary colors only for alarms

Hot-switch without restart via Settings dropdown.

### 9.3 Pages

1. **Dashboard Executive**: Global KPIs (% Auto, % AI coverage), Bad Actors (top 5 IAE), AI ROI (before/after), system health (CPU/RAM/uptime)
2. **Dashboard Operational (Main)**: Grid of ControllerCards with analog bars (top), TrendChart + Faceplate (bottom 70/30 split), AILogBox, AlarmBar (fixed footer)
3. **Multi-Trend**: 2x2 grid, Time-Sync (zoom/pan synchronized across 4 charts)
4. **Alarm Panel**: Full table with filters (priority, type, time range), ACK button
5. **Settings**: OPC-UA endpoint config, test connection, project management (New/Open/Save/SaveAs)

### 9.4 Key Widgets

- **TrendChart**: pyqtgraph PlotWidget. Y1 (PV/SP), Y2 (CO). Time window selector (value + unit dropdown). Auto-scale checkbox. Manual scale fields. AI action markers (orange circles). CSV export button. Downsampling for large datasets.
- **Faceplate**: Bar graphs (PV/SP/CO), numeric inputs, stats display (2σ/Range, IAE), mode indicator, optimizer state buttons (RUN/PAUSE/STOP), config gear icon.
- **ControllerCard**: Fixed 280px width, left-justified horizontal row. Alarm strip (5px colored bar at top), tag name + description header with alarm icon and settings button (⚙/CFG), PV/SP/CO analog bars. Border color indicates alarm state. No sparklines or mode badge — trend data shown in TrendChart.
- **AILogBox**: Terminal-style scrolling text with timestamps and color-coded entries (Fuzzy orange, RL cyan).
- **AlarmBar**: Fixed bottom widget showing 10 most recent alarms across all controllers.
- **OPCUABrowser**: Modal tree view for navigating OPC-UA address space, search bar, double-click to select NodeID.

---

## 10. Configuration

### 10.1 Settings (pydantic-settings)

Environment prefix: `SPID_`. Loaded from `.env` file.

Key settings: opcua_endpoint, opcua_timeout, db_retention days, db_flush_interval, simulator_port/enabled, theme, chart_fps, chart_max_points.

### 10.2 Exception Hierarchy

```
SmartPIDError
├── DomainError
│   ├── PIDComputationError
│   ├── AIInferenceError
│   ├── AlarmConfigError
│   └── InvalidModeTransition
├── InfrastructureError
│   ├── OPCUAConnectionError
│   ├── OPCUAReadError / OPCUAWriteError
│   ├── DatabaseError
│   └── ExportError
├── ProjectError
│   ├── ProjectNotFoundError
│   └── ProjectCorruptedError
├── AuthenticationError
└── AuthorizationError
```

---

## 11. Database Schema

SQLite with WAL mode. File extension: `.spid`.

Tables (from spec Module 6):
- `Usuarios`: RBAC with bcrypt password hash
- `Controladores`: Full controller config including AI and simulator settings
- `Configuracao_Alarmes`: Alarm limits and priorities per controller
- `Log_Processo`: Process historian (indexed by timestamp + controller_id)
- `Log_Sintonia_IA`: AI tuning log with justification
- `Log_Auditoria`: Audit trail (old value -> new value + user)
- `Log_Alarmes`: Alarm events with timestamps (in/out/ack)

Retention: 7 days for process data, 30 days for alarms.

---

## 12. Implementation Phases

### Phase 1: Foundation + PID Core

Scaffold project, config, exceptions, logging, event bus (ZeroMQ), domain models (Controller, PIDParams, TelemetryFrame, etc.), domain events, ports, PID engine (velocity form, anti-windup, bumpless transfer), PID mode manager (8 modes), PID worker, DB schema (all tables), SQLite repository, DB worker, historian.

**Tests:** Unit tests for PID equation, anti-windup, bumpless transfer, mode transitions. Integration tests for event bus and SQLite repo.

**Deliverable:** PID executing in thread, receiving fake telemetry via bus, writing to SQLite.

### Phase 2: Basic UI + Operational Dashboard

QApplication bootstrap, theme loader, BusBridge, main window with navigation, Dark theme, Dashboard Operational (controller cards grid, trend chart, faceplate, AI log box), alarm bar, controller config dialog, project management (New/Open/Save/SaveAs).

**Tests:** pytest-qt: widgets render, bridge emits signals, theme applies.

**Deliverable:** App opens, shows dashboard with fake bus data, navigation works.

### Phase 3: OPC-UA + Simulator

OPC-UA client (asyncua connect/read/batch), OPC-UA writer (CO, Ki, watchdog), tag browser modal, IO worker (async thread, connection state machine, reconnect), tag binding UI, simulator models (4 presets via scipy + Custom SOPTD), simulator OPC-UA server (asyncua), simulator adapter, disturbance injection (noise, load step), simulator UI panel, settings panel (OPC-UA config).

**Tests:** Integration: simulator server read/write, IO worker reconnect.

**Deliverable:** App connects to real OPC-UA or local simulator, PID closes loop, trend shows real data.

### Phase 4: AI (Fuzzy + RL) + Statistics

Fuzzy engine (3 matrices, fuzzification, CoG defuzz), speed factor, Ki update equation, cycle time, RL engine (SAC, observation/action/reward), AI worker, AI log (justification), AI events, statistics calculator (all KPIs), statistics display in faceplate, AI config UI, optimizer controls (RUN/PAUSE/STOP), trend AI markers.

**Tests:** Unit: fuzzy inference with known inputs, reward functions, statistics formulas. Integration: AI worker full cycle.

**Deliverable:** Fuzzy AI optimizing Ki in real-time, reasoning log visible, stats in faceplate.

### Phase 5: Alarms + RBAC + Security

Alarm engine (HIHI/HI/LO/LOLO + deadband + deviation), alarm events and persistence (30 days), alarm panel (table + filters + ACK), alarm visuals (card borders, alarm bar), alarm sound (optional for CRITICAL), RBAC (users table, bcrypt, 3 roles), login screen, permission-based UI (grayed out buttons), audit trail (Log_Auditoria), alarm config dialog.

**Tests:** Unit: alarm detection with deadband, permission checks. Integration: login flow, audit entries.

**Deliverable:** Alarms detected and displayed, login functional, operator cannot change configs.

### Phase 6: Executive Dashboard + Multi-Trend + Export + Themes

Dashboard Executive (global KPIs, Bad Actors, AI ROI, system health), Multi-Trend (2x2 grid, Time-Sync), CSV/XLSX export (per loop or global, background worker), PDF report (charts + stats + AI log), Material Design 3 theme, ISA-101 theme, theme selector (hot-switch), simulator SVG assets with dynamic overlay, export dynamics button.

**Tests:** Visual: themes apply correctly. Integration: export generates valid files.

**Deliverable:** Complete application, all 12 spec modules functional.

### Phase Dependency Graph

```
Phase 1 (Foundation + PID)
   └──> Phase 2 (Basic UI)
           └──> Phase 3 (OPC-UA + Simulator)
                   ├──> Phase 4 (AI + Stats)     [parallel]
                   └──> Phase 5 (Alarms + RBAC)  [parallel]
                           └──> Phase 6 (Executive + Export + Themes)
```

Phases 4 and 5 can run in parallel after Phase 3.

---

## 13. References

- [docs/smartPID.md](../../smartPID.md) — Original spec V2.4 (12 modules)
- [docs/bloco_pid.md](../../bloco_pid.md) — PID block function specification (modes, parameters, equations)
