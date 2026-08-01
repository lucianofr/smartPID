# L4 Reliability Review — 2026-07-31 frozen diff

Scope: failure handling introduced/touched by the frozen diff — the two new
worker catch-alls, the `hasattr`-guarded simulator resync, and the wiring
site that relies on a pre-existing bare `except Exception`. Builds on L1
(peer review, no BLOCKING) without re-deriving its findings. Style,
layering, and OWASP are explicitly out of scope.

## Central verdict

**RELOCATED, not CLOSED.** The diff's own rationale (`stats_worker.py:192-196`,
`project_service.py:304-306`) is that a dead worker is indistinguishable from
a perfectly steady loop. Before the diff, a permanent fault killed the
thread outright — `is_alive()` went `False`, but nothing reads it. After the
diff, a permanent fault makes the thread retry forever, logging
`stats_worker_iteration_error`/`monitor_worker_iteration_error` once per
`scan_rate_s` — but nothing reads that either. In both states:

- `SystemStatusResponse` (`smart_pid_domain/dtos/system.py:7-10`) carries
  `status`/`uptime_s`/`active_controllers`/`bus_active`/`cpu_percent`/
  `memory_percent` — no per-worker or per-controller health field.
- `/system/status` (`adapters/inbound/api/routers/system.py:39-51`) computes
  `active_controllers=len(loop_manager._loops)` — dict membership, not
  thread liveness.
- `LoopManager.is_loop_running()` (`application/loop_manager.py:126-134`)
  exists and calls `.is_alive()` correctly, but **no router or dependency
  calls it** — confirmed by exhaustive grep across `adapters/inbound/api/`.
- `get_stats_workers()` (`adapters/inbound/api/dependencies.py:172-185`)
  hands the router whatever `StatsWorker` object is in `loop_manager`,
  unconditionally; `/controllers/{id}/stats` (`routers/stats.py:31-35`) calls
  `get_current_stats()` on it regardless of `.is_alive()` — a stuck-retrying
  worker and a dead one both serve the same frozen snapshot.
- `AlarmWorker._run` (`application/workers/alarm_worker.py:152-156`) is a
  pure `STATUS.*` consumer with a 100 ms poll and `continue` on timeout — no
  staleness counter, no "no data for N ticks" alarm.

So the only distinguishing signal between "healthy," "dead," and
"stuck-retrying-on-a-permanent-fault" is grepping logs for
`*_iteration_error` — exactly the state of affairs before this diff, just
with different log lines. The diff converts *transient* faults (the single
malformed frame in `test_stats_worker_survives_null_pv` /
`test_monitor_worker_survives_null_pv`) from permanent thread death into
genuine self-healing — that part is real and correct. It does not touch the
*permanent*-fault case at all.

## Findings

