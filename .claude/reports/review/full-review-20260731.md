# Full Review Summary: change set reviewed pre-commit (13 files, +512/−197)

**Review Date:** 2026-07-31
**Reviewed By:** Claude Code Review System (`/review-full`)
**Target:** working-tree diff on `main`, frozen at `.claude/reports/review/_reviewed-diff-20260731.patch`.
Reviewed while uncommitted; subsequently landed as `33c8407`
(source + tests) plus a separate doc-only commit for `CLAUDE.md`. The frozen
patch is kept because it is the exact byte image all four levels reviewed and
spans both commits.
**Scope note:** no path/flag was supplied to the command; target defaulted to the pending
uncommitted change set, which is what was actually awaiting review. All four levels
triggered on the automatic rules (709 lines changed; API + error-handler surface; worker
and lifecycle code).

## Levels Completed

- [x] L1: Peer Review — `python-reviewer`
- [x] L2: Architecture Review — `architect` (>200 lines, new module seam, cross-cutting lifecycle)
- [x] L3: Security Review — `security-reviewer` (user input handling, global exception handler, API routes)
- [x] L4: Reliability Review — `silent-failure-hunter` (worker error handling, retries, startup sequencing)

## What the change set does

Five fixes: (1) extract `bind_opcua_client()` to dedupe OPC-UA client binding across three
wiring sites; (2) `ProjectService._resync_simulator_link()` restarts the twin + client after
a project switch; (3) `_load_opcua_endpoint()` early-return in simulator mode; (4) a
`RequestValidationError` handler so NaN/inf commands return 422 instead of 500; (5) catch-all
`except Exception` + paced retry in `MonitorWorker` and `StatsWorker`.

---

## Blocking Issues (Must Fix)

| ID | Level | Issue | Location | Severity |
|----|-------|-------|----------|----------|
| **B1** | L2 + L4 (found by L1) | **Twin state leaks across project switches.** `SimulatorAdapter.stop()` is a *thread* verb that never clears `_controllers`, and `register_controller` is insert-if-absent, never an upsert. The twin's controller set is therefore the union of every project opened since boot, with first-writer-wins field values. Controller ids start at 1 in every `.spid`, so **any** two-project workflow reuses ids by default: open project B and the twin silently simulates project A's process model on project A's PV scale. No log, no alarm, no UI signal. Fix 2 is precisely what makes this reachable — it re-arms a twin whose state no component owns across the project boundary. | `adapters/inbound/simulator_adapter.py:200-206,323-333` + `application/project_service.py:290-295` | BLOCKING |
| **B2** | L3 | **`FiniteFloat` is absent from `ControllerCreate`/`ControllerUpdate`** — fix 4 hardened only `commands.py`, leaving the sibling DTOs for this router's own admin routes unguarded. Reproduced against the running app: `NaN` on `scan_rate_s` → unhandled **500** `sqlite3.IntegrityError` (no 422 at all); `Infinity` on `pid_params.gain` → **201 Created** with `inf` genuinely persisted, while every subsequent read reports `"gain": null` because Pydantic v2's `ser_json_inf_nan` swallows it at serialization. The operator sees neither an error nor the real value while the stored config carries `inf`. | `smart_pid_domain/dtos/controllers.py:107,124-158,167-208` | BLOCKING |
| **B3** | L4 | **`except zmq.ZMQError: break` never inspects `errno`.** `EINTR` is documented `zmq_poll` behaviour (e.g. a profiler attaching to diagnose a stuck worker) and is treated identically to a dead socket: the thread exits with **zero log output** and no supervisor to restart it. The diff mirrors this pre-existing shape into two more long-lived threads, tripling exposure. | `application/workers/monitor_worker.py:94-95`, `application/workers/stats_worker.py:189-190` (mirroring `pid_worker.py:550-551`) | BLOCKING |

