# Simulator registration lifecycle — root cause and fix

Branch `fix/simulator-registration-and-schema` (no commits made). `smart_pid_web` untouched;
`sqlite_repo.py` / `sim_persistence.py` / `db_engine.py` left to the Database specialist (their
in-flight edits were present in the tree and all suites stayed green).

## Root cause

`SimulatorAdapter` keeps one `_ControllerSim` per controller in `self._controllers`, populated
*only* by `register_controller`. That was called from exactly two places, both whole-project bulk
loads: `main.py:298-309` (daemon startup) and `project_service.py:256-263` (project open/import).

`POST /controllers` persisted the row and stopped there. So a controller created while the daemon
was running existed in `Controladores` but not in `self._controllers`, and every `/simulator/*`
route addressing it hit `self._controllers[controller_id]` on an absent key. Restarting the daemon
"fixed" it because startup re-ran the bulk load.

Three secondary defects fell out of the same investigation:

1. **`DELETE /controllers/{id}` never deregistered** (the mirror bug). No `unregister_controller`
   existed at all, so a deleted loop kept being integrated by `_tick` and kept answering.
2. **Three routes leaked the bare `KeyError` as a 500** — `POST /preset`, `PUT /parameters`,
   `POST /disturbance`. The other nine each had their own `except KeyError -> 404` copy; these
   forgot it. Confirmed pre-fix: `KeyError: 999` from `simulator_adapter.py:267` (`set_preset`),
   `:287` (`set_parameters`), `:301` (`inject_step`).
3. **`POST /simulator/{id}/co` had the opposite failure — a silent success.** `write_output` looks
   its controller up with `dict.get`, so pre-fix an unknown id returned
   `200 {"ok":true,"controller_id":999,"detail":"CO=42.0"}`.

## Seams chosen, and why

**Registration/deregistration: the `controllers.py` router**, via one private helper
`_sync_simulator_registration(request, controller | None, controller_id)`.

The project has **no** application-layer service for controller lifecycle. `LoopManager` owns
*loops*, not adapter registration, and `POST /controllers` does not call it either; giving it a
handle on an *inbound* adapter would also invert the dependency direction. The idiom for exactly
this concern already lives in this file: `_reregister_opcua(request, controller)`
(`controllers.py:474`) reaches `request.app.state.opcua_adapter` after a `tag_bindings` update, and
`update_controller` reaches `request.app.state.loop_manager` to restart the AI worker. The new
helper mirrors that shape, so the diff adds no wiring to `main.py`, `create_app`,
`dependencies.py` or `conftest.py`. A `ControllerService` for two calls would be speculative
generality.

**Honest 404: the router boundary, not the adapter.** Two facts forced this:

- `KeyError` is the codebase-wide "not registered" contract — `SQLiteRepository.get`/`delete` and
  `OPCUAAdapter` (4 sites) all use it, and `tests/core/unit/test_simulator_adapter.py:391` asserts
  `pytest.raises(KeyError)` on `get_config_dict`.
- `sim_persistence.persist_sim_config` guards `get_config_dict` with `except KeyError` and is owned
  by another agent this round, so the adapter cannot change that contract anyway.

A domain `ControllerNotFoundError` was rejected as *inaccurate*: a controller can exist in the
project DB and merely be absent from the simulator. The message states the simulator-specific fact:
`Controller 999 is not registered in the simulator`.

Rather than adding three more copies of the missing `try/except`, all thirteen controller-scoped
routes now share one guard, `_sim_controller(adapter, controller_id)` — a context manager that
pre-checks membership (needed for the `dict.get` no-op case) and translates any `KeyError` escaping
the block (closing the check-to-use window). The 404 is structural instead of a per-route
obligation.

## Files changed

| File | Change |
|---|---|
| `adapters/inbound/simulator_adapter.py` | +`has_controller()`, +`unregister_controller()` (also discards the id from `_dirty_cids` so the flusher cannot write a config row back for a deleted controller) |
| `adapters/inbound/api/routers/simulator.py` | +`_not_registered()`, +`_sim_controller()` guard; applied to all 13 routes, removing 9 duplicated `except KeyError` blocks |
| `adapters/inbound/api/routers/controllers.py` | +`_sync_simulator_registration()`; called from `create_controller` and `delete_controller` (both gained `request: Request`) |
| `tests/core/integration/test_simulator_registration_lifecycle.py` | **new** — 18 tests |
| `tests/core/unit/test_simulator_adapter.py` | +6 tests |

Simulator-disabled safety: the helper returns early when `app.state.simulator_adapter is None`, and
never raises — the controller row is already committed when it runs, so an adapter hiccup is logged
via `logger.exception` rather than turned into a 5xx for a create that succeeded.

## Tests added

`test_simulator_registration_lifecycle.py` deliberately does **not** use the shared `sim_api_deps`
fixture: that one calls `register_controller(1)` up front, and the first API-created controller is
assigned id 1 — every assertion would pass vacuously. It builds an empty `SimulatorAdapter`.

