# Phase 9 — Executive Dashboard — Completion Report

**Status:** COMPLETE — all 4 tasks shipped, phase gate green.
**Plan:** `docs/superpowers/plans/2026-07-26-phase09-executive-dashboard.md`
**Worktree:** `.worktrees/web-frontend-rewrite` · branch `docs/web-frontend-rewrite-spec`

## Commits

| SHA | Subject |
|---|---|
| `e5dc5e9` | `feat(web): aggregate executive dashboard data` |
| `094bac0` | `feat(web): add executive KPI and bad actor views` |
| `1a49f24` | `feat(web): add AI ROI and backend health panels` |
| `087e64c` | `feat(web): ship recorder executive dashboard` |

Phase 10 was writing to the same branch throughout. Commits `5e9ec99`,
`559320e`, `d58e640`, `820f312` and `a88989d` are theirs; nothing of theirs was
staged by this phase and nothing of mine was reverted. Shared files touched by
both of us — `src/app/routes.tsx`, `src/api/{types,endpoints,queryKeys}.ts` —
were edited append-only and resolved live over `hub`.

## Gate results

| Gate | Result |
|---|---|
| `npm run test -- --run` | **592 passed / 81 files** (492 / 72 at phase 8; +100, of which 49 are phase 9 — 47 in 4 new files plus 2 added to `DashboardPage.test.tsx`) |
| `npm run typecheck` | exit 0 |
| `npm run lint` | exit 0 |
| `npx playwright test e2e/executive-dashboard.spec.ts` | **2 passed** — both previously-red specs |
| `npx playwright test` (full dir) | **53 passed / 0 failed** |
| `npm run build:budget` | exit 0 — **184.0 KB gzip JS** (budget 300), CSS 7.8 (budget 50), fonts 109.6 (budget 160) |

No regression: the 49 baseline-green E2E all still pass. The full suite is now
53/53 because this phase turned `executive-dashboard.spec.ts` (×2) green and
phase 10 turned `fatia7-connection` / `fatia7-projects` green in parallel.

## What shipped

`src/features/executive/`

| File | Contents |
|---|---|
| `types.ts` | `AUTO_MODES`, `VARIABILITY_TARGET`, `variabilityOutOfTarget`, `healthOf`, `HEALTH_LABEL`, `AggregateInput`, `ExecutiveLoop`, `AggregateKpis`, `aggregate`, `rankBadActors`, `AiRoi`, `aiRoi`, `BackendHealthState`, `OpcState` |
| `useExecutiveData.ts` | `ExecutiveData`, `useExecutiveData`, `PERIOD_OPTIONS`, `periodWindow`, `ExecutivePeriod`, `EXECUTIVE_POLL_MS` |
| `ExecutiveKpiCard.tsx` | `ExecutiveKpiCard` (one card), `ExecutiveKpiBand` (the four canonical KPIs) |
| `BadActorsTable.tsx` | `BadActorsTable` |
| `AiRoiPanel.tsx` | `AiRoiPanel` |
| `BackendHealthPanel.tsx` | `BackendHealthPanel`, `formatUptime` |

`src/pages/ExecutiveDashboardPage.tsx` + test; `/executive` registered in
`src/app/routes.tsx` as command-only (`Painel executivo`, keywords
`executivo/kpi/roi`) — no `nav`, no `cfg`, not `adminOnly`.

### Rules recovered from the pre-rewrite tree

Ported from the deleted `src/lib/kpi.ts` / `ExecutiveDashboardPage.tsx`
(recovered at `38005e9^`), styling deliberately left behind:

- `AUTO_MODES = {AUTO, CAS, RCAS}` — cascade slaves count as automatic.
- `VARIABILITY_TARGET = 0.05` — 2σ inside 5 % of engineering range.
- `healthOf(mode, hasLiveStatus)` — `OOS`/`IMAN` → error; silent and
  mode-less (`''`/`BYPASS`) → stopped; otherwise running.
- Live STATUS mode wins over the REST snapshot mode, per loop.
- Per-loop KPIs: REST seeds, the live STATS frame supersedes per id.

### Reuse, not rebuild

