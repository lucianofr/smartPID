# Phase 7 — Multi-trend, Statistics, History, Export — Completion Report

**Status:** COMPLETE — all 6 tasks shipped, phase gate green.
**Plan:** `docs/superpowers/plans/2026-07-26-phase07-multitrend-stats-export.md`
**Worktree:** `.worktrees/web-frontend-rewrite`

## Commits

| SHA | Subject |
|---|---|
| `561a69e` | `feat(web): add four-slot multitrend model` |
| `246e531` | `feat(web): synchronize multitrend time ranges` |
| `3fe94f2` | `feat(web): add multitrend history windows` |
| `77091de` | `feat(web): restore loop statistics panel` |
| `78968f9` | `feat(web): add CSV export create and download` |
| `17a27d7` | `feat(web): ship synchronized multitrend workspace` |
| `78c59a2` | `test(web): cover multitrend history replay and stats scoring end to end` |

Two agents worked this branch concurrently. `3fe94f2` and `77091de` were staged
with a too-wide path add (`packages/smart_pid_web/src`) and swept in
`src/features/simulator/*` files authored by the phase-8 agent; the content is
theirs, unmodified, and their own later commits carry the deltas. Staging was
narrowed for every subsequent commit. Symmetrically, the phase-8 commit
`abd964a` carries this phase's one-line `src/app/routes.tsx` registry entry.
Nothing under `tests/` or `packages/smart_pid_core/` was staged.

## Gate results

| Gate | Result |
|---|---|
| `npm run test -- --run` | **490 passed / 72 files**, exit 0 (398 / 57 at phase 6; +45 phase-7 tests in 8 new files, remainder from the concurrent phase-8 agent) |
| `npm run typecheck` | exit 0 |
| `npm run lint` | exit 0 |
| `npx playwright test e2e/multitrend.spec.ts` | **3 passed** |
| 43 previously-green E2E | **43 passed** — no regression |
| `npm run build && npm run check:bundle` | exit 0 — **183.1 KB gzip JS** (budget 300), CSS 7.5 KB, fonts 109.6 KB |

E2E commands run:

```
npx playwright test e2e/multitrend.spec.ts
npx playwright test --grep-invert 'Executive Dashboard|Connection page|Projects page|Simulator|Multi-trend'
npx playwright test          # full dir: 49 passed / 4 failed
```

`CI=1` is set in this environment, which flips Playwright's
`reuseExistingServer` off and makes the run abort against the already-running
dev server; the commands above were executed with `env -u CI`.

All 4 full-suite failures are unchanged red-by-design specs for routes that
still do not exist in `appRoutes`: `executive-dashboard` ×2 (`/executive`),
`fatia7-connection` (`/connection`) and `fatia7-projects` (`/projects`).
An earlier pass of this gate also showed `simulator.spec.ts:308` failing; that
belonged to the phase-8 agent mid-edit and is green in the final run.

## What shipped

### Task 1 — four-slot model

- `features/multitrend/types.ts` — `Signal`, `SIGNALS`, `MAX_SLOTS = 4`,
  `TrendSlot`, `SignalKey`, `AlignedSeries`, `signalLabel` (the frozen
  `L{loopId} {SIGNAL}` legend name), `freeSlot`.
- `useMultiTrendModel.ts` — four slots, `assign` (all three signals on) /
  `clear` / `toggleSeries`, all three rejecting an out-of-range index with
  `slot must be between 0 and 3`; a controller occupies at most one cell.
  `toggleSignal(loopId, signal)` is the checkbox-grid bridge: it takes the
  first free cell, and releasing a loop's last signal frees the cell and drops
  its buffer. A fifth loop is simply not addable.
- Live buffers: ONE `createWindowBuffer(3, {60 s, 600 pts})` per occupied slot,
  fed from a single `useRealtime(null, 'status')` subscription filtered by the
  slot table. Per-slot buffers make the cross-loop misalignment the deleted
  client had to patch (commit `9b34b24`) impossible by construction — every row
  in a chart shares that buffer's time column — and `push()` returning false on
  a repeated `t` IS the coalesced-frame de-dupe. Timestamps go through
  `statusTimestampToEpoch` (ISO from `pid_worker`, float epoch from
  `monitor_worker`).
- `SeriesSelector.tsx` — `Loop {id} · {PV|SP|CO}` checkboxes (accessible name
  frozen by the E2E; the visible text is the short tag it contains, WCAG 2.5.3).
  Loops are disabled, not silently ignored, once the grid is full.

### Task 2 — feedback-safe time sync

- `timeSync.ts` — `createTimeSync()` with one re-entrancy flag: a publish is
  never echoed to its source, and the publish a sibling's `setScale` triggers
  while broadcasting is dropped. Re-registering an id replaces the entry, and
  an unregister only evicts the chart still owned by that id (remount-safe).
- `MultiTrendChart.tsx` — one uPlot per occupied slot, PV/SP on the left scale,
  CO on a fixed 0–100 right scale, SP dashed (no colour-only encoding), colours
  from `lib/uplotTheme` and rebuilt on `data-theme` flips.
  **Scale pinning:** an untouched chart auto-follows live data and publishes
  nothing — two live charts publishing their own auto-ranges would fight over
  the shared x. The first drag-zoom pins the chart, which both publishes the
  range and switches `setData` to `resetScales = false`, so live samples cannot
  yank a view the operator just framed. uPlot's dblclick releases the pin.

### Task 3 — history and decimation

- `endpoints.history` / `HistoryParams` — `GET /history/{controller_id}`.
  Unlike `/alarms/history`, this route's `start`/`end` are optional; both are
  sent anyway, because an unbounded replay of a historian table is not a window.
