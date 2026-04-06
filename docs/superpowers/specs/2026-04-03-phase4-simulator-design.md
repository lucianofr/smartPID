# Phase 4: Simulator (Digital Twin) — Design Spec

**Date:** 2026-04-03
**Status:** Approved
**Parent Spec:** `2026-04-02-smart-pid-v2-architecture-design.md`
**Phase:** 4 of 7
**Prerequisites:** Phase 1 (Domain + PID) ✅, Phase 2 (REST + Auth + Telemetry) ✅, Phase 3a (HMI Desktop) ✅

---

## 1. Goal

Provide a digital twin that simulates industrial process dynamics, enabling end-to-end PID testing and AI tuning validation without physical hardware. The simulator runs an embedded OPC-UA server accessible by any standard OPC-UA client, and integrates with the existing backend via the hexagonal port/adapter pattern.

## 2. Scope

### In scope (this phase)

- 4 preset process models (Flow, Level, Pressure, Temperature) + Custom SOPTD
- SimulatorAdapter implementing both `TelemetrySource` and `ControlWriter` ports
- Embedded `asyncua.Server` on configurable port (default 4841)
- Closed-loop operation: PID CO feeds back into process model
- Manual disturbance injection (step ± amplitude, white noise toggle)
- REST endpoints for simulator control (`/simulator/*`)
- Basic HMI Simulator page (preset selector, parameter sliders, disturbance buttons)
- AdapterFactory conditional creation based on `SPID_SIMULATOR` setting

### Out of scope (deferred to Phase 7)

- SVG process overlay visualization
- "Export Dynamics to Loop" feature
- Programmed disturbance sequences / predefined scenarios

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     smart_pid_core                       │
│                                                          │
│  ┌──────────────┐      ┌──────────────────────────┐     │
│  │  LoopManager  │─────▶│   SimulatorAdapter        │     │
│  │  (PID Engine) │      │  (TelemetrySource +       │     │
│  │               │◀─────│   ControlWriter)          │     │
│  └──────────────┘      │                            │     │
│        │                │  ┌──────────────────┐     │     │
│        │                │  │ ProcessModel     │     │     │
│        │                │  │ (scipy.signal)   │     │     │
│        │                │  └──────────────────┘     │     │
│        │                │  ┌──────────────────┐     │     │
│        │                │  │ asyncua.Server   │     │     │
│        ▼                │  │ :4841            │     │     │
│   Event Bus ◀───────────│  └────────┬─────────┘     │     │
│   (ZMQ)                 └───────────┼────────────────┘     │
│        │                            │                      │
└────────┼────────────────────────────┼──────────────────────┘
         │                            │
    ZMQ tcp:5555               OPC-UA tcp:4841
         │                            │
         ▼                            ▼
   ┌──────────┐               ┌──────────────┐
   │   HMI    │               │ Any OPC-UA   │
   │ (PySide6)│               │   Client     │
   └──────────┘               └──────────────┘
```

### Data flow (closed-loop, one cycle)

1. `SimulatorAdapter` thread wakes at configured interval (default 100ms)
2. Reads last CO written by PID engine via `write_output()` (ControlWriter port)
3. Feeds CO as input to `ProcessModel.step(co, dt)`
4. Adds active disturbances (step offset, noise) to resulting PV
5. Updates OPC-UA server nodes (PV, SP, CO, Mode, Status)
6. Publishes telemetry frame to `SimpleQueue` (TelemetrySource port)
7. LoopManager's PID engine reads PV, computes new CO
8. PID calls `write_output(co)` on the ControlWriter → back to step 2

---

## 4. Process Models

All models use `scipy.signal` for transfer function construction and step-by-step simulation.

### 4.1 Model types

**FOPTD (First-Order Plus Dead Time):**

```
G(s) = K * e^(-Ls) / (τ₁s + 1)
```

Used for fast-responding processes (Flow, Pressure).

**SOPTD (Second-Order Plus Dead Time):**

```
G(s) = K * e^(-Ls) / (τ₁s + 1)(τ₂s + 1)
```

Used for slower processes with more complex dynamics (Level, Temperature, Custom).

Dead time implemented via Padé approximation (order 3).

### 4.2 Preset parameters

| Preset | Type | K | τ₁ (s) | τ₂ (s) | L (s) | Rationale |
|--------|------|-----|--------|--------|-------|-----------|
| Flow | FOPTD | 1.2 | 3 | — | 1 | Fast valve response, short dead time |
| Pressure | FOPTD | 0.8 | 10 | — | 2 | Compressible fluid, moderate lag |
| Level | SOPTD | 2.0 | 30 | 15 | 5 | Tank interaction, integrating behavior |
| Temperature | SOPTD | 1.5 | 60 | 20 | 10 | Heat exchanger, thermal inertia |
| Custom | SOPTD | user | user | user | user | Any user-defined dynamics |

### 4.3 Implementation

File: `packages/smart_pid_core/src/smart_pid_core/domain/services/process_models.py`

```python
class ProcessModel:
    """Continuous-time process model with dead time via Padé approximation."""

    def __init__(self, gain: float, tau1: float, tau2: float | None,
                 dead_time: float) -> None: ...

    def step(self, co: float, dt: float) -> float:
        """Advance one time step with given control output, return new PV."""

    def reset(self) -> None:
        """Reset internal state to initial conditions."""