- Roster: `useControllers` (canonical `queryKeys.controllers`, so the §7
  resync's `setQueryData` lands without a refetch).
- Metrics: phase 7's `useStats` — the `GET /controllers/stats` poll plus the
  `STATS.{id}` overlay. No second stats fetch exists.
- Live modes: phase 4's `useLoopStatuses`.
- Numerals: `@/lib/format` only (`formatNumber`, `formatPercent`,
  `formatTimestamp`). Every KPI numeral carries `.numeric` → Geist Mono (§6.2).
- Primitives consumed unchanged: `Badge`, `EmptyState`/`ErrorState`/
  `LoadingState`. Nothing under `src/components/` was modified.

Only `/system/status`, `/opcua/status` and `/alarms/ai-history` are fetched by
this phase. `src/api/{types,endpoints,queryKeys}.ts` gained, append-only:
`SystemStatusResponse`, `AiTuningLogRow`, `endpoints.systemStatus`,
`endpoints.aiTuningHistory`, `AiTuningHistoryParams`, `queryKeys.systemStatus`,
`queryKeys.aiTuningHistory`.

### AI ROI — what the number actually means

The backend keeps exactly one piece of before/after evidence: the AI tuning log
(`GET /alarms/ai-history` → `ai_repo.get_tuning_history_range`), where each row
carries the objective `metric` measured at that tuning. `aiRoi` therefore takes
"before" as the metric at a loop's **first** scored tuning in the window and
"after" as the metric at its **last**, averaged over loops that have both, and
reports `(before − after) / before`. It returns `null` — never a zeroed shape —
when the window cannot support that comparison (fewer than two scored tunings
on every loop, or a zero baseline), and `AiRoiPanel` renders the explanatory
missing state. A regression shows as a negative gain in the warn token; it is
never re-signed or hidden.

## Deviations from the plan, and why

1. **`?loop=` was a dead link.** The plan requires a bad-actor row to navigate
   to `/?loop=<id>`, but `DashboardPage` selected loops from local state only
   and ignored the query string. Four lines in `DashboardPage.tsx` now seed the
   initial selection from `?loop=`, covered by two new tests. Without it the
   plan's requirement would have shipped as a link that lands on the wrong loop.
2. **Period control.** The plan does not name one, but the AI ROI window would
   otherwise be an invisible constant and the E2E fixture stubs
   `/alarms/ai-history**` with a query string. A native `<select>` (the
   `HistoryQuery` convention, not the Radix `Select`) offers 1 h / 8 h / 24 h /
   7 d. The window anchor is rounded down to the minute — a fresh `Date.now()`
   per render would mint a new query key every render and refetch forever.
3. **Code splitting.** See below.
4. **Wordmark → `/executive`** (plan Task 4 step 1) was applied by the phase-10
   agent inside their `AppShell.tsx` commit, agreed over `hub`, because that
   file is theirs. Verified present at HEAD.
5. **No tuning-recommendation card.** The pre-rewrite page had one and the E2E
   fixture still stubs `/controllers/1/ai/status` and
   `/commands/tuning-recommendations/1`; the plan's task list does not include
   it, so those two stubs are now unused. Left in the spec: harmless, and they
   document the routes a future per-loop AI panel would need.

## Bundle

Registering the fifth route took the entry chunk to **193.7 KB gzip**, 18.8 KB
over the committed 174.9 KB baseline and past the 10 KB tolerance (phases 7-10
all contributed; phase 9's own share is a few KB of it). The budget itself
(300 KB) was never at risk.

Per the phase brief the lever was code splitting, not a higher budget and not a
rebaseline. `src/app/routes.tsx` now wraps the secondary surfaces in a
`lazyPage` helper (`React.lazy` over a named export, returning `ComponentType`
so `AppRoute.element` needed no widening) and `App.tsx` gained one `Suspense`
boundary **inside** `AppShell`, so the top bar and palette stay on screen while
a route chunk arrives.

| Step | Entry JS gzip | Δ vs baseline |
|---|---|---|
| before | 193.7 KB | +18.8 KB ✗ |
| `/executive` + 4 admin routes lazy | 186.5 KB | +11.6 KB ✗ |
| `/simulator` also lazy | **184.0 KB** | **+9.1 KB ✓** |

`bundle-baseline.json` is untouched. Loops · Trends · Alarms remain in the
first paint; `/simulator` is a commissioning tool and the admin group plus the
buyer dashboard are visited rarely, so on-demand loading costs them one cached
request each.

## Concerns / follow-ups

1. **`/system/status` publishes no CPU or memory.** `routers/system.py` returns
   `status`, `uptime_s`, `active_controllers`, `bus_active`, `api_version`, and
   `EVENT.SYSTEM` carries only `source/severity/message/timestamp`. The plan's
   `BackendHealthPanel` contract names `cpu_percent` and `memory_percent`, so
   they are optional on `BackendHealthState` and render '—' rather than a
   fabricated 0. Two rows of that panel are therefore permanently empty until a
   backend build publishes process counters — a real API gap, not a UI one.
   Nothing here is synthesised; flagging it rather than faking it.
2. **`Readout` was not usable for the health rows.** The plan's normative test
   requires `getByText('12.4%')` to itself carry `.numeric`, and `Readout`
   splits value and unit into sibling spans (and takes `value: number`, while
   uptime is `'1 h 1 min'`). `BackendHealthPanel` renders its own label/value
   row over pre-formatted strings instead. The primitive was NOT forked — no
   formatting logic is duplicated — but reporting it as asked: a `Readout`
   variant that glues a unit into the numeric span would have fit.
3. **`EVENT.SYSTEM` severity is a free string.** `system_event_worker.emit`
   takes `severity: str` with no enum; only `INFO` is emitted today, so the
   panel treats anything else as abnormal. A backend enum would make that
   robust instead of conventional.
4. **AI coverage is roster-level.** `Cobertura da IA` counts loops with
   `optimization_enabled === true` and `ai_config.engine !== 'NONE'` — one
   `/controllers` request instead of N `/controllers/{id}/ai/status` calls. If
   the buyer question is really "how many AI workers are RUNNING right now",
   that needs the per-loop route and an N-query fan-out.
5. **`e2e/helpers/harness.ts` still has no `__pushStats`.** The executive spec
   keeps a local socket stub for that one capability. If a second spec ever
   needs to inject a live frame, promote it into the harness rather than
   copying the stub a third time.
