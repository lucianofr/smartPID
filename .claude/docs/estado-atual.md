# Estado Atual - FF Signals & BKCAL

**Data:** 2026-04-04
**Branch:** ff-signals-bkcal (worktree)

---

## Concluido

### Tasks 1-2: FFSignal, FFSignalStatus, enums (pre-existente)
- `FFSignal` and `FFSignalStatus` in `packages/smart_pid_domain/src/smart_pid_domain/models/signal.py`
- `LimitBits`, `SignalSeverity`, `InitSubStatus` enums in `enums.py`

### Task 3: Update TelemetryFrame, ControlAction, TagBindings (commit 81f9af8)
- **TelemetryFrame**: pv/sp/co changed from `float` to `FFSignal`, added `bkcal_in: FFSignal`, removed `status: SignalStatus`
- **ControlAction**: co changed from `float` to `FFSignal`, added `bkcal_out: FFSignal`
- **TagBindings**: added `node_id_bkcal_in` and `node_id_bkcal_out` fields
- Fixed 15 files (7 production + 8 test files)
- 553 tests pass, 9 pre-existing OPC-UA setup errors

## Arquivos Modificados (Task 3)

### Domain models
- `packages/smart_pid_domain/src/smart_pid_domain/models/telemetry.py`
- `packages/smart_pid_domain/src/smart_pid_domain/models/controller.py`

### Production code (adapters using .value)
- `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/historian.py`
- `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/opcua_adapter.py`
- `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/history.py`
- `packages/smart_pid_core/src/smart_pid_core/application/export_worker.py`
- `packages/smart_pid_core/src/smart_pid_core/application/workers/db_worker.py`

### Tests
- `tests/domain/test_models.py` (5 new tests + 2 fixed)
- `tests/domain/test_events.py` (2 fixed)
- `tests/core/integration/test_historian.py` (4 fixed)
- `tests/core/integration/test_api_history.py` (2 fixed)
- `tests/core/integration/test_db_worker.py` (2 fixed)
- `tests/core/integration/test_opcua_fullstack.py` (3 fixed)
- `tests/core/unit/test_export_worker.py` (2 fixed)
- `tests/core/unit/test_opcua_server.py` (1 fixed)

### Task 4: PID Engine — FFSignal-aware compute (commit 482a5b6)
- PID engine `compute()` now takes `pv: FFSignal, sp: FFSignal, bkcal_in: FFSignal`
- Directional anti-windup via BKCAL_IN limit bits
- Returns `bkcal_out: FFSignal` in PIDResult

### Task 5: PID Engine — IMAN tracking (commit 2393e7e)
- `compute_iman_tracking()` forces CV to match BKCAL_IN value

### Task 6: Mode Manager — Cascade handshake (commit e9daf58)
- `evaluate_cascade_handshake()` returns `CascadeAction`

### Task 7: CascadeHandshakeChanged event (commit 3352343)
- Audit event for cascade handshake transitions

### Task 8: PIDWorker — FFSignal integration (commit 0bf30c9)
- Replaced float fields with FFSignal: `_last_pv`, `_last_sp`, `_last_co`
- Added `_last_bkcal_in` and `_last_bkcal_out` FFSignal fields
- `_drain_telemetry` deserializes FFSignal (backward compat with plain floats)
- Cascade handshake evaluation before PID compute
- IMAN tracking mode support
- Serialized FFSignal in published messages (co, bkcal_out as dicts)
- 578 tests pass, 9 pre-existing OPC-UA setup errors

## Proximos Passos
- Task 9+ from the FF signals plan (check docs/spec_ff.md)