```

Presets defined as frozen dataclasses:

```python
@dataclass(frozen=True)
class ProcessPreset:
    name: str
    model_type: str          # "FOPTD" or "SOPTD"
    gain: float
    tau1: float
    tau2: float | None
    dead_time: float
```

Enum `ProcessPresetName` in `smart_pid_domain/enums.py`: `FLOW`, `PRESSURE`, `LEVEL`, `TEMPERATURE`, `CUSTOM`.

### 4.4 Disturbances

Additive to PV after model computation:

- **Step**: constant offset added until cleared. `pv_out = pv_model + step_amplitude`
- **Noise**: Gaussian white noise. `pv_out = pv_model + random.gauss(0, noise_amplitude)`
- Both can be active simultaneously.

---

## 5. SimulatorAdapter

File: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/simulator_adapter.py`

Implements two hexagonal ports:

- `TelemetrySource` — publishes simulated PV/SP/CO/status frames to SimpleQueue
- `ControlWriter` — receives CO from PID engine, stores for next simulation cycle

### 5.1 Responsibilities

- Manages one `ProcessModel` per configured controller
- Runs a dedicated daemon thread with configurable cycle time (default 100ms)
- Manages the embedded `asyncua.Server` lifecycle (start/stop)
- Exposes control methods for REST layer: `set_preset()`, `set_parameters()`, `inject_step()`, `inject_noise()`, `clear_disturbance()`
- Thread-safe: CO writes from PID thread, reads from simulator thread (use `threading.Lock`)

### 5.2 Interface

```python
class SimulatorAdapter:
    """Digital twin adapter — TelemetrySource + ControlWriter."""

    def __init__(self, settings: CoreSettings) -> None: ...

    # TelemetrySource port
    def start(self) -> None: ...
    def stop(self) -> None: ...
    @property
    def queue(self) -> SimpleQueue: ...

    # ControlWriter port
    def write_output(self, controller_id: int, value: float) -> None: ...

    # Simulator control (called from REST handlers)
    def set_preset(self, controller_id: int, preset: str) -> None: ...
    def set_parameters(self, controller_id: int, gain: float, tau1: float,
                       tau2: float | None, dead_time: float) -> None: ...
    def inject_step(self, controller_id: int, amplitude: float) -> None: ...
    def inject_noise(self, controller_id: int, amplitude: float) -> None: ...
    def clear_disturbance(self, controller_id: int) -> None: ...
    def get_status(self) -> dict: ...
```

---

## 6. OPC-UA Server

Embedded `asyncua.Server` managed by `SimulatorAdapter`.

### 6.1 Configuration

| Setting | Env var | Default |
|---------|---------|---------|
| Port | `SPID_SIM_PORT` | `4841` |
| Enabled | `SPID_SIMULATOR` | `false` |

Endpoint: `opc.tcp://0.0.0.0:4841`
Namespace URI: `urn:smartpid:simulator`

### 6.2 Node structure

Per controller (e.g., controller_id=1):

```
Objects/
  SmartPID_Simulator/
    Controller_1/
      PV    (Double, read-only)
      SP    (Double, read-only)
      CO    (Double, read-only)
      Mode  (String, read-only)
      Status (String, read-only)
    Controller_2/
      ...
```

All nodes are read-only from external clients. The SimulatorAdapter writes PV values; CO is written by the PID via ControlWriter port (internal).

### 6.3 Update cycle

Nodes are updated every simulation cycle (synchronous with ProcessModel step). External OPC-UA clients see values at the simulation rate.