| # | Severity | File:Line | Operator-visible symptom | Fix |
|---|---|---|---|---|
| 1 | NON-BLOCKING | `stats_worker.py:150-151,191-202` | A **persistent** upstream fault (e.g. a stuck-bad-quality PV that never recovers) hits `error = self._last_sp - self._last_pv` every tick because `_drain_telemetry` (line 210-229) writes `self._last_pv = None` *before* the exception fires and nothing resets it in the `except` branch — the same `TypeError` re-fires every `scan_s` forever with no counter, no escalation, no circuit breaker. `MonitorWorker` doesn't have this specific self-poisoning (it's stateless per tick — see `_drain_latest`), but reproduces the same "retry forever on a permanent condition" outcome if the producer keeps emitting bad frames. Neither worker distinguishes "will heal on the next good frame" from "will never heal." | Add a `_consecutive_errors` counter reset on any successful tick; past a threshold (e.g. 10), stop retrying silently and instead publish a `STATUS`/`ALARM` with a `COMM_FAIL`-style quality flag, or raise to a point the daemon can flag the controller unhealthy in `/system/status`. Minimum viable version: log at `CRITICAL` (not just `exception`, which is `ERROR`) once the streak crosses the threshold, so it's `grep`-distinguishable from a one-off. |
| 2 | NON-BLOCKING | `monitor_worker.py:96-104`, `stats_worker.py:191-202` vs `pid_worker.py:552-565` | Comment claims "same guard... as `PIDWorker._loop`" — **verified true**: `PIDWorker._loop` has the identical `except zmq.ZMQError: break` / `except Exception: log; wait(scan_s)` shape with no retry budget either (matches ai_worker.py/db_worker.py/io_worker.py per its own comment, `pid_worker.py:553-555`). The claim is accurate, but it means the diff imports a known, unaddressed reliability gap into two more long-lived threads rather than avoiding it. Not a regression by this diff's own standard (it doesn't claim to fix the gap) but it triples the exposure surface for item 1's failure mode. | Track as one ticket across all 5 workers sharing this shape (`pid_worker.py`, `stats_worker.py`, `monitor_worker.py`, and the retry loops the comment cites in `ai_worker.py`/`db_worker.py`/`io_worker.py`) rather than fixing two of five in isolation. |
| 3 | **BLOCKING** | `monitor_worker.py:94-95`, `stats_worker.py:189-190` (new); `pid_worker.py:550-551` (pre-existing, mirrored) | `except zmq.ZMQError: break` never inspects `.errno`. `BusSubscriber.recv()` (`application/event_bus.py:54-56`) calls `self._socket.poll(timeout=...)`, and `zmq_poll()` is documented to return `EINTR` — a delivered-but-otherwise-harmless signal — as a `ZMQError`, not something the caller is meant to treat as fatal (`zmq_poll(3)`: "the operation was interrupted by delivery of a signal"). This code treats `EINTR`/`EAGAIN` identically to a genuinely dead socket: **silent** (`break` has no `logger` call before it, unlike the `except Exception` branch two lines below) permanent thread death. `SIGTERM`/`SIGINT` are wired via `asyncio.add_signal_handler` (`main.py:637-638`); any other signal delivered to the process while a worker thread is blocked in `poll()` — a profiler attaching (`py-spy`, exactly the tool an operator would reach for to diagnose a "stuck" worker per finding #1), a container runtime's pause/unpause, etc. — can hit this. Nothing restarts the thread: `loop_manager.py` has no supervisor loop, only explicit `start_loop`/`stop_loop` driven by API calls. | Check `exc.errno` before `break`: retry on `zmq.EAGAIN`/`errno.EINTR` (with the same paced wait as the `Exception` branch), and log even on the terminal path — `break` with zero log output is the single quietest failure mode in either worker; an operator has no log line to find. This applies to `pid_worker.py:550-551` identically, even though it predates this diff — the diff's own claim to "mirror" it makes it fair game, and fixing 2/3 of the mirrored trio without the third leaves the same daemon in a mixed state. |
| 4 | NON-BLOCKING | `project_service.py:314,316` | `hasattr(sim, "start")` / `hasattr(sim, "opcua_node_ids")` degrade to a **silent no-op** — no `else`, no log — if `SimulatorAdapter`'s API surface is ever renamed or refactored. That exact outcome (twin never restarted / client never rebound) is precisely the "healthy status, zero telemetry" bug this change set exists to fix (`project_service.py:304-306`), reintroduced by a future refactor with zero signal: no exception, no log line, no test failure (`_FakeTwin`/`_FakeClient` in `test_project_service.py` implement the full API, so a rename in production code wouldn't be caught by the existing fixtures either — this is L1 NB2's coverage gap manifesting as a live regression path, not just a test gap). | `domain/ports/inbound.py:9-12` already defines `TelemetrySource(Protocol)` with `start`/`stop`. Add a narrow `@runtime_checkable` `SimulatorPort(Protocol)` with `start`/`opcua_node_ids`, replace both `hasattr` checks with one `isinstance(sim, SimulatorPort)`, and log at `ERROR` (not silently `return`) on a mismatch — a refactor that breaks the contract should fail loud, not reintroduce the original bug byte-for-byte. |
| 5 | NON-BLOCKING | `project_service.py:126,149,181` calling `:294-320` | `_resync_simulator_link()` is the *last* `await` before the response is built in all three entry points, after `daemon_state.set_active_project(name)` and `_start_db_worker()` have already committed. If `bind_opcua_client` or `self._opcua_adapter.start()` (line 320) raises mid-way, the exception propagates **out of** `open_project`/`new_project`/`import_project` uncaught — `routers/project.py:116-120` (new) and `:132-136` (open) only catch `ValueError`/`FileExistsError`/`FileNotFoundError`, so a different exception type is *not* silently turned into a 200: it becomes an unhandled 500 (no generic `Exception` handler is registered anywhere — confirmed by grep). `import_project`'s route (`project.py:172-180`) does catch generic `Exception` → 400. **Correcting the assignment's premise: the client does not see a false 200.** What it does not see is a rollback: `daemon_state`'s active project, the reopened repo, and the restarted `DBWorker` are already pointed at the new project and are not unwound, while the twin/OPC-UA client binding is left however far the loop got — some controllers bound to the new project's nodes, others not, and the client's own registry (`OPCUAAdapter._controllers`, `outbound/opcua_adapter.py:52`) is append/overwrite-only with no path that removes an id, so stale bindings from the *previous* project are never purged by any code path, resync or otherwise. | Wrap `_resync_simulator_link()`'s body so a partial failure is explicit: log which controller ids bound successfully before re-raising, and give the caller (or an admin retry endpoint) a way to re-run just the resync without a full project switch. At minimum, document in the docstring that a mid-resync failure leaves the project switch "applied" with binding incomplete, since nothing here rolls it back. |
| 6 | **BLOCKING** (operational, not code) | `project_service.py:294-320` interacting with `simulator_adapter.py:200-206,323-333` (L1 NB1, cited not re-derived) | Concrete operator scenario: controller id 5 exists as "TIC-005 — Flow" in project A (fast dynamics, PV 0-100%) and also as "TIC-005 — Reactor Temp" in project B (slow dynamics, PV 0-500 °C). Operator opens project B. UI renders TIC-005 with **project B's** scale, limits, and label (all sourced from the freshly-reopened SQLite `Controladores` row — that part is correct, per L1's verified `reopen()`/`list_all()` ordering). The **physics** driving `pv.value` is still project A's `_ControllerSim` — `gain=1.2, tau1=3.0` from a flow loop — because `register_controller` (`simulator_adapter.py:323-333`) no-ops on an already-present id and `stop()` (`:200-206`) never clears `_controllers`. There is **zero** operator-visible signal of the mismatch: no log line (confirmed — neither the no-op branch of `register_controller` nor `stop()` logs anything), no alarm (alarms fire on PV limit crossings computed from the *actual*, if wrong, PV — they don't know the model is wrong), no UI indicator (the frontend has no "twin dynamics source" field to display). An operator tuning PID gains for a 500 °C reactor against a twin that is secretly still a 100 %-flow loop will derive gains that are wrong for the real process, silently, and may carry that tuning toward a real DCS deployment later — this is the platform's own documented use case (`CLAUDE.md`: twin used to tune before deploying to real hardware). This is the most dangerous item in the change set: everything else here is a monitoring/observability gap (you can't tell a thing is broken); this one produces **plausible, wrong data with no error path at all** — a silent correctness bug wearing a "working system" costume, in a diff whose entire purpose was closing exactly this class of gap. | (L1 already proposed the code fix — clear `_controllers` in `stop()` or reset `pv_min`/`pv_max`/model params on re-registration.) From the reliability angle: at minimum, log at `WARNING` when `register_controller` no-ops on an id that's already present with *different* `pv_min`/`pv_max` than requested — that single log line would have turned this from "no signal at all" into "grep would find it." |
| 7 | Verified non-issue | `monitor_worker.py:78,105-107`; `stats_worker.py:126-134` | `finally: sub.close(); pub.close()` sits on the **outer** `try` that wraps the `while` loop (monitor) / wraps the `_loop()` call (stats); the new inner `try/except` (zmq break, broad-Exception retry) is entirely inside that outer scope. Every exit path — normal `stop_event` completion, the new `break` on `ZMQError`, and the retry-then-continue path — funnels through the same `finally`. Confirmed by direct read, not inferred from convention. | None. |
| 8 | Rollback safety | n/a | — | See below. |