- `useHistory.ts` — the operator picks a DURATION (`Janela` × `Unidade`),
  which `historyWindow()` converts to canonical `hours` plus ISO `start`/`end`
  ending now. `useHistory(null)` stays idle: the page never replays unasked.
  `historySeries()` turns wire frames into decimated uPlot columns.
- `decimate.ts` — `decimateHistory()` reuses `windowBuffer`'s min/max-per-pixel
  algorithm through one transient unbounded buffer rather than carrying a
  second copy, sorts to ascending time first (the historian's ordering is not a
  contract we control), and then pins the exact first and latest samples back —
  bucket extrema have no reason to land on the window edges, and those two
  readings are what an operator checks against the range they asked for.
- `HistoryQuery.tsx` — `Janela` / `Unidade` / `Carregar histórico`, submit-only,
  with loading / empty / error states and the returned window plotted through
  the same chart component (`multitrend-history-chart`).

### Task 4 — statistics

- `useStats.ts` — `GET /controllers/stats` polled at 5 s is the ROSTER (a loop
  with no stats worker has nothing to trend and nothing to score, which is why
  the selector's loop list derives from it, not from `/controllers`).
  `STATS.{id}` frames carry the same snake_case payload minus `controller_id`,
  so a live frame supersedes the polled row for that loop and a bus-only loop
  is added. `toStatsRow` maps the wire names onto the panel vocabulary.
- `StatsPanel.tsx` — one row per loop, metrics as columns, so the same metric
  is compared down a column: `IAE ISE ITAE MSE σ 2σ/SP 2σ/Range TV` plus a
  sample count. `lib/format` is the only formatter — `formatNumber(v, 2)` on
  `.numeric` cells and `formatPercent` for the two variability ratios. The
  deleted client's private `multitrend/format.ts` was not recreated.

### Task 5 — export

- `api/types.ts` — `ExportRequest` is `Omit<…, 'format'> & { format?: … }`:
  permanently singular `controller_id`, and `format` stays optional because the
  server defaults it to csv even though the codegen marks defaults required.
- `useExport.ts` — `POST /export` → poll `GET /export/{id}` at 800 ms until
  `done`/`error` → `GET /export/{id}/download`. The download is an
  authenticated fetch (`api.download`): the Bearer token lives in a header that
  a plain `<a href>` navigation cannot carry, so the bytes come back as a blob
  behind an object URL. Revocation is deferred one macrotask — revoking inside
  the click's own turn can cancel the transfer.
- `ExportButton.tsx` — gated on `useCan('export.data')`, which is granted to
  **both** roles (verified against `auth/useCan.ts`, not assumed). States:
  `Exportar CSV` → `Gerando…` (`role="status"`) → `Download CSV`, with
  `Download falhou — repetir` on a failed transfer and `Exportar novamente` on
  a failed job. No list/history affordance: there is no `GET /export/list`
  (TD-008), so one would be fiction.

### Task 6 — page, route, E2E

- `pages/MultiTrendPage.tsx` — 2×2 chart grid (container testid
  `multitrend-chart`, one `multitrend-slot-{i}` per occupied cell) sharing one
  `createTimeSync()`, plus the stats table, the series selector, the history
  panel and the export control, over the persistent §6.9 alarm footer.
- `app/routes.tsx` — one literal appended: `/multitrend`, nav `Trends` order 20,
  palette entry `Ir para Trends`.
- `e2e/multitrend.spec.ts` — fixtures fixed exactly as the plan required and no
  assertion touched: the spec now layers over `e2e/helpers/harness.ts`
  (`seedSession` + `mockRest`, which supply `GET /api/auth/me` — without it
  `useCan` is deny-by-default and the export control never renders — and the
  full §7 resync set, which StrictMode's second mount always runs), keeps its
  own on-demand `__pushStatus` socket stub, and gives that stub a **monotonic**
  per-connection `seq`; a constant `seq: 1` reads as a gap to the phase-3
  tracker and forces a resync on every frame. A third test was added covering
  history replay (duration → ISO bounds spanning exactly the request, decimated
  chart, sample count), the REST-derived stats table, and pause/resume.

## Concerns / follow-ups

1. **Bundle NOT rebaselined.** 183.1 KB gzip against a 300 KB budget and a
   174.9 KB baseline: +8.2 KB, inside the 10 KB regression tolerance, so
   `check-bundle` passes as committed. That figure is phase 7 **and** phase 8
   combined (both landed on this branch before the build). Whoever lands the
   next feature will likely cross the tolerance and should rebaseline in a
   dedicated commit, or take the intended lever — route-level code splitting,
   which needs a `Suspense` boundary in `App.tsx`.
2. **Slot assignment is implicit.** The checkbox grid takes the first free
   cell; there is no drag-to-slot or explicit cell picker. `assign(slot, …)`
   and `clear(slot)` exist and are tested, so a later phase can add one without
   touching the model.
3. **Sync releases per chart.** dblclick unpins the chart it happened on; there
   is no page-level "back to live" that unpins all four at once.
4. **Shared `src/api` files touched.** `types.ts`, `endpoints.ts` and
   `queryKeys.ts` gained append-only entries (history / stats / export). Agreed
   with the phase-8 agent over IRC beforehand; no capability was added, because
   `export.data` already existed in `CAPABILITY_ACTIONS`.
5. **Legend labels can collide under Playwright strict mode.** A live slot for
   loop 1 and a loaded history window for loop 1 both render an `L1 PV` legend
   entry. Harmless for a human (separate labelled panels) but a future
   `getByText('L1 PV')` in a test that does both will need scoping.