---

## 7. REST Endpoints

Added to FastAPI app under `/simulator` prefix. Protected by JWT auth (existing middleware).

| Method | Path | Body | Response | Description |
|--------|------|------|----------|-------------|
| `GET` | `/simulator/status` | — | `SimulatorStatusResponse` | Current state: enabled, per-controller preset/params/disturbances |
| `POST` | `/simulator/preset` | `{controller_id, preset}` | `CommandResponse` | Set process model preset for a controller |
| `PUT` | `/simulator/parameters` | `{controller_id, gain, tau1, tau2?, dead_time}` | `CommandResponse` | Set custom parameters (works with any preset) |
| `POST` | `/simulator/disturbance` | `{controller_id, type, amplitude}` | `CommandResponse` | Inject step or noise disturbance |
| `DELETE` | `/simulator/disturbance/{controller_id}` | — | `CommandResponse` | Clear all disturbances for a controller |

### 7.1 DTOs

Added to `smart_pid_domain/dtos/`:

```python
class SimulatorPresetRequest(BaseModel):
    controller_id: int
    preset: ProcessPresetName

class SimulatorParametersRequest(BaseModel):
    controller_id: int
    gain: float
    tau1: float
    tau2: float | None = None
    dead_time: float

class SimulatorDisturbanceRequest(BaseModel):
    controller_id: int
    type: Literal["step", "noise"]
    amplitude: float

class SimulatorStatusResponse(BaseModel):
    enabled: bool
    controllers: dict[int, ControllerSimStatus]

class ControllerSimStatus(BaseModel):
    preset: str
    gain: float
    tau1: float
    tau2: float | None
    dead_time: float
    step_active: bool
    step_amplitude: float
    noise_active: bool
    noise_amplitude: float
```

---

## 8. ControlWriter Port

New port in `smart_pid_core/domain/ports/outbound/`:

```python
class ControlWriter(Protocol):
    def write_output(self, controller_id: int, value: float) -> None: ...
```

The `SimulatorAdapter` implements this directly. In production (Phase 3b), `OPCUAWriter` will implement it.

`LoopManager` receives a `ControlWriter` via dependency injection (AdapterFactory).

---

## 9. AdapterFactory

File: `packages/smart_pid_core/src/smart_pid_core/adapters/factory.py`

Centralized DI based on `CoreSettings`:

```python
class AdapterFactory:
    def __init__(self, settings: CoreSettings) -> None: ...

    def create_telemetry_source(self) -> TelemetrySource:
        if self._settings.simulator_enabled:
            return self._simulator_adapter
        raise NotImplementedError("OPCUAClient not yet implemented (Phase 3b)")

    def create_control_writer(self) -> ControlWriter:
        if self._settings.simulator_enabled:
            return self._simulator_adapter  # same instance
        raise NotImplementedError("OPCUAWriter not yet implemented (Phase 3b)")
```

The same `SimulatorAdapter` instance serves both roles.

---

## 10. HMI — Simulator Page

File: `packages/smart_pid_hmi/src/smart_pid_hmi/pages/simulator_page.py`

### 10.1 Layout

```
┌─────────────────────────────────────────┐
│  Simulator Control                       │
├─────────────────────────────────────────┤
│  Controller: [▼ FIC-101  ]              │
│                                          │
│  Preset: [▼ Flow      ]                │
│                                          │
│  Parameters                              │
│  Gain (K):    [====●====] 1.20          │
│  Tau1 (s):    [====●====] 3.00          │
│  Tau2 (s):    [====●====] ---  (disabled)│
│  Dead Time:   [====●====] 1.00          │
│                                          │
│  Disturbances                            │
│  Step: [-5%] [Amplitude: ___] [+5%]     │
│  Noise: [OFF/ON]  [Amplitude: ___]      │
│                                          │
│  [Clear All Disturbances]               │
│                                          │
│  Status: Flow preset, no disturbances    │
└─────────────────────────────────────────┘
```

### 10.2 Behavior

- Controller combo populated from `APIClient.list_controllers()`
- Preset combo: Flow, Pressure, Level, Temperature, Custom
- Selecting a preset calls `POST /simulator/preset` and updates slider ranges/defaults
- Parameter sliders call `PUT /simulator/parameters` on release (not during drag)
- τ₂ slider disabled for FOPTD presets, enabled for SOPTD/Custom
- Step buttons call `POST /simulator/disturbance` with type="step"
- Noise toggle calls `POST /simulator/disturbance` with type="noise" (or DELETE to clear)
- Status label refreshed via `GET /simulator/status` on a 2-second QTimer

