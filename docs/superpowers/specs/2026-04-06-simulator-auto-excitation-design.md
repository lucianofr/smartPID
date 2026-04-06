# Simulator Auto-Excitation Design

**Date:** 2026-04-06  
**Feature:** Automatic SP variation and disturbance injection in the simulator  
**Motivation:** Enable automated excitation of PID loops to test Fuzzy/RL tuning algorithms without manual intervention.

---

## 1. Overview

Two independent auto-excitation modes are added to the simulator:

- **Auto SP Variation**: every `T = 10 × tau1` seconds, the simulator picks a new setpoint at a random value within a configurable `[sp_min%, sp_max%]` range of the process span.
- **Auto Disturbance Injection**: every `T = 10 × tau1` seconds, the simulator injects a step disturbance with a random amplitude within `[-max_amplitude%, +max_amplitude%]` of the process span. This replaces any existing step disturbance.

Both modes can be enabled/disabled **independently** and are configured per controller.

The period `T = 10 × tau1` is computed dynamically — if `tau1` changes via `/simulator/{id}/parameters`, the next excitation event uses the updated value automatically.

---

## 2. Backend Changes

### 2.1 `_ControllerSim` dataclass (6 new fields)

```python
# Auto SP variation
auto_sp_enabled: bool = False
auto_sp_min_pct: float = 30.0    # % of (pv_max - pv_min) span
auto_sp_max_pct: float = 70.0
auto_sp_elapsed_s: float = 0.0   # time accumulator (seconds)

# Auto disturbance injection
auto_dist_enabled: bool = False
auto_dist_max_pct: float = 10.0  # max |amplitude| as % of span
auto_dist_elapsed_s: float = 0.0
```

### 2.2 `SimulatorAdapter._tick()` — auto-excitation logic

Added at the beginning of each tick (before PID compute), per controller:

```python
dt = interval_s  # e.g. 0.1s

period_s = 10.0 * sim.tau1

if sim.auto_sp_enabled:
    sim.auto_sp_elapsed_s += dt
    if sim.auto_sp_elapsed_s >= period_s:
        sim.auto_sp_elapsed_s = 0.0
        span = sim.pv_max - sim.pv_min  # from controller scaling
        lo = sim.pv_min + sim.auto_sp_min_pct / 100.0 * span
        hi = sim.pv_min + sim.auto_sp_max_pct / 100.0 * span
        sim.sp = random.uniform(lo, hi)

if sim.auto_dist_enabled:
    sim.auto_dist_elapsed_s += dt
    if sim.auto_dist_elapsed_s >= period_s:
        sim.auto_dist_elapsed_s = 0.0
        span = sim.pv_max - sim.pv_min
        max_amp = sim.auto_dist_max_pct / 100.0 * span
        sim.step_amplitude = random.uniform(-max_amp, max_amp)
        sim.step_active = True
```

`sim.pv_min` / `sim.pv_max` are read from the controller's `pv_scale` (already available in the adapter via the repository).

### 2.3 New DTOs (`smart_pid_domain/dtos/simulator.py`)

```python
class AutoSPRequest(BaseModel):
    enabled: bool
    sp_min_pct: float = Field(ge=0.0, le=100.0, default=30.0)
    sp_max_pct: float = Field(ge=0.0, le=100.0, default=70.0)

class AutoDisturbanceRequest(BaseModel):
    enabled: bool
    max_amplitude_pct: float = Field(ge=0.0, le=100.0, default=10.0)
```

`ControllerSimStatus` (existing) gains two new optional fields:

```python
auto_sp: AutoSPRequest | None = None
auto_disturbance: AutoDisturbanceRequest | None = None
```

### 2.4 New REST Endpoints (`routers/simulator.py`)

```
PUT /simulator/{id}/auto-sp           — configure and enable/disable auto SP
PUT /simulator/{id}/auto-disturbance  — configure and enable/disable auto disturbance
```

Both require `SUPERVISOR` role (same as existing simulator endpoints).  
Both return `200 OK` with the updated `ControllerSimStatus`.

### 2.5 `SimulatorAdapter` — new methods

```python
def set_auto_sp(self, controller_id: int, req: AutoSPRequest) -> None
def set_auto_disturbance(self, controller_id: int, req: AutoDisturbanceRequest) -> None
```

Thread-safe (protected by existing `self._lock`).  
When `enabled=False`, the elapsed accumulator is reset to 0 to avoid an immediate trigger on re-enable.

---

## 3. HMI Changes