B1 was independently confirmed three ways: L1 found it by code trace, L2 ruled it a missing
lifecycle contract, L4 ruled it the most dangerous item in the change set. The coordinator
verified the two mechanics directly (`stop()` at `:200-206` touches only the thread;
`register_controller` at `:327` is guarded by `if controller_id not in self._controllers`).
B2 was spot-checked by the coordinator: **zero** `FiniteFloat` occurrences in that file
against ~20 bare `float` fields.

---

## Non-Blocking Issues (Should Fix)

| Level | Issue | Location | Priority |
|-------|-------|----------|----------|
| L2 | Gratuitous inbound-adapter import. `ProjectService` already receives the simulator at `:50`/`:59` and uses it duck-typed everywhere else; the module import exists only because the helper is a free function. Making `bind_opcua_client` a `SimulatorAdapter` method removes the diff's only new layering inversion as a side effect — one fix closes both A2 and A3. | `application/project_service.py:11`; `adapters/inbound/simulator_adapter.py:87-136` | HIGH |
| L2 | The "in simulator mode the client points at the twin" invariant is enforced in **one of four** places. `PUT /opcua/endpoint` and `POST /opcua/connect` are unguarded, and `_resync_simulator_link` calls `start()` **without** re-asserting the endpoint — so after an admin points the client at a real DCS, every later project switch re-arms it on the wrong endpoint while binding twin node ids. | `application/project_service.py:326-331` vs `adapters/inbound/api/routers/opcua.py:85-86,96-99` | HIGH |
| L3 | `jsonable_encoder(exc.errors())` raises uncaught `RecursionError` on a ~990-deep wrong-typed body (~12 KB), before `_json_renderable` ever runs. No body-size or nesting-depth middleware exists. **Pre-existing FastAPI behaviour**, not introduced here; bounded to one authenticated-admin request receiving a 500 instead of a 422. | `adapters/inbound/api/error_handlers.py:19,48` | MEDIUM |
| L4 | No retry budget or circuit breaker. A persistent bad PV re-raises the same `TypeError` every tick forever (`self._last_pv=None` is never reset), logging on each pass with no escalation. | `application/workers/stats_worker.py:150-151,191-202` | MEDIUM |
| L4 | The "mirrors `PIDWorker._loop`" comment is **true** — which means the fix imports that loop's pre-existing unbounded-retry gap into two more threads. Should be tracked as one ticket across all five worker loops rather than fixed in two of five. | `monitor_worker.py:96-104`, `stats_worker.py:191-202`, `pid_worker.py:552-565` | MEDIUM |
| L4 | `hasattr()` guards degrade to a silent no-op on future API drift, reintroducing the exact "healthy status, zero telemetry" bug this change set exists to fix. No log, and no test would catch it because the fakes implement the full API. (L1 confirmed the *style* matches the class; this is the reliability consequence, not a style note.) | `application/project_service.py:314,316` | MEDIUM |
| L4 | Project switch is non-atomic: `_resync_simulator_link` runs last, after daemon state and the DB worker are committed. A mid-loop failure leaves the switch half-applied with no rollback, and `OPCUAAdapter._controllers` is append-only so stale prior-project bindings are never purged. (L4 corrected the brief's premise: the router's narrow `except` yields a 500/400, **not** a false 200.) | `application/project_service.py:126,149,181` → `:294-320` | MEDIUM |
| L2 | Ordering inverted on open/import: `_start_control_loops()` starts workers while the twin is stopped and the client unbound; `_resync_simulator_link()` runs after. Window is two statements wide and the new guards absorb it, so not a live defect — but free to fix. | `application/project_service.py:138-151` | LOW |
| L2 | Do **not** widen `TelemetrySource` with `register_controller` — its eleven `node_id_*`/`mode_int_map` kwargs would drag OPC-UA addressing into the dependency-free domain package, a worse violation than the `type: ignore` it removes. Declare a one-method `OpcuaTagBindable(Protocol)` in the adapter layer instead. | `domain/ports/inbound.py:9-12` | LOW |
| L2 | `register_controller` names two unrelated contracts (twin: `(id, pv_min, pv_max)`; OPC-UA: `(id, node_id_*, mode_int_map)`) in the two modules this diff exists to bridge. Already load-bearing: `project_service.py:262` probes the name via `hasattr`, which would pass for either adapter. | `adapters/inbound/simulator_adapter.py:323` vs `adapters/outbound/opcua_adapter.py:212` | LOW |
| L1 | Fix 3 ships with **zero** test coverage; reverting it fails no test, because `_resync_simulator_link`'s unconditional `start()` masks the `stop()`/`set_endpoint()` a reverted guard would trigger. | `application/project_service.py:326-337` | HIGH |
| L1 | Fix 1's call sites 1 (`main.py:438`, boot) and 2 (`controllers.py:592`, `POST /controllers`) have no covering test; only site 3 is exercised. A signature regression in the shared helper would be caught at one of three sites. | `main.py:438-443`, `adapters/inbound/api/routers/controllers.py:592` | MEDIUM |
| L1 | `_free_port()` is a fifth copy of an existing 3-line helper. | `tests/conftest.py:32-42` | LOW |

