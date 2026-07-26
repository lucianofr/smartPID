# Phase 6 — Alarms — Completion Report

**Status:** COMPLETE — all 6 tasks shipped, phase gate green.
**Plan:** `docs/superpowers/plans/2026-07-26-phase06-alarms.md`
**Worktree:** `.worktrees/web-frontend-rewrite`

## Commits

| SHA | Subject |
|---|---|
| `bce3157` | `feat(web): define four-severity alarm language` |
| `a291d69` | `feat(web): add active alarm panel and acknowledgement` |
| `e94dbe9` | `feat(web): add alarm history filters` |
| `d26c1f3` | `feat(web): add administrator alarm configuration` |
| `962f98b` | `feat(web): complete reduced-motion alarm feedback` |
| `de1e5f9` | `test(web): re-enable alarm lifecycle e2e` |
| `12a8c76` | `chore(web): rebaseline bundle budget for the phase-6 alarm workspace` |

A concurrent backend agent owns `tests/` and `packages/smart_pid_core/` and a
concurrent realtime agent owns `src/realtime/` on this branch; nothing under
those paths was staged by this phase.

## Gate results

| Gate | Result |
|---|---|
| `npm run test -- --run` | **398 passed / 57 files** (337 / 50 at phase 5; +48 alarm tests in 6 new files, remainder from the concurrent realtime agent) |
| `npm run typecheck` | exit 0 |
| `npm run lint` | exit 0 |
| `npm run test:e2e -- e2e/alarms.spec.ts` | **3 passed** |
| 8 previously-green E2E specs | **40 passed** — no regression |
| `npm run build:budget` | exit 0 after rebaseline — 174.9 KB gzip JS (budget 300) |

E2E commands run:

```
npx playwright test e2e/alarms.spec.ts
npx playwright test e2e/alarms.spec.ts e2e/faceplate.spec.ts \
  e2e/fatia2-commands.spec.ts e2e/fatia7-auth-negative.spec.ts \
  e2e/login-dashboard.spec.ts e2e/responsive.spec.ts \
  e2e/target-size.spec.ts e2e/themes.spec.ts e2e/user-role.spec.ts
npx playwright test          # full dir: 43 passed / 8 failed
```

The 8 full-suite failures are unchanged from phase 5 and belong to later
phases: `executive-dashboard`, `multitrend`, `simulator`, `fatia7-connection`
and `fatia7-projects` navigate to `/executive`, `/multitrend`, `/simulator`,
`/connection` and `/projects` — none of which exist in the frozen `appRoutes`
registry yet (only `/` and, as of this phase, `/alarms`).

## What shipped

### Task 1 — severity and alarm model

- `src/features/alarms/types.ts` — every alarm name is an alias of the
  generated OpenAPI schema re-exported through `api/types` (`AlarmSeverity` =
  `AlarmPriority`, `AlarmType`, `AlarmThreshold`, `AlarmConfigResponse`), so a
  backend enum change breaks the build instead of drifting.
- `src/features/alarms/severity.ts` — `severity()` + `SEVERITY_PRESENTATION`
  map: `CRITICAL/octagon/--alarm-crit`, `WARNING/triangle/--alarm-warn`,
  `ADVISORY/diamond/--alarm-adv`, `LOG/dot/--alarm-log`, plus `priorityRank`,
  `toSeverity` (unknown wire priority degrades to LOG, never dropped),
  `severityClass`, `severityVar`, `isUnackedStatus`.
- `src/index.css` — glyph clip-paths, `alarm-blink` (glyph opacity only,
  compositor-safe), unacked row stripe, and the reduced-motion re-encode
  (weight + underline).
- `features/dashboard/useAlarmCounts.ts` now imports and re-exports that single
  vocabulary instead of holding a second copy of `ALARM_SEVERITIES`/`toSeverity`.

### Task 2 — active panel and acknowledgement

- `useAlarms.ts` — `useActiveAlarms`, `useAckAlarm`, `useAckAllAlarms`,
  `useAlarms(filters)`. REST is the only source of alarm ROWS: `EVENT.ALARM`
  carries a `(controller, type)` transition and no row id (GAP-3b), so a frame
  triggers a **coalesced** (500 ms) invalidation of `queryKeys.alarmsActive`
  rather than one refetch per frame. Acks are never optimistic and settle into
  a refetch even on failure.
- `AlarmPanel.tsx` — `VirtualList` at `estimateSize=48`, rows deduped by id,
  sort by severity-then-recency or by time, filters for state and loop, an
  assertive `alarm-panel-live` region, and a per-row `ACK` gated on
  `useCan('alarms.ack')` (**both roles**) and on the row still being unacked.
