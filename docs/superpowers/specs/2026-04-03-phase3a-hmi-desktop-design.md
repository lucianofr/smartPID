# Phase 3a: PySide6 HMI Desktop — Design Spec

## 1. Overview

Phase 3a delivers the PySide6 desktop HMI client for the Smart PID Edge Platform. This is the operator-facing application that displays real-time telemetry, allows process control (setpoint, mode, output), and visualizes alarm states.

The HMI is a **pure network client** — it has no direct access to hardware, database, or the internal event bus. It consumes data via:
- **ZeroMQ SUB** (`tcp://`) for real-time telemetry (one-way, Backend → HMI)
- **httpx REST** for commands, history, and login (HMI → Backend)

### Scope

- Connection screen (login + server URL)
- Dashboard Operational (cards grid + trend + faceplate + alarm bar)
- ISA-101 theme (with `ThemeBase` Protocol for future themes)
- Mock service layer for offline dev/test
- 4 core widgets: ControllerCard, Faceplate, TrendChart, AlarmBar

### Out of Scope

- OPC-UA (Phase 3b)
- OPCUABrowser widget (Phase 3b)
- ControllerConfig dialog (future)
- AILogBox (Phase 5)
- Multi-Trend 2x2 (Phase 7)
- Dashboard Executive (Phase 7)
- Dark Room and MD3 themes (Phase 7, only ThemeBase Protocol now)
- Alarm Panel full with ACK (Phase 6)
- Auto-refresh token (future)
- Export CSV from trend (Phase 7)

## 2. Architecture

### 2.1 Package Structure

```
packages/smart_pid_hmi/src/smart_pid_hmi/
├── __init__.py
├── main.py                  # QApplication + MainWindow bootstrap
├── config.py                # HMISettings (pydantic-settings, SPID_HMI_ prefix)
│
├── services/                # Network layer (never imported by widgets)
│   ├── __init__.py
│   ├── api_client.py        # httpx async → REST calls
│   ├── telemetry_sub.py     # ZMQ SUB thread → SimpleQueue
│   ├── session.py           # JWT token storage, login state
│   └── mock_service.py      # Mock implementations for dev/test offline
│
├── bus_bridge.py            # QTimer 33ms drains SimpleQueue → emits typed Qt Signals
│
├── themes/                  # Theme system (Protocol + 1 implementation)
│   ├── __init__.py
│   ├── base.py              # ThemeBase(Protocol)
│   └── isa101.py            # ISA-101 concrete theme (QSS stylesheet)
│
├── pages/                   # Full-screen pages
│   ├── __init__.py
│   ├── connection_page.py   # Login + server URL
│   └── dashboard_page.py    # Layout: cards grid + trend/faceplate + alarm bar
│
└── widgets/                 # Reusable components
    ├── __init__.py
    ├── analog_bar.py        # AnalogBarWidget — continuous bar PV/SP/CO
    ├── controller_card.py   # ControllerCardWidget — summary card per loop
    ├── faceplate.py         # FaceplateWidget — detailed operation panel
    ├── trend_chart.py       # TrendChartWidget — pyqtgraph dual Y-axis
    └── alarm_bar.py         # AlarmBarWidget — footer with last 10 alarms
```

### 2.2 Data Flow

```
Backend (tcp://5555)          HMI
    ZMQ PUB ──────────→ telemetry_sub.py (background thread)
                              │ SimpleQueue (thread-safe)
                              ▼
    FastAPI ◀── httpx ── api_client.py ── session.py (JWT)
                              │
                         bus_bridge.py (QTimer 33ms, main thread)
                              │ Typed Qt Signals
                              ▼
                         widgets (ControllerCard, Faceplate, TrendChart...)
```

### 2.3 Dependency Rules

