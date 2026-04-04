# Phase 3b+4b — OPC-UA Full-Stack (Server + Client)

**Date:** 2026-04-03
**Status:** Approved
**Dependencies:** Phase 4 (Simulator), Phase 1 (PID Engine, Ports)

---

## Overview

Merge Phases 3b (OPC-UA I/O Worker) and 4b (asyncua.Server) into a single deliverable.
The SimulatorAdapter gains an embedded asyncua.Server exposing process variables as OPC-UA
nodes. A new OPCUAAdapter (client) implements TelemetrySource + ControlWriter, enabling
closed-loop PID control over OPC-UA — testable locally without real hardware.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Backend Daemon                                      │
│                                                      │
│  ┌──────────────┐    asyncua     ┌────────────────┐ │
│  │ OPCUAAdapter │◄──(tcp:4840)──►│ asyncua.Server │ │
│  │ (client)     │                │ (embedded)     │ │
│  │ TelemetrySrc │                │ in Simulator   │ │
│  │ ControlWriter│                │ Adapter        │ │
│  └──────┬───────┘                └───────┬────────┘ │
│         │                                │          │
│         ▼                                ▼          │
│  ┌─────────────┐                ┌────────────────┐  │
│  │ PID Worker  │                │ ProcessModel   │  │
│  │ (velocity)  │                │ (FOPTD/SOPTD)  │  │
│  └─────────────┘                └────────────────┘  │
└─────────────────────────────────────────────────────┘
```

Closed-loop path:
1. PID Worker computes CO → OPCUAAdapter.write_output()
2. OPCUAAdapter writes CO node on asyncua.Server
3. SimulatorAdapter reads CO via server callback → ProcessModel.step()
4. SimulatorAdapter updates PV node on asyncua.Server
5. OPCUAAdapter.read_telemetry() reads PV node → TelemetryFrame → PID Worker

## OPC-UA Namespace

Each registered controller gets a folder under a common root:

```
Objects/
  SmartPID/
    Controllers/
      {controller_tag}/          # e.g. "FIC-101"
        PV    (Float, readable)
        SP    (Float, read/write)
        CO    (Float, read/write)
        Mode  (String, readable)
        Status (String, readable)  # RUNNING, STOPPED, FAULT
```

- **Namespace URI:** `urn:smartpid:sim` (simulator mode) or `urn:smartpid:process` (real mode)
- Nodes created dynamically when a controller is registered via SimulatorAdapter
- SP and CO are writable — allows external SCADA/DCS to write setpoint

## OPCUAAdapter (Client)

New file: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/opcua_adapter.py`

Implements both `TelemetrySource` and `ControlWriter` protocols.

### Connection State Machine

```
DISCONNECTED ──connect()──► CONNECTING ──success──► CONNECTED
     ▲                                                  │
     │                          timeout/error           │
     │                              │                   │
     └──────── max retries ◄── RECONNECTING ◄──────────┘
                                    │                disconnect/error
                                    └── backoff ──► retry connect
```

- Exponential backoff: 1s, 2s, 4s, 8s... capped at `SPID_OPCUA_RETRY_MAX` (default 30s)
- On disconnect → state = RECONNECTING, PID Worker pauses CO writes (holds last value)
- On reconnect → bumpless transfer: resume with last CO, no output bump

### Core Interface

```python
class OPCUAAdapter:
    state: ConnectionState  # DISCONNECTED, CONNECTING, CONNECTED, RECONNECTING

    async def connect(self, endpoint: str) -> None
    async def disconnect(self) -> None
    async def read_telemetry(self, controller_id: int) -> TelemetryFrame
    async def write_output(self, controller_id: int, co: float) -> None
    async def write_parameter(self, controller_id: int, param: str, value: float) -> None
    async def browse_tags(self) -> list[OPCUANode]  # for TagBrowser port
```

### Node Cache

- `Dict[int, Dict[str, ua.NodeId]]` — maps controller_id → {PV, SP, CO, Mode, Status} node IDs
- Populated on first read per controller (lazy)
- Invalidated on reconnect (nodes may have changed)

## SimulatorAdapter Changes

