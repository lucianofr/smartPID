# Web HMI Fatia 2 — Commands + Loop Config (Enable PID Optimization)

**Date:** 2026-06-18
**Scope:** REST mechanism to enable/disable the per-loop PID online tuning optimizer, exposed through the commands router and consumed by the web HMI Fatia 2 controls.

---

## 1. Problem Statement

The web HMI spec (Fatia 2) references an "enable PID" control on each loop, but no
`commands` endpoint existed to back it. The only enable-style endpoint was the
simulator's `POST /simulator/{id}/pid/enable`, which controls the *simulated*
internal PID — not the real SmartPID online tuning optimizer that monitors an
external loop and writes tuning back to the DCS.

The AI worker already had a transient in-memory `_enabled` flag toggled via the
ZMQ `CMD.AI` channel (`POST /controllers/{id}/ai/start|stop`), but that state was
**not persisted**, **not reported** in controller config, and was lost on restart.

## 2. Gap Resolution — Implemented Endpoint

"Optimization enabled" maps to a new **persisted per-loop boolean** on the
`Controller` domain model: `optimization_enabled` (the platform's
`ENABLE_OPTIMIZER` concept from `docs/bloco_pid.md`). It is the master switch for
the online tuning optimizer (Fuzzy / RL) on that loop.

When **disabled**, SmartPID keeps monitoring and publishing telemetry/stats, but
the AI worker does **not** compute tuning or publish `ACTION.AI` — so no
tuning is written back to the controller. When **enabled**, the optimizer runs
as normal (still gated by mode = AUTO/CAS/RCAS and `ai_config.engine != NONE`).

### Endpoint

```
POST /commands/optimization
Body: { "controller_id": int, "enabled": bool }
Auth: require_operator   (same risk level as setpoint/mode/output and ai/start|stop)
```

Response (`CommandResponse`):

```json
{ "ok": true, "controller_id": 7, "enabled": false, "detail": "Optimization disabled" }
```

Errors:
- `401` — missing/invalid JWT
- `403` — role below operator
- `404` — unknown controller

### Behavior

1. Loads the controller, persists `optimization_enabled` via the repo
   (survives restart, surfaced by `GET` controller).
2. Updates the in-memory `LoopContext.controller` and calls
   `AIWorker.set_enabled(...)` for immediate effect on the running worker.
3. Publishes `CMD.AI.{id}` start/stop on the bus (reuses the existing command
   channel) so a thread draining commands also reacts.
4. Audits the action (`AuditAction.CONFIG_AI`) and broadcasts a system event.

The `AIWorker._enabled` flag is now **seeded from**
`controller.optimization_enabled` at construction (previously hardcoded `True`),
so a loop that boots with the optimizer disabled stays disabled.

## 3. Persistence

New column on `Controladores`: `optimization_enabled INTEGER NOT NULL DEFAULT 1`
(added to DDL and to `_apply_migrations` for existing databases). Mapped in
`_controller_to_params` and `_row_to_controller`.

## 4. Files Changed

- `packages/smart_pid_domain/src/smart_pid_domain/models/controller.py` — new `optimization_enabled: bool = True` field.
- `packages/smart_pid_domain/src/smart_pid_domain/dtos/commands.py` — `OptimizationCommand` DTO; `enabled` field on `CommandResponse`.
- `packages/smart_pid_core/src/smart_pid_core/application/workers/ai_worker.py` — seed `_enabled` from the flag; add `set_enabled()`.
- `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/commands.py` — `POST /commands/optimization`.
- `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py` — DDL column, migration, save/load mapping.

## 5. Tests

`tests/core/integration/test_api_optimization_toggle.py`:
- enable/disable persists to repo and reports state in the response
- live AI worker reflects the new state
- `401` without auth, `404` for unknown controller
- `AIWorker` seeds `_enabled` from `optimization_enabled`
