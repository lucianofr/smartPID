# OPC-UA Server Independent Control — Design Spec

**Date:** 2026-04-06  
**Status:** Approved  
**Scope:** Fix default port, decouple OPC-UA server lifecycle from simulator loop, add UI controls

---

## Problem

1. `SPID_SIMULATOR_PORT` defaults to 4849 in `.env`/`.env.example`, but code defaults are hardcoded to 4841 in `config.py`, `opcua_server.py`, and `simulator_page.py`.
2. The OPC-UA server lifecycle is tightly coupled to the simulator loop — both start/stop together via `SimulatorAdapter.start()`/`stop()`.
3. The simulator UI has no indicator showing whether the OPC-UA server is running.
4. There are no controls to start/stop the OPC-UA server independently of the simulation loop.

## Solution

### 1. Fix Default Port (4841 → 4849)

Update hardcoded defaults in:
- `packages/smart_pid_core/src/smart_pid_core/config.py` — `simulator_port: int = 4849`
- `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/opcua_server.py` — `def __init__(self, port: int = 4849)`
- `packages/smart_pid_hmi/src/smart_pid_hmi/pages/simulator_page.py` — `self._opcua_port_spin.setValue(4849)`
- `tests/hmi/pages/test_simulator_page.py` — `assert spin.value() == 4849`
- `CLAUDE.md` — update documented default

### 2. Backend: Decouple OPC-UA Server from Simulator Loop

**`SimulatorAdapter`** gains independent OPC-UA lifecycle methods:

```python
def start_opcua(self) -> None:
    """Start only the OPC-UA server (without simulation loop)."""
    self._opcua_server.start()

def stop_opcua(self) -> None:
    """Stop only the OPC-UA server (without affecting simulation loop)."""
    self._opcua_server.stop()

@property
def opcua_running(self) -> bool:
    return self._opcua_server.is_running

@property
def opcua_port(self) -> int:
    return self._opcua_server.port

@property
def opcua_endpoint(self) -> str:
    return self._opcua_server.endpoint
```

**`start()` / `stop()`** change to control only the simulation loop:

- `start()`: starts the simulation thread only (no longer calls `self._opcua_server.start()`)
- `stop()`: stops the simulation thread only (no longer calls `self._opcua_server.stop()`)

**`main.py`** startup sequence:
1. `simulator_adapter.start_opcua()` — OPC-UA server starts first
2. `simulator_adapter.start()` — simulation loop starts after

**`main.py`** shutdown sequence:
1. `simulator_adapter.stop()` — simulation loop stops first
2. `simulator_adapter.stop_opcua()` — OPC-UA server stops after

**API router** (`simulator.py`) — new endpoints:

```
POST /simulator/opcua/start   → adapter.start_opcua(); returns CommandResponse
POST /simulator/opcua/stop    → adapter.stop_opcua(); returns CommandResponse
GET  /simulator/opcua/status  → {"running": bool, "port": int, "endpoint": str}
```

### 3. HMI: Status Indicator + Start/Stop Controls

In the existing `QGroupBox("OPC-UA Server")` on the simulator page:

**New widgets:**
- Status label: "Running" (green) / "Stopped" (red) — themed colors from `ThemeBase`
- "Start" button (`opcua_start_btn`) — enabled when OPC-UA is stopped
- "Stop" button (`opcua_stop_btn`) — enabled when OPC-UA is running

**New signals:**
- `opcua_start_requested = Signal()`
- `opcua_stop_requested = Signal()`

**New public method:**
- `set_opcua_running(running: bool)` — updates status label text/color and button enable states

### 4. Runtime Behavior

| Scenario | OPC-UA Server | Simulator Loop | Effect |
|---|---|---|---|
| Backend starts (`SPID_SIMULATOR_ENABLED=true`) | Starts automatically | Starts automatically | Full operation |
| User stops OPC-UA via UI | Stops | Continues running | Simulator calculates internally; `update_values` is no-op |
| User restarts OPC-UA via UI | Starts | Still running | Values resume being published |
| User stops simulator via UI | Unchanged | Stops | OPC-UA server stays up, no new values |
| User stops both | Stops | Stops | Everything idle |
| Backend shutdown | Stops (after loop) | Stops first | Graceful teardown |

### 5. DTO for OPC-UA Status

New Pydantic model in `smart_pid_domain/dtos/simulator.py`:

```python
class OPCUAServerStatus(BaseModel):
    running: bool
    port: int
    endpoint: str
```

## Files Modified

- `packages/smart_pid_core/src/smart_pid_core/config.py`
- `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/opcua_server.py`
- `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/simulator_adapter.py`
- `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/simulator.py`
- `packages/smart_pid_core/src/smart_pid_core/main.py`
- `packages/smart_pid_domain/src/smart_pid_domain/dtos/simulator.py`
- `packages/smart_pid_hmi/src/smart_pid_hmi/pages/simulator_page.py`
- `tests/hmi/pages/test_simulator_page.py`
- `CLAUDE.md`