Current: uses `SimpleQueue` for direct in-process communication.
New: exposes process variables via embedded asyncua.Server.

### New Methods

- `_start_opcua_server()` — starts asyncua.Server in a dedicated asyncio event loop thread
- `_stop_opcua_server()` — graceful shutdown
- `_create_controller_nodes(tag: str)` — creates OPC-UA folder + variable nodes for a controller
- `_remove_controller_nodes(tag: str)` — removes nodes when controller is unregistered
- `_update_nodes()` — after each ProcessModel.step(), writes new PV/Mode/Status to OPC-UA nodes
- `_on_co_written(node, value)` — datachange callback when OPCUAAdapter writes CO

### Removed

- `SimpleQueue` communication path — OPC-UA replaces it entirely
- Direct `read_telemetry()` / `write_output()` methods (now goes through OPC-UA)

### Kept (via REST)

- `set_preset()`, `set_parameters()` — simulator configuration
- `inject_step()`, `inject_noise()`, `clear_disturbance()` — disturbance injection
- `get_controller_status()` — simulator status

## AdapterFactory Changes

```python
class AdapterFactory:
    def __init__(self, settings: CoreSettings):
        if settings.simulator_enabled:
            self._simulator = SimulatorAdapter(settings)  # starts asyncua.Server on :4840
            self._opcua = OPCUAAdapter()
            # connect to local server
            self._opcua_endpoint = f"opc.tcp://localhost:{settings.simulator_port}"
        else:
            self._simulator = None
            self._opcua = OPCUAAdapter()
            self._opcua_endpoint = settings.opcua_endpoint  # external DCS/PLC

    @property
    def telemetry_source(self) -> TelemetrySource:
        return self._opcua

    @property
    def control_writer(self) -> ControlWriter:
        return self._opcua

    @property
    def simulator_adapter(self) -> SimulatorAdapter | None:
        return self._simulator
```

Key change: `telemetry_source` and `control_writer` always return the OPCUAAdapter,
regardless of simulator mode. The SimulatorAdapter is only the process plant — it never
implements TelemetrySource/ControlWriter directly anymore.

## Configuration

New pydantic-settings fields (prefix `SPID_`):

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `SPID_SIMULATOR_PORT` | int | 4840 | asyncua.Server port (simulator mode) |
| `SPID_OPCUA_ENDPOINT` | str | `opc.tcp://localhost:4840` | OPC-UA server endpoint (production) |
| `SPID_OPCUA_RETRY_MAX` | float | 30.0 | Max reconnect backoff in seconds |
| `SPID_OPCUA_SCAN_RATE_MS` | int | 1000 | Default telemetry read interval |

## Dependencies

- `asyncua` — OPC-UA client + server (already in pyproject.toml as optional)
- No new external dependencies required

## Testing Strategy

### Unit Tests
- OPCUAAdapter: connect/disconnect, read_telemetry, write_output with mock asyncua.Server
- Node cache: population, invalidation on reconnect
- Connection state machine transitions

### Integration Tests
- Closed-loop: SimulatorAdapter (with asyncua.Server) + OPCUAAdapter + PID Worker
- Verify PV tracks SP after step change
- Verify CO writes propagate through OPC-UA to ProcessModel

### Resilience Tests
- Simulate server disconnect → verify RECONNECTING state + backoff
- Simulate reconnect → verify bumpless transfer (no CO bump)
- Verify PID Worker pauses writes during RECONNECTING

## Files to Create/Modify

### New Files
- `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/opcua_adapter.py`
- `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/opcua_server.py` (asyncua.Server wrapper)
- `tests/test_opcua_adapter.py`
- `tests/test_opcua_integration.py`

### Modified Files
- `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/simulator_adapter.py` — add OPC-UA server
- `packages/smart_pid_core/src/smart_pid_core/adapters/factory.py` — new wiring
- `packages/smart_pid_core/src/smart_pid_core/config.py` — new settings
- `packages/smart_pid_core/src/smart_pid_core/main.py` — startup/shutdown wiring
- `packages/smart_pid_core/src/smart_pid_core/domain/ports/inbound.py` — TagBrowser protocol (if not exists)