- create-then-`/preset` returns 200 without a restart; `/pid/enable` + `/pid/params` reachable;
  `pv_scale` is forwarded to `pv_min`/`pv_max` (auto-excitation span depends on it)
- delete drops the entry and `/preset` then 404s
- 11 parametrised routes x unknown id -> 404 with the id in the message
- simulator disabled: create + delete still 201/204, and `/simulator/*` reports
  `"Simulator not enabled"` from the dependency, not the new guard
- adapter unit tests: `has_controller`, `unregister_controller`, unknown-id no-op, `_dirty_cids`
  discard, tick loop stops visiting the controller, siblings unaffected

**RED proof.** Against a pristine `git archive HEAD` tree (PYTHONPATH-shadowed) -> **16 failed,
2 passed** (the 2 being the simulator-disabled cases, correctly already working). After -> 18 passed.

## Verification

```
$ ruff check <5 changed files>                    All checks passed!
$ mypy --follow-imports=silent <3 source files>   25 before, 25 after, 0 new
$ pytest tests/core/unit tests/domain             935 passed
$ pytest tests/core/integration                   532 passed, 1 deselected
$ pytest tests/core/api                            34 passed
$ openapi(): no Request parameter leaked into the schema
```

The deselected test is `test_api_simulator.py::TestOPCUAEndpoints::test_opcua_start_stop`: it binds
`0.0.0.0:4849`, which the live daemon (`pid=3898314`, also on `127.0.0.1:8000`) holds. It fails
identically on pristine HEAD — pre-existing and environmental.

## Out of scope — handoffs

1. **`repo.delete()` does not cascade `Configuracao_Simulador`** — Database specialist's area.
2. **`POST /controllers` does not start a control loop** and `DELETE` does not stop one; neither
   updates `IOWorker.controller_ids`, `AlarmWorker` metadata, or OPC-UA registration. Same class of
   bug, wider blast radius — own task.
3. **`OPCUAServer` has no node-removal API**, so `unregister_controller` leaves the `CTRL_{id}`
   folder in the address space until restart. Inert, but a real leak.

---

# Follow-up: CO read-through and mode reporting

Second defect in the same subsystem, diagnosed read-only by a Process Control Engineer; I own the
patch. Its four premises were spot-checked before touching anything and all four hold:

| Premise | Check |
|---|---|
| PIDWorker publishes, not MonitorWorker | `loop_manager.py:71` branches on the *global* `execution_mode`; per-controller `SUPERVISORY` never reaches worker selection |
| CO seeded once, never refreshed | `pid_worker.py:518-521` `if not self._has_telemetry:` |
| MAN is the only branch that never reassigns `_last_co` | the seven branches at `:308-419`; MAN (`:363`) only calls `bumpless_transfer` |
| SP already implements the rule CO is missing | `:487-491`, whose comment even opens "SP ownership mirrors CO below" — the mirror it names did not exist |

## P1 — CO read-through (`pid_worker.py::_drain_telemetry`)

In SUPERVISORY the DCS runs the loop and the IO worker never writes CO (the ACTION.CTRL comment at
`:430`), so telemetry CO is a *measurement* of the DCS controller's output — the same kind of fact
as PV measuring the process. Every frame wins and the source's quality propagates. DDC is
unchanged: SmartPID computes CO there and owns it, so telemetry may only seed it. Implemented as a
literal mirror of the SP block, same condition shape.

`integral_val` was collateral, not a separate bug: MAN's `bumpless_transfer` seeds `state.cv` from
`_last_co`, so a frozen 0.0 CO froze the integral too. It comes back for free — covered by a test.

**`bkcal_out` and `delta_cv` are *not* fixed, deliberately.** Neither is a measurement: MAN simply
never computes them (`_last_bkcal_out` keeps its `FFSignal.good(0.0)` init, `delta_cv` is re-zeroed
each tick), and telemetry does not carry a `bkcal_out` to read through. Making BKCAL_OUT track the
block output in MAN is a Foundation-Fieldbus semantics change, not a wiring fix — separate task.

## P2 — no more fabricated GOOD zeros (`opcua_adapter.py:295`)

One `default_signal` feeds pv/sp/co/bkcal_in (`:298-301`), so the single substitution
`FFSignal.good(0.0, now)` → `FFSignal.bad(0.0, now)` covers all four. An unmapped tag is the
absence of a measurement, not a measurement of zero.

## P3 — `mode` reports the monitored controller (`pid_worker.py:454`)

Added `self._dcs_mode`, captured in `_drain_telemetry` from the `mode` IOWorker already publishes
(`io_worker.py:143`), following the MonitorWorker precedent (`monitor_worker.py:128`). Published in
SUPERVISORY only; DDC keeps reporting SmartPID's own mode.

One deviation from MonitorWorker: it defaults to `"UNKNOWN"`, PIDWorker falls back to its internal
mode when the producer supplies no `mode` key at all. MonitorWorker has no internal mode to fall
back on; PIDWorker does, and absence of the field is not evidence the DCS is in MAN. Covered by a
test.

## P4 — simulator supplies its own `mode_int_map` (`main.py`)