## NITs

| Level | Issue | Location |
|-------|-------|----------|
| L1 | `%s` vs `%d` for `controller_id` in the two sibling guards added by the same diff. Repo majority is `%d`. | `monitor_worker.py:102` vs `stats_worker.py:199` |
| L2 | `sim.start()` mints a phantom default controller `id=0` when `_controllers` is empty, so `new_project` integrates a loop that exists in no project — invisible except as CPU. | `application/project_service.py:315`; `adapters/inbound/simulator_adapter.py:190-193` |
| L2 | The extraction turned an O(n) boot loop into O(n²): `opcua_node_ids(cid)` returns `dict(...)` — a full copy of the whole map — once per controller. Immeasurable at realistic counts. | `adapters/inbound/simulator_adapter.py:100` → `:184` |
| L3 | The handler comment's premise is wrong for the installed FastAPI (0.135.3): the stock handler does **not** echo `exc.body` (zero grep matches), so this is not a security-improving reduction in echo versus the real default. | `error_handlers.py:41-49` |

## Verified non-issues (litigated and closed — do not re-raise)

- `_resync_simulator_link` queries the **new** project: it runs after `repo.reopen()`, which mutates in place (`sqlite_repo.py:843-856`).
- `OPCUAAdapter.start()` is idempotent (`opcua_adapter.py:67-69`).
- `bind_opcua_client`'s `nodes.get("pv","")` is guarded by `if not nodes: continue`; a partial dict never occurs (`opcua_server.py:199-258` populates atomically).
- `monitor_worker`'s `tick_start` move into the inner `try` loses no accounting.
- `finally: sub.close(); pub.close()` runs on every exit path including the new `break` (read directly, not inferred).
- The bare `except Exception` in `controllers.py:595-598` is **pre-existing**, not introduced by this diff.
- `exc.errors()` surfaces only standard pydantic-core vocabulary — no internal class names, paths, or `ctx` leaks.
- `RequestValidationError` / `WebSocketRequestValidationError` / `ResponseValidationError` are MRO siblings, so the handler cannot catch the other two.
- Frontend reads only `loc`/`msg`/`type`/`detail` (`smart_pid_web/src/api/client.ts:69,86-93`) — no regression.
- No new third-party dependency; both new imports are first-party FastAPI.
- **The 422 handler is an AUTHENTICATED surface.** FastAPI's `solve_dependencies()` resolves all `Depends()` — including `require_admin`/`require_user` — before `request_body_to_args()` validates the body. Confirmed by probe: unauthenticated + malformed body returns 401, never 422.

