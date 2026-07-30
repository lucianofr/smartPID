# CO channel pinned at 0.0 in STATUS.{id} — adjudication

**VERDICT: DEFECT.** Two defects plus one config gap. None of the three hypotheses in the brief is the
root cause; the publishing worker is also not the one assumed.

## Evidence chain (measured live against pid=3898314, read-only)

1. **The twin's `co` node is live and Good.** External asyncua client on `opc.tcp://127.0.0.1:4849`:
   `CTRL_2/PID/CO` (`ns=2;i=27`) = **100.0**, StatusCode `0x0`. Same instant, `STATUS.2.co.value = 0.0`.
   `simulator_adapter.py::_tick` (518-533) writes **both** `"co": ctrl.last_co` and `"pid_cv"` every tick.
   → hypotheses (a) `pid_cv` vs `co` and (b) `co` never populated are **both false**.
2. **The publisher is `PIDWorker`, not `MonitorWorker`.** `loop_manager.py:71` selects MonitorWorker only
   when the *global* `SPID_EXECUTION_MODE == "monitor"`; per-controller `execution_mode=SUPERVISORY` is
   never consulted. Confirmed on the wire: live STATUS frames carry `kp/ti/td/integral_val` and lack
   `error`/`saturated` → PIDWorker's shape (`pid_worker.py:443-460`), not MonitorWorker's
   (`monitor_worker.py:123-138`). `ACTION.CTRL.{id}` existing at all is PIDWorker-only.
3. **Root cause — `pid_worker.py::_drain_telemetry`, lines 518-521:**
   ```python
   if not self._has_telemetry:
       self._last_co = _deserialize_ff_signal(data.get("co", 0.0))
   ```
   CO is seeded from the **first** frame only, then never refreshed. At daemon start the twin's `last_co`
   is 0.0, so the seed is 0.0. `self._mode` defaults to `MAN` (`pid_worker.py:112`) and **MAN is the only
   mode branch (363-371) that does not assign `_last_co`** → frozen at 0.0 forever. `bkcal_out`,
   `integral_val`, `delta_cv` are 0.0 for the same reason.
4. **It is an incomplete fix, not a design choice.** The SP block immediately above (487-491) already
   implements the correct ownership rule ("in SUPERVISORY the DCS owns SP, so each frame wins"). CO was
   left behind.

## Q1 — is `co == 0` in SUPERVISORY correct?

Defect, and the worst variety: a **fabricated GOOD-quality number**. In monitor/supervisor posture CO is
a *measurement* of the DCS controller's output, exactly as PV is a measurement of the process — it must be
read through with the source's quality propagated. What the operator must see:
the monitored controller's CO when SmartPID can substantiate it; an explicit **not-available** treatment
when it cannot (tag unmapped, link down). Never a number SmartPID invented. ISA-101 quality practice is
unambiguous here, and the UI already has the vocabulary: `AnalogBar.tsx:86` renders `sem dados` for a
null value and a hatched `(desatualizado)` for stale. A plausible **0 %** on the CO bar tells the operator
**the valve is shut** — worse than an explicit bad-quality marker, because it is actionable and wrong.

## Q3 — `mode` reads MAN: second defect, same family

`STATUS.mode` is `self._mode.value` (`pid_worker.py:454`) — PIDWorker's **own internal** mode, default MAN
(112), mutated only by REST `set_mode`/forced transitions. It reports *SmartPID's* mode, not the monitored
controller's. IOWorker does put the monitored mode in TELEMETRY (`io_worker.py:115,143`), but PIDWorker's
`_drain_telemetry` never reads `data["mode"]`. MonitorWorker does (`monitor_worker.py:128`) and has a test
(`tests/core/unit/test_monitor_worker_mode.py`). Compounding config gap: `read_actual_mode` needs
`mode_int_map`; the live project DB has `{}` for controllers 2-5 (only id 1 has `{"MAN":0,"AUTO":1}`), so
telemetry `mode` would be `"UNKNOWN"` for 2-5 even after P2. Twin node `CTRL_2/PID/Mode` reads `1` (AUTO).

## Q4 — patch proposal

**P1 — CO read-through.** `pid_worker.py::_drain_telemetry`, replace 518-521 with the SP block's predicate:
```python
if (self._controller.execution_mode is not ExecutionMode.DDC or not self._has_telemetry):
    self._last_co = _deserialize_ff_signal(data.get("co", 0.0))
```
`_deserialize_ff_signal` already preserves `severity`/`limit_bits` — no quality is invented.