### 3.1 `SimulatorPage` — two new groups

A shared period label is placed above both groups:

> **Excitation Period (10 × τ₁): N s**  
> Updates in real-time when Tau1 spinbox value changes (no Apply needed).

**Group: "Auto SP Variation"**

| Widget | Type | Range | Default |
|--------|------|-------|---------|
| Enable | QCheckBox | — | unchecked |
| SP Min (%) | QDoubleSpinBox | 0–100 | 30.0 |
| SP Max (%) | QDoubleSpinBox | 0–100 | 70.0 |
| Apply | QPushButton | — | — |

**Group: "Auto Disturbance"**

| Widget | Type | Range | Default |
|--------|------|-------|---------|
| Enable | QCheckBox | — | unchecked |
| Max Amplitude (%) | QDoubleSpinBox | 0–100 | 10.0 |
| Apply | QPushButton | — | — |

### 3.2 New signals emitted by `SimulatorPage`

```python
auto_sp_changed = Signal(bool, float, float)        # enabled, sp_min_pct, sp_max_pct
auto_disturbance_changed = Signal(bool, float)       # enabled, max_amplitude_pct
```

### 3.3 `MainWindow` wiring

Two new `_send_sim_auto_*` methods calling `api_client.set_simulator_auto_sp()` and `api_client.set_simulator_auto_disturbance()`.

### 3.4 `ApiClient` — two new methods

```python
async def set_simulator_auto_sp(self, controller_id: int, enabled: bool,
                                 sp_min_pct: float, sp_max_pct: float) -> dict
async def set_simulator_auto_disturbance(self, controller_id: int, enabled: bool,
                                          max_amplitude_pct: float) -> dict
```

### 3.5 Status loading

When the controller selector changes in `SimulatorPage`, the existing `GET /simulator/status` call is made. The page reads `auto_sp` and `auto_disturbance` from the response and populates the new widgets.

---

## 4. Data Flow

```
User clicks "Apply" in HMI
    → SimulatorPage emits auto_sp_changed / auto_disturbance_changed
    → MainWindow._send_sim_auto_sp/dist()
    → ApiClient.set_simulator_auto_sp/dist()  [PUT /simulator/{id}/auto-sp]
    → Router calls SimulatorAdapter.set_auto_sp()
    → _ControllerSim fields updated (thread-safe)
    → Next _tick() uses updated config
    → SP or step_amplitude changes after period T
    → OPCUAServer publishes new PV/SP to external OPC-UA clients
    → SmartPID DDC/SUPERVISORY controller picks up new SP or PV disturbance
```

---

## 5. Files Modified

| File | Change |
|------|--------|
| `smart_pid_domain/dtos/simulator.py` | Add `AutoSPRequest`, `AutoDisturbanceRequest`; extend `ControllerSimStatus` |
| `smart_pid_core/adapters/inbound/simulator_adapter.py` | Add 6 fields to `_ControllerSim`; auto-excitation logic in `_tick()`; `set_auto_sp()`, `set_auto_disturbance()` methods |
| `smart_pid_core/adapters/inbound/api/routers/simulator.py` | Add `PUT /{id}/auto-sp` and `PUT /{id}/auto-disturbance` endpoints |
| `smart_pid_hmi/pages/simulator_page.py` | Add period label, "Auto SP Variation" group, "Auto Disturbance" group, two new signals |
| `smart_pid_hmi/main.py` | Wire two new signals to `_send_sim_auto_*` methods |
| `smart_pid_hmi/services/api_client.py` | Add `set_simulator_auto_sp()` and `set_simulator_auto_disturbance()` |
| `smart_pid_hmi/services/ports.py` | Add two new abstract methods to the service port |

---

## 6. Edge Cases

- **sp_min_pct >= sp_max_pct**: validated in the DTO (FastAPI raises 422). HMI should also validate before sending.
- **tau1 = 0**: period would be 0. Guard: `period_s = max(10.0 * sim.tau1, 1.0)` (minimum 1s period).
- **Controller not registered in simulator**: endpoint returns 404 (existing behavior).
- **Re-enable after disable**: elapsed accumulator is reset to 0, so the first excitation happens after a full period (no immediate trigger).
- **pv_min == pv_max** (no span): amplitudes would be zero. Guard: if span ≤ 0, skip excitation.

---

## 7. Out of Scope

- Sinusoidal or PRBS excitation profiles (future enhancement)
- Separate periods for SP and disturbance (both use `10 × tau1`)
- Logging of auto-excitation events to `Log_Processo`