Three coordinator preliminary findings were **refuted** by evidence: the bare `except` is
pre-existing; the `hasattr` guards match established class style; and the recursion crash
originates in `jsonable_encoder` (pre-existing FastAPI), not in this diff's `_json_renderable`.
The layering concern was **downgraded** — `application/workers/db_worker.py:16-17` already
imports `adapters.outbound.*`, so the rule is broken repo-wide; only the *inbound* direction
is new here.

## Recommendations

1. **Fix B1 before merge, in two halves** (both required). Make `register_controller` an upsert that always rebuilds `_ControllerSim`, and — critically — guard the inner `self._opcua_server.register_controller(cid)` on `cid not in controller_node_ids`, **not** on `_controllers`: `_async_register_controller` does an unconditional `add_folder(ns, f"CTRL_{id}")`, so re-registering an id would otherwise mint a duplicate OPC-UA folder. Then add `SimulatorAdapter.reset_to(ids)` (reusing the `unregister_controller:345` body) and call it from `_load_simulator_configs()` after `list_all()`, before the registration loop. Do **not** make `stop()` destructive — `POST /simulator/stop` is the operator's pause button, and that would trade a state-leak bug for a state-loss bug.
2. **Fix B2 before merge.** Alias `commands.py`'s `FiniteFloat`/`FiniteTime` into `dtos/controllers.py` and apply to every float field on `ControllerCreate` and `ControllerUpdate`. Fix 4 is otherwise only half-delivered.
3. **Fix B3 before merge.** Check `exc.errno` and retry `EINTR`/`EAGAIN` with the same paced wait as the `Exception` branch; log on the terminal `break` path so a dying worker leaves evidence.
4. **Close the layering inversion for free** by making `bind_opcua_client` a `SimulatorAdapter` method — one signature move deletes `project_service.py:11` and needs no ports program.
5. **Add the two missing tests** (fix 3's early-return; the two untested `bind_opcua_client` call sites) — both are cheap and both currently allow a silent revert.
6. **Decide the worker-liveness question separately.** L4's central verdict is that the catch-alls **relocate** rather than close the "dead worker looks like a steady loop" gap: a worker that survives but retries forever is equally indistinguishable from a healthy one, because nothing (`/system/status`, `LoopManager.is_loop_running`, `get_stats_workers`, `AlarmWorker`) reads worker liveness or a consecutive-failure count. That is a design gap larger than this diff and should not block it.

## Tech Debt (Deferred)

Appended to `.claude/reports/_tech-debt.md` as TD-016 … TD-021: worker-liveness
observability (High), unbounded retry across 5 worker loops (Medium), the
unowned simulator-endpoint invariant (High), the `register_controller` name
collision (Medium), systemic `application/`→`adapters/` imports (Medium), and
the missing request nesting-depth limit (Low).

## Verdict

- [ ] **APPROVED**
- [x] **CHANGES REQUESTED** — three blocking issues (B1, B2, B3).

The five fixes are individually correct and well-reasoned, and the `bind_opcua_client`
extraction is genuinely sound (three real duplicate sites, one rule, no fourth site missed —
verified by grep). But two of them are incomplete in ways that produce *silently wrong data*
rather than errors: fix 2 re-arms a twin that still models the previous project (B1), and
fix 4 leaves the sibling create/update DTOs unguarded so `inf` reaches the database and reads
back as `null` (B2). Both are inside the use case each fix exists to serve.

**Rollback safety:** safe to revert. No DB migration, no on-disk `.spid` mutation, no
persisted adapter state — reverting only un-fixes the five bugs.

## Report Links

- L1: `.claude/reports/review/L1-peer-20260731.md`
- L2: `.claude/reports/review/L2-arch-20260731.md`
- L3: `.claude/reports/security/L3-security-20260731.md`
- L4: `.claude/reports/sre/L4-reliability-20260731.md`
- Reviewed diff (frozen): `.claude/reports/review/_reviewed-diff-20260731.patch`