- `pages/AlarmsPage.tsx` + one literal appended to the frozen `appRoutes`
  (`/alarms`, nav order 30, palette entry "Ir para Alarmes").

### Task 3 — history filters

- `AlarmHistory.tsx` — draft/applied filter split: nothing fires until
  `Aplicar filtros`, and a failed fetch keeps the chosen range. Sends the
  required `start`/`end` plus `limit=1000` and an optional `controller_id`.
- `/alarms/history` accepts **no** priority or type parameter, so those two
  narrow the fetched window client-side (`filterHistoryRows`) instead of being
  sent to the wire where they would silently do nothing.
- `placeholderData: (prev) => prev` keeps the previous window readable while a
  new one loads.

### Task 4 — administrator configuration

- `useAlarmConfig.ts` — the GET is `enabled`-gated by the caller's capability,
  so a user session never spends a request on a guaranteed 403. The PUT sends
  the **whole** six-row threshold array, because the backend replaces rather
  than merges.
- `AlarmConfigForm.tsx` — `aria-label="Configuração de alarmes"`, gated on
  `useCan('alarms.configure')` (**admin only**), per-type limit / deadband /
  priority / enabled controls. Ordering validation walks only the ENABLED
  analog limits, so a disabled HI leaves the chain instead of blocking its
  neighbours; deviation limits carry no ordering rule. FastAPI 422 `loc`
  indices are mapped back onto their field without resetting the draft.
- Reachable from an admin-only `Configuração` tab on `/alarms` with a loop
  selector.

### Task 5 — reduced motion and footer

- `useReducedMotion.ts` — `useSyncExternalStore` over
  `(prefers-reduced-motion: reduce)`, live.
- `AlarmFooterBar.tsx` — buckets now carry the severity GLYPH; unacked buckets
  get `alarm-blink` with motion on and a persistent, labelled
  `unacked-badge-{severity}` with motion off; `alarm-bar-live` announces
  unacknowledged criticals `aria-live="assertive"`; the last-alarm line now
  falls back to the newest REST row before any live frame arrives. The footer
  reuses `useAckAllAlarms()` instead of its own inline mutation.
- Contracts preserved: `count-{severity}`, `unacked-{severity}`,
  `unacked-badge-{severity}`, `alarm-count-chip`, `alarm-bar-live`, `ACK ALL`.
  `ACK ALL` still survives the sub-768 collapse (§6.9 320 px floor).

### Task 6 — E2E

`e2e/alarms.spec.ts` now layers its stateful alarm double over the shared
`e2e/helpers/harness.ts`, which supplies `GET /api/auth/me` (without it
`useCan` is deny-by-default and the ACK button never renders) and the full §7
resync set (StrictMode always resyncs on first load), and emits monotonically
increasing `seq`. Two tests were added beside the original lifecycle test:
severity shape + history + admin config reachability, and footer `ACK ALL`.

## Concerns / follow-ups

1. **Bundle rebaselined.** Measured at `c10ba9e` (pre-phase-6): 161.8 KB gzip.
   Phase 6 adds **+13.1 KB** (alarm workspace plus the Radix `Tabs`/`Switch`
   primitives, which no shipped page pulled in before). 174.9 / 300 KB still
   leaves headroom, but route-level code splitting is the obvious lever when a
   later phase presses the budget — it needs a `Suspense` boundary in `App.tsx`
   and so was left out of this phase.
2. **Bulk ack lives in exactly one place.** The panel toolbar does not repeat
   `ACK ALL`; the §6.9 footer is mounted on `/alarms` and owns it. `AlarmPanel`
   rendered without a footer therefore has no bulk-ack control.
3. **Cross-feature imports.** `features/alarms` reads
   `features/dashboard/useControllers` (canonical roster) and
   `features/dashboard/useAlarmCounts` re-exports `features/alarms/severity`.
   No cycle, but the roster hook arguably belongs at app level.
4. **`useAlarmCounts.ts` was edited** although the wave contract only listed
   `AlarmFooterBar*` — it was the only way to avoid a second definition of
   `AlarmSeverity`. Collision-free: no other agent held dashboard files.
5. **E2E cold start.** `alarms.spec.ts` sorts first and pays the Vite dev
   server's on-demand compile; each navigation is gated on the `Ativos` tab
   with a 60 s readiness wait so a slow first transform is not read as a
   missing panel. No assertion was weakened.