**P2 — mode honesty.** Store `self._monitored_mode: str | None = data.get("mode")` in `_drain_telemetry`;
at `pid_worker.py:454` publish `mode = self._monitored_mode or "UNKNOWN"` when `execution_mode is not DDC`,
else `self._mode.value`. Add `"smartpid_mode": self._mode.value` as an **additive** key (msgpack dict
consumers are unaffected) so the HMI can still show SmartPID's own mode.

**P3 — do not fabricate GOOD (do not skip this one).** `opcua_adapter.py::_async_read_telemetry:295,300`:
`default_signal = FFSignal.good(0.0)` substitutes a **GOOD zero for every unmapped tag**. Use
`FFSignal.bad(0.0)` (already exists, `signal.py:81`) so an unmapped CO surfaces as BAD rather than 0 % GOOD.

**P4 — simulator config.** `main.py:334`: `mode_map = db_ctrl.tag_bindings.mode_int_map if db_ctrl else {}`
→ fall back to the twin's own convention `{"MAN": 0, "AUTO": 1}` when the DB map is empty; the same branch
already auto-assigns the sim's node ids, so pulling only the map from the DB is inconsistent.

**Front end (separate change).** `LoopCard.tsx:173` and `Faceplate.tsx:204` do `status?.co.value ?? null`
and **ignore `co.severity`**. They should render `null` (→ `sem dados`) whenever `severity !== 'GOOD'`.

### CO quality per execution mode

| Execution mode | CO source | `severity` | `limit_bits` |
|---|---|---|---|
| DDC, engine computed this scan | SmartPID's own output | `GOOD` | `HIGH/LOW_LIMITED` when clamped at `out_hi_lim`/`out_lo_lim` — currently discarded by `FFSignal.good(co_val)` at `pid_worker.py:360` |
| DDC, MAN (`set_output`) | operator-entered | `GOOD` | `NONE` |
| SUPERVISORY / global monitor | read-through of DCS output | propagate the OPC-UA StatusCode verbatim | propagate |
| CO tag unmapped, or link down | nothing substantiable | `BAD` (P3) | `NONE` |

## Regression risks

- **WILL FAIL:** `tests/core/integration/test_pid_worker_v2_features.py::TestOutputSelectionByMode::test_manual_mode_uses_set_output` (~565). `Controller.execution_mode` defaults to `SUPERVISORY` (`controller.py:141`) and the `_send_telemetry` helper defaults `co=50.0`, so read-through overwrites `set_output(42.0)`. Fix the test by building that controller with `execution_mode=ExecutionMode.DDC` — that is what it actually means to assert. MAN is the only branch that does not reassign `_last_co`, so **no other mode test is affected**.
- If P1 is extended to also *reject* `set_output` for SUPERVISORY controllers (correct, and consistent with `loop_manager.py:243` "Cannot set output in monitor mode"), `tests/core/integration/test_api_commands.py::TestOutputCommand::test_set_output_in_man_mode` also breaks. Recommend deferring that gate.
- `e2e/connection-loss.spec.ts` asserts **PV** `aria-valuetext` only (42/66/82) — unaffected by P1/P2/P4. It *would* be affected by the front-end severity change, since a BAD CO would then read `sem dados`.
- `Faceplate.test.tsx:59` (CO `64.0 %`) and `AnalogBar.test.tsx:38` (`sem dados`) are mock-driven → unaffected.
- `tests/core/unit/test_monitor_worker*.py` unaffected (MonitorWorker untouched).
- **Behavioural:** `Faceplate.tsx:119` — `if (!coTouched && data !== null) setCoDraft(data.co.value)`. Once CO goes live, the manual-CO draft field starts following the DCS output. Confirm that is intended.

## Secondary observation (not the root cause, separate ticket)

`CTRL_2` shows `PID_CV=0.0` and `PID_Enabled=false` on the address space while `/simulator/status` reports
`pid_enabled=True`. `_tick` (513-533) deliberately does not echo `pid_enabled`, and
`_sync_pid_config_to_opcua` fires only on config change — so `PID_Enabled` goes stale on the OPC-UA nodes.
Does not affect the CO channel.