- **widgets/** and **pages/** depend only on `bus_bridge` signals and `themes.base`
- **services/** is never imported by widgets (full decoupling)
- **bus_bridge** is the sole bridge between network and UI
- **mock_service** implements the same interface as api_client + telemetry_sub

### 2.4 Threading Model

| Thread | Purpose | Rate |
|--------|---------|------|
| **Main (Qt)** | PySide6 event loop, widget rendering, user interaction | — |
| **Telemetry Receiver** | ZMQ SUB socket, pushes frames into SimpleQueue | Continuous |
| **BusBridge** | QTimer on main thread, drains queue → emits Qt Signals | 33ms (~30 FPS) |

## 3. Configuration

`HMISettings` via pydantic-settings with `SPID_HMI_` prefix:

| Variable | Default | Description |
|----------|---------|-------------|
| `SPID_HMI_SERVER_URL` | `http://localhost:8000` | Backend REST URL |
| `SPID_HMI_ZMQ_URL` | `tcp://localhost:5555` | Backend ZMQ PUB URL |
| `SPID_HMI_THEME` | `isa101` | Active theme name |
| `SPID_HMI_MOCK_MODE` | `false` | Use mock services for dev/test |
| `SPID_HMI_REFRESH_MS` | `33` | Bus bridge poll interval (30 FPS) |

## 4. Services Layer

### 4.1 `telemetry_sub.py` — ZMQ Subscriber Thread

- Daemon thread (not asyncio — `threading.Thread`)
- Connects `zmq.SUB` to `tcp://{host}:5555`
- Subscribes to: `TELEMETRY.*`, `EVENT.ALARM.*`, `SYS.STATE`
- Deserializes msgpack → `TelemetryFrame`, `AlarmEvent` from domain
- Enqueues into `queue.SimpleQueue` (thread-safe, lock-free)
- Automatic reconnect with exponential backoff (1s, 2s, 4s... max 30s)
- `stop()` sets flag + closes socket with LINGER=0

### 4.2 `api_client.py` — REST Client

- `httpx.AsyncClient` with base_url from config
- Typed methods returning domain models:
  - `login(username, password) → TokenResponse`
  - `list_controllers() → list[ControllerSummaryDTO]`
  - `get_controller(id) → ControllerDetailDTO`
  - `set_setpoint(id, value) → None`
  - `set_mode(id, mode) → None`
  - `set_output(id, value) → None`
  - `get_history(id, start, end) → list[TelemetryFrame]`
- Headers: `Authorization: Bearer {token}` injected via `session.py`
- Timeout 5s, 1x retry on connection error

### 4.3 `session.py` — JWT Management

- Stores token in memory (not persisted to disk)
- Property `is_authenticated → bool`
- `token_expires_at` parsed from JWT payload
- Signal `session_expired` to force re-login

### 4.4 `mock_service.py` — Mock for Dev/Test

- `MockTelemetrySource`: generates synthetic `TelemetryFrame` every 100ms
  - PV: sinusoidal + gaussian noise (simulates process)
  - SP: constant with periodic step changes
  - CO: PV tracking with lag
  - 3 mock controllers: "FIC-101" (flow), "LIC-201" (level), "TIC-301" (temperature)
- `MockAPIClient`: same interface as `api_client.py`
  - `login()` always returns fake token
  - `list_controllers()` returns 3 fixed controllers
  - `set_setpoint/mode/output` accepts and logs
  - `get_history()` returns last N generated frames
- Feeds the same `SimpleQueue` as real telemetry_sub → bus_bridge is unaware of the difference

### 4.5 Service Ports (Protocol)

```python
class TelemetrySourcePort(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...
    @property
    def queue(self) -> SimpleQueue: ...

class APIClientPort(Protocol):
    async def login(self, username: str, password: str) -> TokenResponse: ...
    async def list_controllers(self) -> list[ControllerSummaryDTO]: ...
    async def get_controller(self, controller_id: str) -> ControllerDetailDTO: ...
    async def set_setpoint(self, controller_id: str, value: float) -> None: ...
    async def set_mode(self, controller_id: str, mode: str) -> None: ...
    async def set_output(self, controller_id: str, value: float) -> None: ...
    async def get_history(
        self, controller_id: str, start: datetime, end: datetime
    ) -> list[TelemetryFrame]: ...
```

`main.py` instantiates mock or real based on `SPID_HMI_MOCK_MODE`.

## 5. Bus Bridge

### 5.1 Signals

```python
class BusBridge(QObject):
    telemetry_received = Signal(str, object)    # (controller_id, TelemetryFrame)
    alarm_received = Signal(str, object)        # (controller_id, AlarmEvent)
    system_state_changed = Signal(object)       # (SystemState)
    connection_lost = Signal()                  # ZMQ timeout detected
    connection_restored = Signal()              # ZMQ reconnected
```

### 5.2 Batching Strategy

- If multiple frames for the same controller arrive in the same tick, emit only the **last** for each controller — avoids repaint flood
- Alarms: emit **all** (never drop)
- Maintains internal `_latest: dict[str, TelemetryFrame]` for widgets requesting current state

### 5.3 Heartbeat / Connection Monitoring

- No frame received in 5s → emit `connection_lost`
- Frames resume → emit `connection_restored`
- Widgets can react by showing "COMM FAIL" indicator

### 5.4 Widget Consumption Pattern

```python
card = ControllerCardWidget(controller_id="FIC-101", theme=theme)
bus_bridge.telemetry_received.connect(card.on_telemetry)
bus_bridge.alarm_received.connect(card.on_alarm)
```

Each widget filters internally by its `controller_id`.

## 6. Theme System

### 6.1 `ThemeBase(Protocol)`

```python
class ThemeBase(Protocol):
    name: str

    # Core palette
    bg_primary: str          # main background
    bg_secondary: str        # secondary panels
    bg_widget: str           # card/widget background
    fg_primary: str          # main text
    fg_secondary: str        # secondary text / labels
    border: str              # borders and dividers

    # Semantic (alarms only)
    alarm_critical: str      # HIHI/LOLO
    alarm_warning: str       # HI/LO
    alarm_text: str          # text on alarm background

    # Bars (PV/SP/CO)
    bar_pv: str
    bar_sp: str
    bar_co: str

    # Chart palette
    chart_pv: str
    chart_sp: str
    chart_co: str
    chart_grid: str
    chart_bg: str

    # Typography
    font_family: str
    font_size_normal: int
    font_size_label: int
    font_size_value: int
    font_size_title: int

    def apply(self, app: QApplication) -> None:
        """Apply QSS stylesheet globally."""
        ...
```

### 6.2 ISA-101 Theme

Based on `docs/identidade_visual_ISA101.md`:

| Token | Value | Usage |
|-------|-------|-------|
| `bg_primary` | `#808080` (Gray 50%) | Main background |
| `bg_secondary` | `#999999` (Gray 60%) | Secondary panels |
| `bg_widget` | `#B0B0B0` (Gray 69%) | Card background |
| `fg_primary` | `#1A1A1A` (near black) | Main text |
| `fg_secondary` | `#4D4D4D` | Labels, units |
| `border` | `#666666` | Flat borders, 1px |
| `alarm_critical` | `#FF0000` | HIHI/LOLO |
| `alarm_warning` | `#FFCC00` | HI/LO |
| `bar_pv` | `#404040` | PV bar fill (normal) |
| `bar_sp` | `#606060` | SP marker |
| `bar_co` | `#505050` | CO bar fill (normal) |
| `chart_pv` | `#333333` | PV line (solid) |
| `chart_sp` | `#666666` | SP line (dashed) |
| `chart_co` | `#505050` | CO line (Y2 axis) |
| `chart_grid` | `#999999` | Grid lines |
| `chart_bg` | `#B0B0B0` | Chart background |
| `font_family` | `"Segoe UI"` / `"Arial"` | Sans-serif, legible |
| `font_size_normal` | `12` | Body text |
| `font_size_label` | `10` | Small labels |
| `font_size_value` | `14` | Numeric values |
| `font_size_title` | `16` | Card titles |

**ISA-101 Rules:**
- 100% flat — zero gradients, zero shadows, zero 3D
- Color = alarm — in normal state, everything is gray. Color appears ONLY for abnormal conditions
- Card borders change color when controller has active alarm
- AnalogBarWidget: gray fill in normal, red/yellow fill in alarm
- `apply()` generates QSS and calls `app.setStyleSheet()`

## 7. Widgets

### 7.1 `AnalogBarWidget`

- Horizontal continuous bar (QPainter custom)
- Props: `value`, `min_val`, `max_val`, `unit`, `label`, `alarm_state`
- SP marker as thin indicator overlay on the bar (when applicable)
- Normal: dark gray fill. Alarm: fill changes to ISA-101 semantic color
- Label left, numeric value right (e.g., `PV  45.3 °C`)
- No rounded corners (flat ISA-101)

### 7.2 `ControllerCardWidget`

- Compact card for grid overview. One per controller.
- Content: tag name, mode badge (Auto/Man/Cas...), 3x AnalogBar (PV, SP, CO)
- Border: 1px gray normal → alarm color when active
- Slot `on_telemetry(controller_id, frame)`: filters by ID, updates bars
- Slot `on_alarm(controller_id, event)`: updates border
- Single click: selects controller (emits `controller_selected(str)`)
- Double-click: opens faceplate (same as select for now)

### 7.3 `FaceplateWidget`

- Fixed side panel (30% width of dashboard, right side)
- Shows selected controller in detail
- Sections:
  - **Header**: tag name + mode badge
  - **Bars**: PV, SP, CO with AnalogBar (larger than card)
  - **Inputs**: SP numeric editable (Enter → `api_client.set_setpoint`), CO editable in MAN mode (Enter → `api_client.set_output`)
  - **Mode buttons**: row of buttons (Auto/Man) → `api_client.set_mode`
  - **Stats**: placeholder for future (IAE, 2σ/Range) — displays "—" for now
- Slot `on_controller_selected(id)`: loads controller data
- Updates in real-time via `bus_bridge.telemetry_received`

### 7.4 `TrendChartWidget`

- `pyqtgraph.PlotWidget` with dual Y-axis
- Y1 (left): PV (solid line) + SP (dashed line)
- Y2 (right): CO
- Circular buffer in memory: last N points (default 600 = 10min at 1s scan)
- Time axis (bottom): timestamps formatted HH:MM:SS
- Controls: combo time window (1min, 5min, 10min, 30min, 1h)
- Auto-scale Y by default, with fixed range option
- Colors from theme (`chart_pv`, `chart_sp`, `chart_co`)
- Subtle grid (`chart_grid`)
- Updates via `bus_bridge.telemetry_received`, filters by selected controller

### 7.5 `AlarmBarWidget`

- Fixed footer at dashboard bottom. Fixed height ~40px.
- Horizontal scrollable list of last 10 alarms (all controllers)
- Each item: `timestamp | TAG | type (HIHI/HI/LO/LOLO) | value`
- Background: semantic color (red critical, yellow warning)
- Slot `on_alarm(controller_id, event)`: prepend to list, remove oldest if > 10
- No interaction (ACK comes in Phase 6)

## 8. Pages

### 8.1 `ConnectionPage`

- Initial screen, displayed on app open
- Centered layout:
  - Field: Server URL (default from config, editable)
  - Field: Username
  - Field: Password (masked)
  - Button: Connect
  - Status/error label (hidden by default)
- Flow:
  1. User fills fields and clicks Connect
  2. Calls `api_client.login(user, pass)`
  3. Success → `session` stores token → starts `telemetry_sub` → navigates to DashboardPage
  4. Failure → shows error in label ("Connection refused" / "Invalid credentials")
- Saves last used server URL in `QSettings` (local Qt persistence)

### 8.2 `DashboardPage`

Layout divided in 3 zones:

```
┌─────────────────────────────────────────────────┐
│  ControllerCard  │  ControllerCard  │  Ctrl...  │  ← Grid top (wrap, ~25% height)
├────────────────────────────────┬────────────────┤
│                                │                │
│       TrendChartWidget         │  Faceplate     │  ← Bottom split (70/30)
│       (pyqtgraph)              │  Widget        │
│                                │                │
├────────────────────────────────┴────────────────┤
│  AlarmBarWidget (footer, ~40px)                 │
└─────────────────────────────────────────────────┘
```

- On startup: calls `api_client.list_controllers()` → creates one `ControllerCardWidget` per controller
- Cards in `QGridLayout` with wrapping
- First controller auto-selected → Faceplate and TrendChart show its data
- Signal flow: `card.controller_selected` → `faceplate.on_controller_selected` + `trend.on_controller_selected`

### 8.3 `MainWindow`

- `QMainWindow` with `QStackedWidget` for page navigation
- Minimal toolbar: app name, connection indicator (green/red), logged username
- Method `navigate_to(page_name)` switches active page
- On close: stops telemetry_sub, cleanup

### 8.4 Application Lifecycle

```
main.py
  → QApplication()
  → HMISettings loaded
  → ISA-101 theme applied (app.setStyleSheet)
  → MainWindow created
  → If MOCK_MODE: MockTelemetrySource + MockAPIClient
    Else: TelemetrySub + APIClient (real)
  → BusBridge(queue) created, timer started
  → ConnectionPage displayed
  → Login → DashboardPage
  → app.exec()
```

## 9. Testing Strategy

### 9.1 Dependencies

- `pytest-qt` — `qtbot` fixture for PySide6 widget testing

### 9.2 Test Matrix

| Module | Tests | Type |
|--------|-------|------|
| `config.py` | Loads defaults, override via env | Unit |
| `session.py` | Token storage, is_authenticated, expiry | Unit |
| `api_client.py` | Login, list_controllers, set_setpoint (httpx mock) | Unit |
| `telemetry_sub.py` | Connect, deserialize, enqueue, reconnect | Unit |
| `mock_service.py` | Generates valid frames, compatible interface | Unit |
| `bus_bridge.py` | Drains queue, emits correct signals, batching | Unit + pytest-qt |
| `isa101.py` | apply() no crash, QSS not empty | Unit + pytest-qt |
| `analog_bar.py` | Renders, updates value, changes color on alarm | pytest-qt |
| `controller_card.py` | Shows data, emits controller_selected | pytest-qt |
| `faceplate.py` | Updates with telemetry, SP input emits command | pytest-qt |
| `trend_chart.py` | Adds data, circular buffer, time window | pytest-qt |
| `alarm_bar.py` | Adds alarms, max 10, correct color | pytest-qt |
| `connection_page.py` | Login flow success/error | pytest-qt |
| `dashboard_page.py` | Creates cards, selects controller, layout | pytest-qt |
| **Integration** | Mock → bridge → card updates value | pytest-qt |

## 10. Dependencies

### 10.1 Runtime (`smart_pid_hmi/pyproject.toml`)

| Package | Version | Usage |
|---------|---------|-------|
| `PySide6` | `>=6.7` | Qt6 bindings (LGPL) |
| `pyqtgraph` | `>=0.13` | TrendChart real-time plots |
| `httpx` | `>=0.27` | REST client async |
| `pyzmq` | `>=26` | ZMQ SUB (already in workspace) |
| `msgpack` | `>=1.0` | Deserialization (already in workspace) |
| `pydantic-settings` | `>=2.0` | HMISettings config |

### 10.2 Dev/Test

| Package | Usage |
|---------|-------|
| `pytest-qt` | Widget testing with qtbot |

## 11. Deliverable

A functional PySide6 desktop application that:

1. Connects to a Smart PID backend (or runs with mock data)
2. Displays operational dashboard with cards per controller
3. Allows selecting controller → view faceplate + trend in real-time
4. Shows recent alarms in footer bar
5. Allows operation: change SP, mode, CO via faceplate
6. ISA-101 theme applied, with `ThemeBase` infrastructure for future themes
