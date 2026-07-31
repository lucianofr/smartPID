# TEST_E2E_loops_faceplate_setpoint — Setpoint write via the main Loops faceplate

Validation for the fix: writing a setpoint through the main faceplate on the
`Loops` page (`/`) was silently discarded for the demo loop `FIC-101`. This
runbook follows the same contract as `TEST_E2E.md`: a real Chrome browser
driven over CDP (`xd://browser`) against the real FastAPI daemon, real
WebSocket, real SQLite project, and the real internal simulator — no
`page.route` mocking. Playwright's mocked suite in `packages/smart_pid_web/e2e/`
does not exercise this path and is not a substitute for this runbook.

## Root cause

`FIC-101` (`controller_id=1`) was persisted with `execution_mode=SUPERVISORY`
(the model default — `packages/smart_pid_domain/src/smart_pid_domain/models/controller.py:141`).
`SUPERVISORY` means "an external DCS/PLC owns SP and CO; SmartPID only
observes" (see the tooltip in `LoopConfigDialog.tsx`'s "Modo de execução"
field). Under that mode `PIDWorker._drain_telemetry`
(`packages/smart_pid_core/src/smart_pid_core/application/workers/pid_worker.py:505-509`)
re-reads `sp` from every incoming `TELEMETRY.{id}` frame — by design, so a
real external controller's operator-set SP is reflected faithfully. But
`FIC-101`'s telemetry source is the *internal Simulator* (`ns=2;i=6`), which
nothing ever writes SP to on `POST /commands/setpoint` (that call only
reaches OPC-UA when the **daemon-level** `execution_mode` is `monitor`, which
it is not here — see `commands.py:63-69`). Net effect: `set_setpoint` always
returns `200 OK` and momentarily updates the live PID state, then the next
scan cycle (`scan_rate_s=1`) overwrites it back to the simulator's stale SP
register — silently, with no error surfaced to the operator. This is
correct, tested behavior for a genuinely SUPERVISORY loop
(`tests/core/integration/test_pid_worker_supervisory_readthrough.py`); it was
simply the wrong mode for a loop that SmartPID's own `PIDWorker` is actively
computing CO for (AUTO mode, editable Kp/Ti/Td, live FUZZY optimizer) — i.e.
a DDC loop.

A second, independent gap: config edits to `execution_mode` (also `pid_params`,
`sp_hi_lim`, etc.) are persisted via `PUT /controllers/{id}` but never
propagated to an already-running `PIDWorker` — that object holds its own
`Controller` snapshot from whenever `LoopManager.start_loop()` first ran
(`pid_worker.py:108`, never reassigned) and only `ai_config` /
`process_speed` / `tss_s` / `scan_rate_s` changes hot-reload (the AI worker
only, via `LoopManager.restart_ai_worker`). A config change to
`execution_mode` requires the daemon (or at least that loop) to restart
before it takes effect. No HTTP route exposes a per-loop restart today;
`LoopManager.start_loop`/`stop_loop` are only called from daemon boot
(`main.py`) and project open/import (`project_service.py`). This is a real,
separate limitation worth a follow-up if config hot-reload is ever needed for
a live-tuning workflow, but it is out of scope for this fix (no code
changed; the daemon was restarted once, manually, to apply the corrected
data).

## Fix applied

1. `PUT /api/controllers/1 {"execution_mode": "DDC"}` — corrects `FIC-101` to
   the mode it is actually operated in.
2. Restarted `smart-pid-core-backend` so `LoopManager.start_loop()` re-reads
   the controller fresh from SQLite and the new `PIDWorker` seeds SP once
   from telemetry, then owns it (DDC seed-only rule).

No frontend or backend source was changed — the write path
(`Faceplate.tsx` → `CardControls.tsx` → `useSetpointMutation` →
`POST /api/commands/setpoint` → `LoopManager.set_setpoint` →
`PIDWorker.set_sp`) was already correct; only the loop's own configuration
was wrong.

## Environment

Same daemon used throughout this validation (already running, not started
fresh for this doc):

```
uv run python -m smart_pid_core     # SPID_API_PORT=8537, execution_mode=execute
```

```
cd packages/smart_pid_web && npm run preview   # http://localhost:5173, proxies /api and /ws to :8537
```

Login: `admin` / `admin`. Active project at validation time:
`autotest_project_created_by_agent_2026-07-30_1` (1 loop, `FIC-101`).

## Procedures

### LOOPS-SP-000 — Reproduce the bug (pre-fix)

