# Phase 8 — Simulator — Completion Report

**Status:** COMPLETE — all 5 tasks shipped, phase gate green.
**Plan:** `docs/superpowers/plans/2026-07-26-phase08-simulator.md`
**Worktree:** `.worktrees/web-frontend-rewrite`

## Commits

| SHA | Subject |
|---|---|
| `c65705d` | `feat(web): define simulator API and permission` |
| `5fe7a49` | `feat(web): add simulator status and role state` |
| `abd964a` | `feat(web): add live simulator twin page` |
| `d6e5d42` | `test(web): re-enable simulator e2e` |

**Misattributed files.** The phase-7 agent working the same branch staged
`packages/smart_pid_web/src` wholesale twice, sweeping in-progress phase-8 files
into its own commits. Task 3's components therefore land in `3fe94f2`
("add multitrend history windows" — `useSimulatorMutations.ts`,
`StartStopControl`, `PresetSelector`, `DynamicsSliders`, `DisturbanceControls`,
`AutoToggles`, `TwinOutputModeControl`) and `77091de` ("restore loop statistics
panel" — `SimulatorControlPanel.tsx` + its test). Content is intact and no
history was rewritten; the peer scoped its adds after being told. No backend
path (`tests/`, `packages/smart_pid_core/`) was staged by this phase, and
nothing under `src/realtime/`, `src/features/alarms/`, `src/components/` or the
phase-7 feature dirs was modified.

## Gate results

| Gate | Result |
|---|---|
| `npm run test -- --run` | **490 passed / 72 files** (398 / 57 at phase 6; +42 simulator tests in 7 new files, remainder phase 7) |
| `npm run typecheck` | exit 0 |
| `npm run lint` | exit 0 |
| `npx playwright test e2e/simulator.spec.ts` | **3 passed** |
| 43 previously-green E2E | **43 passed** — no regression |
| Previously-green 43 + simulator | **46 passed** |
| `npm run build:budget` | exit 0 — **183.1 KB gzip JS** (budget 300), CSS 7.5 (budget 50), fonts 109.6 (budget 160) |

E2E commands run:

```
npx playwright test e2e/simulator.spec.ts
npx playwright test e2e/login-dashboard.spec.ts e2e/faceplate.spec.ts \
  e2e/responsive.spec.ts e2e/target-size.spec.ts e2e/themes.spec.ts \
  e2e/fatia7-auth-negative.spec.ts e2e/fatia2-commands.spec.ts \
  e2e/user-role.spec.ts e2e/alarms.spec.ts          # 43 passed
npx playwright test                                  # full dir: 46 passed / 5 failed
```

The 5 full-suite failures belong to other phases and are unchanged by this
work: `executive-dashboard` (2) and `fatia7-connection` / `fatia7-projects` (1
each) navigate to routes that are still not in `appRoutes`, and one
`multitrend` export test is phase-7 work in flight.

**Bundle NOT rebaselined.** 183.1 KB is +8.2 KB over the committed 174.9 KB
baseline, inside the 10 KB regression tolerance, and that delta covers phase 7's
multitrend/stats/export as well as phase 8. `bundle-baseline.json` is left
untouched deliberately — the phase-7 agent should rebaseline once its own
surface is final, with the growth attributed in the commit message.

## What shipped

### Task 1 — API and capability

- `src/auth/useCan.ts` — 13th capability `simulator.configure`, admin-only. The
  `user` set is unchanged: driving twin SP/mode/CO stays `loop.operate`, while
  reshaping the model is configuration. The pinned §9 list in `useCan.test.tsx`
  was extended to match.
- `src/features/simulator/types.ts` — every DTO aliased off
  `api/generated/openapi`, plus `PRESET_NAMES`, `PID_MODE_AUTO` (the wire
  reports twin mode as an int) and the backend's `AutoSP` / `AutoDisturbance`
  schema defaults.
- `src/features/simulator/api.ts` — `simulatorApi` over the real routes.
  `status` delegates to `endpoints.simulatorStatus` so this feature and the §7
  resync set cannot drift onto two URLs. `__tests__/api.test.ts` pins verb, path
  and body for all eleven calls, including the two shapes that fail silently:
  `/simulator/parameters` is a **PUT** (a POST is a 405 swallowed by a mutation
  handler), and `/simulator/{id}/co` reuses `SimulatorPIDSPRequest` — the CO
  percentage travels in the `sp` field.

### Task 2 — status and banner

- `useSimulatorStatus()` — GET `/simulator/status` is admin-only, so the query
  is `enabled`-gated on `simulator.configure` and **never fires** for a `user`.
  An unconditional call would hand every operator the §11 forbidden side
  effects (a "Sem permissão" toast plus an `/auth/me` refetch) on each visit. A
  403 that arrives anyway (role changed mid-session) collapses into the same
  `restricted` state, and `retry: false` stops a permission wall from becoming a
  retry storm. A 5xx stays distinguishable from a permission wall.
- `useTwinRunning()` — ambient read for surfaces outside the Sim page. The §7
  resync already primes `queryKeys.simulatorStatus` on every (re)connect, so
  this subscribes to that cache entry (`enabled: false`) instead of adding a
  second poll of an admin-only route to the dashboard.
- `SimulationModeBanner` — `role="status"`, accessible name `Simulation mode`
  (frozen by the E2E), so the operator is *told* when the plant turns into a
  model rather than having to notice a colour. `SIMULAÇÃO ATIVA` only while the
  twin is stepping; `MODO SIMULAÇÃO` otherwise. Advisory tokens, never
  `--alarm-crit` — simulation is a mode, not an alarm.
- Mounted on the dashboard too, gated on the twin actually running, from the
  cache read above. Harness-based E2E stub `running: false`, so no dashboard
  pixel changed.

### Task 3 — control panel

Pre-rewrite rules ported onto the phase-2 primitives (`Slider`, `Switch`,
`Button`, `Badge`, `Input`, `EmptyState`/`LoadingState`), styling discarded:

- Ranges verbatim — gain 0–5, dead time 0–30, tau1/tau2 0–60, step 0.1;
  `readout-*` testids with `toFixed(2)`; presets FLOW/PRESSURE/LEVEL/
  TEMPERATURE/CUSTOM; step|noise disturbance with a default amplitude of 10;
  auto-SP 30/70 and auto-disturbance 10 defaults; MAN/AUTO with `aria-pressed`;
  CO clamped 0–100 and closed in AUTO; the 250 ms trailing debounce that
  collapses a slider drag into one `parameters` PUT.
- `Remove` is armed by the server's `step_active || noise_active`, never by the
  click that injected — an armed Remove over a clean model reads as a stuck twin.
- Every mutation invalidates `queryKeys.simulatorStatus` and **returns** the
  invalidation promise, so nothing renders the pre-write snapshot as done. The
  simulator has no WS write-echo; that refetch is the entire feedback loop.
- The panel splits by permission, not by page: the configuration region needs
  `simulator.configure`, `TwinOutputModeControl` (SP / mode / CO) stays mounted
  for a plain operator and falls back to the live STATUS frame for its values.
- `PresetSelector` and the disturbance type are deliberately **native**
  `<select>`s, not the Radix `Select`: the value is server-owned and the E2E
  drives them with `selectOption`.

### Task 4 — twin trend, page, route

- `twinTrend.ts` — `toTwinPoint()` (FFSignal values + ISO/epoch timestamp →
  `{x,pv,sp,co}`, `null` when the timestamp cannot be placed rather than a
  guessed x that would shear the trace) and `TWIN_WINDOW_SECONDS = 300`.
- `TwinTrend.tsx` — reuses `useTrendWindow` rather than growing a second
  buffer: the twin publishes on the ordinary STATUS topic, so it inherits the
  same decimation, the undecimated §6.7 pen tip and AI tick marks, with the
  Phosphor halo under that theme. Its header carries PV/SP/CO readouts and the
  last sample's wall clock — a dead simulator and a settled one look identical
  on a plot, and the clock is what tells them apart.
- `pages/SimulatorPage.tsx` — banner + control column + trend. **Not**
  admin-route-guarded (twin SP/mode/CO are `loop.operate`). The loop list comes
  from the twin snapshot when readable and falls back to `/controllers` when it
  is not; the selector only renders for more than one loop, as before.
- One additive literal in the frozen `appRoutes`: `/simulator`, nav `Sim`
  order 40, palette "Ir para Simulador".

### Task 5 — E2E

`e2e/simulator.spec.ts` gained the two stubs it could not pass without —
`GET /api/auth/me` (deny-by-default `useCan` meant the admin region never
rendered) and the rest of the §7 resync set (`/controllers`, per-loop
`ai/status`, alarm history), since StrictMode always resyncs on first load and
one unmocked call rejects the resync, closes the socket and reconnect-loops.
WS `seq` now advances monotonically; a repeated seq reads as a gap, and the
resync it triggers coalesces every later status frame away from the trend.
**No assertion was weakened.** A third test was added: a `user`-role session
against a 403 `/simulator/status`, asserting the designed restricted state, that
no configuration control leaks, that the trend and the `loop.operate` region
still work off live frames, and — by sampling the socket count twice across a
2 s window spanning three backoff steps — that the 403 does not recycle the
connection.

## Concerns / follow-ups

1. **A `user` session still gets one spurious "Sem permissão" toast per
   (re)connect.** Measured, not inferred: with a 403 on `/simulator/status`, a
   user session makes exactly **1** call to it (from `resync`, none from this
   feature) and raises exactly **1** toast. `resync.ts` correctly swallows the
   403 so the socket never recycles, but the toast is raised earlier and
   globally, by `dispatchAuthSideEffects` in `api/client.ts`. The fix is a
   per-call opt-out of the §11 forbidden side effect for calls whose caller
   *expects* a 403 — both files are outside this phase's ownership boundary
   (`src/realtime/**`), so it is reported rather than changed.
2. **No OPC-UA-server or PID-enable/params controls were added.** The plan's
   global constraints classify `/simulator/opcua/*` and
   `/simulator/{id}/pid/{enable,params}` as admin-only, but they were not in the
   pre-rewrite module set Task 3 says to port, and Task 3's file list does not
   name a component for them. Adding a second `Start` button would also have
   collided with the frozen `/^start$/i` E2E locator. The routes are typed
   nowhere yet; whoever exposes them should extend `simulatorApi` first.
3. **StrictMode opens 3 sockets on first load in dev**, not 2 — measured for
   both admin and user, stable at 3 over 6 s. The new E2E therefore asserts
   "the count stops growing" (two samples, 2 s apart) plus a `<= 4` ceiling,
   which is the real invariant; a fixed number would have been a false pin.
4. **`useTwinRunning` is cache-only by design.** If a later phase drops the
   dashboard's §7 resync priming, the dashboard banner silently stops appearing
   for admins. It is bound to `queryKeys.simulatorStatus`, which the resync
   runner names explicitly, so a rename breaks the type — but a removal would
   not.
5. **Cross-feature import.** `features/simulator/TwinTrend` uses
   `features/dashboard/useTrendWindow` and `SimulatorPage` uses
   `features/dashboard/useControllers`. Deliberate — the alternative was a
   second window buffer and a second roster hook — but both are app-level
   concerns that arguably no longer belong under `features/dashboard`.