### 10.3 Navigation

New toolbar button "Simulator" in MainWindow, adds SimulatorPage to QStackedWidget. Only visible/enabled when connected to a backend with `simulator_enabled=true` (detected via `GET /simulator/status` returning 200 vs 404).

---

## 11. Configuration Changes

### 11.1 CoreSettings additions

Already partially defined. Verify:

| Field | Env var | Default | Description |
|-------|---------|---------|-------------|
| `simulator_enabled` | `SPID_SIMULATOR` | `false` | Enable simulator mode |
| `simulator_port` | `SPID_SIM_PORT` | `4841` | OPC-UA server port |
| `simulator_interval_ms` | `SPID_SIM_INTERVAL` | `100` | Simulation cycle time (ms) |

### 11.2 Dependencies

Added to `smart_pid_core/pyproject.toml`:

- `asyncua>=1.0` (OPC-UA server + client)
- `scipy>=1.11` (signal processing, transfer functions)

Note: `python-control` is NOT needed — `scipy.signal` handles FOPTD/SOPTD construction and step simulation directly.

---

## 12. Testing Strategy

### 12.1 Unit tests

- **ProcessModel**: Step response matches expected gain/time-constants for each preset. Dead time behavior verified. Reset works.
- **SimulatorAdapter**: CO write → PV change (closed-loop verification). Disturbance injection additive. Thread safety.
- **REST endpoints**: Mock SimulatorAdapter, verify request routing and response format.
- **HMI SimulatorPage**: Widget state, signal emissions, API calls mocked.
- **DTOs**: Serialization/deserialization of new request/response models.

### 12.2 Integration tests

- **Full loop**: SimulatorAdapter + PID engine → CO feeds back → PV converges to SP.
- **OPC-UA**: Connect asyncua.Client to embedded server, verify nodes update with simulation.
- **REST → Adapter**: Preset change via REST → model parameters actually change.

---

## 13. File inventory

### New files

| Package | Path | Description |
|---------|------|-------------|
| domain | `enums.py` (update) | Add `ProcessPresetName` enum |
| domain | `dtos/simulator.py` | Simulator request/response DTOs |
| core | `domain/services/process_models.py` | ProcessModel + ProcessPreset |
| core | `domain/ports/outbound/control_writer.py` | ControlWriter Protocol |
| core | `adapters/inbound/simulator_adapter.py` | SimulatorAdapter |
| core | `adapters/factory.py` | AdapterFactory |
| core | `api/routes/simulator.py` | REST endpoints |
| hmi | `pages/simulator_page.py` | Simulator UI page |

### Modified files

| Package | Path | Change |
|---------|------|--------|
| core | `config.py` | Add `simulator_interval_ms` setting |
| core | `main.py` | Wire AdapterFactory, register simulator routes |
| core | `pyproject.toml` | Add asyncua, scipy dependencies |
| hmi | `main.py` | Add Simulator toolbar button + page |
| hmi | `services/api_client.py` | Add simulator API methods |

---

## 14. Internal PID (Phase 4 Enhancement)

The simulator supports an optional **internal PID controller** that closes the loop
entirely within the simulator, enabling end-to-end testing of SUPERVISORY mode without
a real DCS. When enabled, the simulator acts as a self-contained "mini-DCS": process
model + PID running internally, with tuning parameters exposed via OPC-UA.

### Key design decisions

- **Reuses existing `PIDEngine`** — no duplicate PID logic; the same engine that runs
  in production is instantiated inside the simulator.
- **Toggle on/off** via a UI checkbox on the Simulator page. When off, the simulator
  works as before (CO comes from the external PID engine).
- **OPC-UA writable nodes** per controller: `Kp`, `Ti`, `Td`, `PID_Mode`, `PID_SP` —
  the smartPID system reads/writes these exactly as it would with a real DCS PLC.
- **REST endpoints** for HMI control: enable/disable internal PID, set parameters,
  query status.
- **No changes to PIDEngine, Controller model, or controller creation flow.**

### Detailed spec

See [`docs/superpowers/specs/2026-04-06-simulator-internal-pid-design.md`](2026-04-06-simulator-internal-pid-design.md)
for full architecture, OPC-UA node layout, REST API, and HMI integration details.
