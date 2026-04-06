# Simulator Internal PID — Design Spec

**Date:** 2026-04-06
**Status:** Approved
**Phase:** 4 (enhancement)

## Goal

Add an internal PID controller to the simulator so users can test SUPERVISORY mode
end-to-end without a real DCS. The simulator becomes a self-contained "mini-DCS":
process model + PID closing the loop internally, with tuning parameters (Kp, Ti, Td)
exposed via OPC-UA for the smartPID system to read/write as it would with a real DCS.

## Requirements

1. Reuse the existing `PIDEngine` — no duplicate PID logic.
2. The PID is optional: toggle on/off via UI checkbox. When off, the simulator
   works as before (CO comes from external source).
3. OPC-UA server exposes Kp, Ti, Td, PID_Mode, PID_SP as writable nodes per controller.
4. The smartPID system connects in SUPERVISORY mode via normal controller creation
   (manual tag binding — same workflow as a real DCS).
5. Simulator continues running in its own daemon thread.
6. REST endpoints for HMI control of the internal PID.

## Non-Goals

- No new PID code — the existing `PIDEngine` is used directly.
- No automatic controller creation — the user configures tag bindings manually.
- No cascade/BKCAL/complex modes — only MAN and AUTO.
- No changes to `PIDEngine`, `Controller` model, or controller creation flow.

## Architecture

### Approach

PID inside `SimulatorAdapter` (Approach A). The `PIDEngine` is instantiated once in
`SimulatorAdapter.__init__()`. Per-controller PID state lives in `_ControllerSim`.
The tick loop conditionally invokes `PIDEngine.compute()` when PID is enabled and in
AUTO mode.

### Thread Model (unchanged)

- `simulator` daemon thread — runs the tick loop (process model + PID compute)
- `opcua-sim-server` daemon thread — runs the asyncua OPC-UA server

## Data Model Changes

### `_ControllerSim` (new fields)

```python
pid_enabled: bool = False
pid_params: PIDParams = field(default_factory=PIDParams)  # Kp=1.0, Ti=10.0, Td=0.0
pid_state: PIDState = field(default_factory=PIDState)
pid_mode: int = 0  # 0=MAN, 1=AUTO
```

### `ControllerSimStatus` DTO (new fields)

```python
pid_enabled: bool = False
pid_kp: float = 1.0
pid_ti: float = 10.0
pid_td: float = 0.0
pid_mode: int = 0
pid_cv: float = 0.0
```

## Tick Loop (modified `_tick`)

```
For each controller:
  1. pv = model.step(co=last_co, dt)           # process model (existing)
  2. Apply disturbances (step/noise)            # existing
  3. If pid_enabled AND pid_mode == AUTO:
       result = PIDEngine.compute(
           params=ctrl.pid_params,
           state=ctrl.pid_state,
           pv=FFSignal.good(pv),
           sp=FFSignal.good(ctrl.sp),
           bkcal_in=FFSignal.good(ctrl.pid_state.cv),  # self-feedback, no cascade
           dt=dt,
           out_limits=(0.0, 100.0),
       )
       ctrl.pid_state = result.new_state
       ctrl.last_co = result.cv                 # PID closes the loop
  4. Update OPC-UA nodes (PV, SP, CO, Kp, Ti, Td, PID_Mode, PID_SP)
```

## OPC-UA Node Structure

Five new nodes per controller (in addition to existing PV, SP, CO, Mode, Status):

```
Objects/SmartPID/Controllers/CTRL_{id}/
  PV        Float   read-only     (existing)
  SP        Float   writable      (existing)
  CO        Float   writable      (existing)
  Mode      Int32   read-only     (existing)
  Status    Int32   read-only     (existing)
  Kp        Float   writable      (NEW)
  Ti        Float   writable      (NEW)
  Td        Float   writable      (NEW)
  PID_Mode  Int32   writable      (NEW — 0=MAN, 1=AUTO)
  PID_SP    Float   writable      (NEW — setpoint for internal PID)
```

All new nodes are writable so the smartPID system (or any OPC-UA client) can
read current tuning and write new values — exactly as with a real DCS.

### Write Handler Expansion

`_WriteHandler._resolve_node()` and `_on_opcua_write()` are expanded to handle:

| Node written | Action |
|---|---|
| `Kp` | Update `ctrl.pid_params.gain` |
| `Ti` | Update `ctrl.pid_params.reset` |
| `Td` | Update `ctrl.pid_params.rate` |
| `PID_Mode` | Update `ctrl.pid_mode` (0=MAN, 1=AUTO) |
| `PID_SP` | Update `ctrl.sp` |

Note: `PIDParams` is a regular (mutable) dataclass, so writes update fields directly
(e.g., `ctrl.pid_params.gain = value`).

