# Kp / Ki-Ti / Kd-Td OPC-UA tag mapping + faceplate source guarantee

**Date:** 2026-08-06
**Status:** Done

## Request

1. Add fields to the loop configuration screen so the operator can declare the
   OPC-UA variables that Kp, Ki/Ti and Kd/Td are read from.
2. The faceplate must *always* render PV, SP, CO, MODE, Kp, Ki/Ti and Kd/Td from
   OPC-UA via the loop's configured tag mapping — never straight from the
   simulator.

## What was already in place (verified, not assumed)

The backend chain for tuning tags was complete end to end before this change:

| Stage | Evidence |
|---|---|
| Domain | `models/controller.py:94-96` `TagBindings.node_id_kp/ti/td` |
| DTO | `dtos/controllers.py:79-81`; generated TS `openapi.ts:2742,2767,2772` |
| Schema | `sqlite_repo.py:72-74` DDL + `:291-293` idempotent migration |
| Round-trip | `sqlite_repo.py:642-644` write, `:775-777` read |
| Registration | `opcua_adapter.py:221-223,247-249` |
| Runtime read | `opcua_adapter.py:505-541` `read_pid_params`, called every `_PARAMS_READ_INTERVAL_S = 1.0` s by `io_worker.py:206-212,249-266` |
| Into telemetry | `io_worker.py:186` `**self._cached_params.get(cid, {})` |
| Into STATUS | `pid_worker.py:575-577`, `monitor_worker.py:147-149` |
| Rendered | `Faceplate.tsx:136-140` from `useRealtime<StatusData>` |

So `node_id_kp/ti/td` were **live-read config, not dead fields**. Two real gaps
remained.

## Gap 1 — the UI exposed only 7 of 12 bindings

`NODE_ID_FIELDS` (`TagPicker.tsx:25-65`) and the `Draft['bindings']` `Pick`
(`LoopConfigDialog.tsx:285-294`) listed `node_id_ti` but omitted `node_id_kp`
and `node_id_td`. Values already stored survived saves (the handler spreads
`...controller.tag_bindings` first) but were invisible and uneditable.

Fix — the render is already data-driven off `NODE_ID_FIELDS`
(`LoopConfigDialog.tsx:564`), so three small edits covered it:

- `TagPicker.tsx` — added `node_id_kp` and `node_id_td` entries; relabelled to
  `NodeID Kp` / `NodeID Ki/Ti` / `NodeID Kd/Td`. The Ki/Ti wording is load
  bearing: `integral_type` is `TIME_TI | GAIN_KI` and the dialog itself warns it
  "decides the SIGN of every integral" (`LoopConfigDialog.tsx:483`).
- `LoopConfigDialog.tsx` — added both keys to the `Pick` union and to `toDraft`.

Picker, tooltip, save payload and both-mode visibility came for free.

## Gap 2 — the twin silently overrode the operator's mapping

`bind_opcua_client` (`simulator_adapter.py:86-121`) registered **every**
controller against the twin's minted node ids whenever the simulator was
enabled, at four call sites (`main.py:394`, `project_service.py:347`,
`controllers.py:623`, `simulator.py:153`). Its own docstring stated the premise —
"a controller's `tag_bindings` are empty" — but never checked it. For a loop
imported from a real project the premise is false, so the configured mapping was
discarded at every boot and project open.

This was reproduced live, not inferred:

- FIC-001's mapping points at `ns=2;i=5/7/14` (twin folder `CTRL_0`).
- With `node_id_kp` deliberately blanked in the DB, the faceplate still showed
  `KP 1.00` — it was reading the twin's `CTRL_n/PID/Kp`, not the empty mapping.
- Across a daemon restart the twin re-minted folders in a different order:
  `CTRL_0` hosted a different controller before and after. The mapping was only
  accidentally correct, and shifted between boots.

Fix — the precedence rule now lives in one place, `bind_opcua_client`, which
takes an optional `bindings: Mapping[int, TagBindings]`: a controller whose
`node_id_pv` is set is registered from its own mapping (new shared
`register_from_tag_bindings`) and skipped for twin binding; only unmapped loops
fall through to the twin. All four call sites updated; `main.py` also registers
mapped controllers the twin never minted a folder for.
`controllers._reregister_opcua` was collapsed onto the shared helper (it was a
verbatim duplicate).

## Verification

Live, against the real daemon + twin (not mocks):

| Check | Result |
|---|---|
| Three fields render, both SUPERVISORY and DDC | pass |
| Pre-existing DB values surfaced (`ns=2;i=10/11/12`) | pass — previously invisible |
| Edit → save → reload → persisted | `ns=9;i=777` / `ns=9;i=888` round-tripped |
| `node_id_kp` empty → faceplate | `KP —` (was `1.00` before the fix) |
| `node_id_kp` → node holding `7.77` | `KP 7.77`, live, no restart |
| `node_id_ti/td` still mapped throughout | `TI 10.00`, `TD 0.00` |

Suites: frontend 962/962 (97 files), `tsc -b` clean, backend 1741/1741, ruff clean.

Regression coverage added — `tests/core/unit/test_simulator_adapter.py`
`TestBindOpcuaClientPrecedence` (4 cases: mapped wins, unmapped falls through,
twin-only loop still binds, blank Kp stays blank rather than borrowing the
twin's). All four fail against the previous behaviour.

## Not changed

- Faceplate labels stay `KP`/`TI`/`TD`; the request concerned the data source.
- Dashboard/faceplate components were already simulator-free — `Faceplate.tsx`,
  `LoopCard.tsx`, `useLoopStatuses.ts`, `AiPanel.tsx`, `CardControls.tsx` have
  zero simulator references. Simulator-sourced values remain confined to
  `/simulator` (`PIDSettings.tsx`, `ClosedLoopDiagram.tsx`,
  `SimulatorControlPanel.tsx`).
- `node_id_integral` / `node_id_bkcal_in` / `node_id_bkcal_out` remain unexposed
  in the UI — out of scope for this request.