The simulator branch already overrides every node id with the twin's auto-assigned ones, then
pulled `mode_int_map` from the DB — which is `{}` for exactly the controllers the simulator
auto-registered, so `read_actual_mode` returned None and every frame said `"UNKNOWN"` regardless of
P3. Now sourced from a new `SIMULATOR_MODE_INT_MAP = {"MAN": 0, "AUTO": 1}` in
`simulator_adapter.py`, beside the `_ControllerSim.pid_mode` encoding it documents (the
`/simulator/{id}/pid/mode` route uses the same `1 if AUTO else 0`).

**Chose not to persist a DB default.** It would duplicate a constant the simulator owns, drift if
the twin's encoding changed, present DB `tag_bindings` as authoritative in simulator mode when the
node ids beside them are not, and — worst — mutate the user's `.spid` file as a side effect of
setting `SPID_SIMULATOR_ENABLED=true`. The map belongs to whoever owns the address space.

## Files changed

`pid_worker.py` (+43/-3: `_dcs_mode` field, CO ownership block, mode publish),
`opcua_adapter.py` (+5/-3: bad default), `simulator_adapter.py` (+`SIMULATOR_MODE_INT_MAP`),
`main.py` (+import, simulator branch mode map),
`tests/core/integration/test_pid_worker_supervisory_readthrough.py` (**new**, 7 tests),
`tests/core/integration/test_pid_worker_v2_features.py` (+7: the one predicted regression).

## Tests and RED proof

New file covers CO-follows-every-frame, integral_val recovery, quality propagation, DDC seed-only,
SUPERVISORY mode read-through, fallback when no mode is supplied, and DDC mode ownership.

Against pristine `git archive HEAD` (PYTHONPATH-shadowed): **3 failed, 4 passed** →
`test_co_follows_every_frame_not_just_the_first`, `test_integral_val_tracks_co`, and
`test_status_reports_the_monitored_controllers_mode` (`AssertionError: assert 'MAN' == 'AUTO'`).
After the fix: **7 passed**.

Honest note on the 4 that already passed: they are guards, not bug proofs. In particular
`test_bad_quality_propagates_from_the_source` passes on HEAD because the *first* frame's seed does
carry quality — it guards the read-through against laundering quality later.

**Exactly one existing test needed editing**, as predicted:
`test_pid_worker_v2_features.py::TestOutputSelectionByMode::test_manual_mode_uses_set_output`, now
constructed with `execution_mode=ExecutionMode.DDC`. That is what it means to assert — "manual mode
uses set_output" is a claim about CO *ownership*, and only DDC gives SmartPID ownership. No second
test regressed, which is the signal the P1 shape is right.

## Verification

```
$ ruff check <6 changed files>                              All checks passed!
$ mypy --follow-imports=silent <4 source files>             61 before, 62 after
      the 2 deltas are at main.py:275,278 — inside another agent's rewritten
      _retention_cleanup, outside my hunks (line 20 and 405-416). 0 mine.
$ pytest tests/core/unit                                    773 passed
$ pytest <readthrough + v2_features + pid_worker
          + opcua_adapter + monitor_worker + main_wiring>    61 passed
$ python -c "SIMULATOR_MODE_INT_MAP decode"                 0->MAN, 1->AUTO OK
```

Full suites, run to completion:

```
$ pytest tests/core/integration          544 passed, 1 deselected in 145.29s
$ pytest tests/domain tests/core/api      196 passed
```

One environmental caveat: `test_api_simulator.py::TestOPCUAEndpoints::test_opcua_start_stop` stays
deselected — the live daemon holds `0.0.0.0:4849`. It fails identically on pristine HEAD.

Correction worth recording. Two earlier full-integration runs appeared to stall (at ~44% and ~59%,
a *different* test each time) and I was about to report that as a pre-existing environmental hang.
It was neither pre-existing nor a hang: it was contention from my own overlapping background pytest
runs plus the live daemon. Run alone, the suite completes in 145s, 544 passed. Pristine HEAD
completes in 122s, 514 passed; the +30 is my 25 new tests plus other agents' in-flight additions.
The moving stall point was the tell — a real hang would have been deterministic.

## Out of scope — noted, not bundled

- **Rejecting `set_output` for SUPERVISORY controllers.** It probably should be rejected
  (`loop_manager.py:243` already forbids it in global monitor mode) and after P1 the call is a
  silent no-op — the next frame overwrites it. Breaks
  `test_api_commands.py::TestOutputCommand::test_set_output_in_man_mode`; own change.
- **`loop_manager.py:71` ignores per-controller `execution_mode`.** The root reason a SUPERVISORY
  controller gets a PIDWorker that computes a CO nobody writes. Fixing worker selection is a much
  larger change than this defect needed.
- **SUPERVISORY + non-MAN modes still publish SmartPID's computed CO**, because the branches at
  `:308-419` reassign `_last_co` after the drain. The SP block has the identical characteristic
  (`:293/:300/:305` reassign `_last_sp`), so this is a property of the accepted precedent I was
  asked to mirror, not something P1 introduced. Worth its own decision.