## REST Endpoints

New endpoints under the existing simulator router:

| Method | Path | Body | Action |
|---|---|---|---|
| `POST` | `/simulator/{id}/pid/enable` | `{"enabled": bool}` | Enable/disable internal PID |
| `POST` | `/simulator/{id}/pid/params` | `{"kp": float, "ti": float, "td": float}` | Update Kp, Ti, Td |
| `POST` | `/simulator/{id}/pid/mode` | `{"mode": "MAN"\|"AUTO"}` | Change PID mode |
| `GET` | `/simulator/{id}/pid/status` | — | Return current PID state |

Two-path tuning:
1. **Via HMI** (REST) — manual configuration from the simulator tab
2. **Via OPC-UA** (smartPID in SUPERVISORY) — automatic tuning, as with a real DCS

## HMI Changes

### SimulatorPage — new "Internal PID" group

Added between the Parameters group and Disturbances group:

```
┌─ Internal PID ──────────────────────────────┐
│  [✓] Enable PID          Mode: [MAN ▼]      │
│                                              │
│  Kp:  [1.00   ]                              │
│  Ti:  [10.0   ] s                            │
│  Td:  [0.0    ] s                            │
│                                              │
│  [Apply PID Parameters]                      │
└──────────────────────────────────────────────┘
```

- **QCheckBox "Enable PID"**: toggles `pid_enabled` via REST
- **QComboBox Mode**: MAN / AUTO
- **QDoubleSpinBox Kp**: range 0.01–50.0, default 1.0, 2 decimals
- **QDoubleSpinBox Ti**: range 0.1–999.0, default 10.0, 1 decimal, suffix " s"
- **QDoubleSpinBox Td**: range 0.0–999.0, default 0.0, 1 decimal, suffix " s"
- **QPushButton "Apply PID Parameters"**: sends Kp, Ti, Td, Mode to backend

When checkbox is unchecked, all PID controls are disabled (`setEnabled(False)`).

### New signals

```python
pid_enabled_changed = Signal(bool)
pid_params_changed = Signal(float, float, float)  # Kp, Ti, Td
pid_mode_changed = Signal(str)                     # "MAN" or "AUTO"
```

## SimulatorAdapter New Methods

```python
def enable_pid(self, controller_id: int, enabled: bool) -> None
def set_pid_params(self, controller_id: int, kp: float, ti: float, td: float) -> None
def set_pid_mode(self, controller_id: int, mode: int) -> None
def get_pid_status(self, controller_id: int) -> dict
```

## End-to-End SUPERVISORY Test Flow

1. User starts the simulator, selects a process preset (e.g., Temperature)
2. User enables internal PID (checkbox), sets mode to AUTO
3. PID closes the loop internally: PIDEngine computes CO → ProcessModel updates PV
4. User creates a Controller in smartPID with `execution_mode=SUPERVISORY`
5. User configures tag bindings pointing to simulator OPC-UA nodes (PV, Kp, Ti, Td, etc.)
6. SmartPID reads PV, computes new Ti via Fuzzy/RL, writes Ti to OPC-UA node
7. The simulator's internal PID uses the updated Ti in the next scan
8. Process response changes accordingly — visible in the trend

## Files Modified

| File | Change |
|---|---|
| `smart_pid_core/adapters/inbound/simulator_adapter.py` | PIDEngine integration, new methods, tick loop |
| `smart_pid_core/adapters/inbound/opcua_server.py` | 5 new nodes, write handler expansion, update_values expansion |
| `smart_pid_core/adapters/inbound/api/routers/simulator.py` | 4 new REST endpoints |
| `smart_pid_domain/dtos/simulator.py` | `ControllerSimStatus` new PID fields |
| `smart_pid_hmi/pages/simulator_page.py` | "Internal PID" group, new signals |
| `smart_pid_hmi/main_window.py` | Wire new simulator signals to API calls |

## Files NOT Modified

| File | Reason |
|---|---|
| `smart_pid_core/domain/services/pid_engine.py` | Reused as-is |
| `smart_pid_domain/models/controller.py` | No changes to Controller model |
| Controller creation dialog | Manual flow unchanged |

## Testing Strategy

- **Unit tests**: `PIDEngine.compute()` called from `_tick()` produces expected CO
- **Unit tests**: OPC-UA write to Kp/Ti/Td updates `_ControllerSim.pid_params`
- **Unit tests**: PID enable/disable toggle, MAN/AUTO mode switching
- **Unit tests**: REST endpoints return correct status and accept valid payloads
- **Integration test**: Full loop — enable PID AUTO, verify PV converges to SP
- **HMI tests**: "Internal PID" group visibility, checkbox enables/disables controls