### NIT

- `stats_worker.py:191-198` catches `MemoryError` (a subclass of `Exception`) along with everything else, then calls `logger.exception(...)`, which formats and serializes a full traceback — itself an allocation — inside the handler for an out-of-memory condition. Under genuine memory pressure this can raise a *second*, uncaught exception from inside the `except` block (no handler wraps the handler), which is a different and worse failure than the one being guarded against. Low priority: `MemoryError` this deep in a single-controller worker thread (not the process-wide allocator) is an unlikely trigger, but it's a free correctness note given the assignment's explicit mention of the category.

## Rollback safety

**Safe to revert.** No DB schema migration, no on-disk `.spid` mutation, and
no persisted adapter state in this diff — `SimulatorAdapter`/`OPCUAAdapter`
registries are process-memory-only and rebuilt fresh on every daemon boot by
`AdapterFactory`. Reverting the code and restarting the daemon returns
cleanly to pre-diff behavior: no data corruption risk. The only consequence
is functional regression — projects opened after the revert go back to
silently-dead telemetry (D2) and workers that die outright on a single bad
frame (D3) — i.e., reverting un-fixes the bugs this diff fixed, it does not
introduce a new one.

## Findings table (reproduced)

| # | Severity | File:Line | Symptom (short) | Fix (short) |
|---|---|---|---|---|
| 1 | NON-BLOCKING | `stats_worker.py:150-151,191-202` | Persistent bad PV re-raises the same `TypeError` every tick forever, no retry budget | Consecutive-error counter → escalate past threshold |
| 2 | NON-BLOCKING | `monitor_worker.py:96-104`, `stats_worker.py:191-202` vs `pid_worker.py:552-565` | "Mirrors PIDWorker" claim verified true — imports its unbounded-retry gap into 2 more threads | One ticket across all 5 mirrored worker loops |
| 3 | BLOCKING | `monitor_worker.py:94-95`, `stats_worker.py:189-190`, `pid_worker.py:550-551` | `except zmq.ZMQError: break` treats EINTR/EAGAIN as fatal, zero log, thread vanishes, no supervisor restart | Check `errno`, retry transient codes, log even on terminal break |
| 4 | NON-BLOCKING | `project_service.py:314,316` | `hasattr` guard silently no-ops on API drift, reintroducing the exact bug this diff fixes | `@runtime_checkable` Protocol + `isinstance`, log on mismatch |
| 5 | NON-BLOCKING | `project_service.py:126,149,181` / `:294-320` | Mid-resync failure leaves project switch half-applied; caller gets an error (not a false 200) but no rollback exists | Document + partial-bind logging; retry-resync path |
| 6 | BLOCKING (operational) | `project_service.py:294-320` + `simulator_adapter.py:200-206,323-333` | Reused controller id across projects: twin silently keeps old project's process model/PV scale, zero log/alarm/UI signal | Clear/reset on stop (L1's fix) + WARNING log on mismatched re-registration |
| 7 | Verified non-issue | `monitor_worker.py:78,105-107`, `stats_worker.py:126-134` | `finally` close runs on every exit path incl. new `break`/retry | None |
| 8 | Rollback | n/a | Safe — no persisted state, revert only un-fixes the 5 bugs | None |

**Central verdict:** the two new catch-alls **relocate**, not close, the
"dead worker looks like a steady loop" gap — they convert *transient*
faults into genuine self-healing (real, verified win), but a *permanent*
fault still produces a frozen `/controllers/{id}/stats` snapshot
indistinguishable from health, because nothing in `/system/status`,
`get_stats_workers()`, or `AlarmWorker` reads worker liveness or a
consecutive-failure count.