- **Steps:** Login as admin; land on `Loops` (`/`); the main faceplate for
  `FIC-101` shows `SP 70.0`. Type `50` into the faceplate's `Setpoint` field;
  click `Set setpoint`.
- **Observed (pre-fix):** `POST /api/commands/setpoint {controller_id:1,
  value:50}` returns `200 OK`. After 1.5 s the faceplate's `SP` readout (and
  the `Malhas PID` card's SP) still reads `70.0` — the write was silently
  discarded. `FIC-101.execution_mode` was `SUPERVISORY` at this point
  (`GET /api/controllers` confirmed).
- **Evidence:** `test-evidence/LOOPS-SP-000-bug-repro-write-discarded.png`
- **Result:** [x] BUG CONFIRMED

### LOOPS-SP-001 — Setpoint write holds and the controller pursues it (post-fix)

- **Steps:** With `FIC-101.execution_mode=DDC` (applied, daemon restarted,
  loop switched to `AUTO`), from a stable state (`SP=80`, `PV≈77.7`,
  oscillation already damped by the FUZZY optimizer — see
  `LOOPS-SP-001-before-write.png`), click into the faceplate's `Setpoint`
  field (already holding operator-typed `70` from the draft), click
  `Set setpoint`.
- **Expected:** `SP` updates to `70.0` immediately and never reverts; `CO`
  changes direction immediately (the controller starts pursuing); `PV` moves
  toward `70` over subsequent scans.
- **Observed:** `SP` read `70` on every one of 49 polls taken every 5 s from
  t=0 to t=245 s after the click (never reverted). `CO` dropped from `41.7`
  to `31.0` within 800 ms of the click. `PV` trajectory (meter
  `aria-valuenow`, `aside[aria-label="Faceplate FIC-101"]`):

  | t (s) | PV | CO | t (s) | PV | CO |
  |---:|---:|---:|---:|---:|---:|
  | 0 (click) | 79.94 | 31.04 | 90 | 74.01 | 34.05 |
  | 5 | 61.38 | 40.03 | 120 | 66.09 | 36.57 |
  | 30 | 70.88 | 42.02 | 150 | 73.42 | 31.87 |
  | 40 | 77.69 | 26.98 | 180 | 66.88 | 38.64 |
  | 60 | 68.01 | 31.41 | 220 | 72.64 | 33.01 |
  | 80 | 70.01 | 39.90 | 245 | 69.08 | 34.09 |

  The loop settles into an underdamped oscillation immediately after the
  step (swing amplitude ≈ ±9 from SP at t=30-60s) that visibly narrows over
  the FUZZY optimizer's damping cycles (`Ti: 10.00 → 12.75` logged at
  `09:28:06`, oscillation-triggered) to ≈ ±3 from SP by t=220-245s, i.e. PV
  is converged on SP=70 well inside the 5-minute budget.
- **Evidence:** `test-evidence/LOOPS-SP-002-immediately-after-click.png` (t=0),
  `test-evidence/LOOPS-SP-003-converged-after-4min.png` (t≈245s — trend chart
  shows the SP step 80→70 and PV settling into a tight band around it).
- **Result:** [x] PASS [ ] FAIL

### LOOPS-SP-002 — Setpoint holds through repeated writes (regression guard for the SUPERVISORY bug)

- **Steps:** Covered incidentally by LOOPS-SP-001 — SP was polled 49 times
  over 245 s of live telemetry (the loop's `scan_rate_s=1`, so ~245 PID
  cycles elapsed) with zero reversion.
- **Expected:** If `execution_mode` regressed to `SUPERVISORY` (or the daemon
  reverted to a stale in-memory `PIDWorker`), `SP` would revert to the
  simulator's stale field value (`80`, observed pre-write) within one scan
  cycle (~1 s).
- **Observed:** No reversion across 245 cycles.
- **Result:** [x] PASS [ ] FAIL

## Notes for future loops

Any new loop meant to be controlled by SmartPID's own `PIDWorker` (i.e.
Kp/Ti/Td live in the "PID Tuning" section, AUTO/MAN offered, AI optimizer
active) must be created or edited with `execution_mode=DDC` in the loop
config dialog. The default (`SUPERVISORY`) is correct for a loop that
mirrors a real external DCS/PLC and is a deliberate, tested product default
— it is not itself a bug. `POST /commands/setpoint|mode|output` accepting a
write for a `SUPERVISORY` loop and having it not stick is expected: the
tooltip already says "SmartPID só monitora" for that mode.
