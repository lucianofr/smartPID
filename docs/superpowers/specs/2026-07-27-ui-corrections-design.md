# Design — UI corrections (faceplate rail, nav, trends, icons)

**Documento:** Design / Spec (saída de brainstorming)
**Data:** 2026-07-27
**Autor:** Luciano França Rocha — LFR Automação
**Status:** Proposto (aguardando revisão)
**Branch:** `docs/web-frontend-rewrite-spec`
**Baseline:** commit `34c445d` (`test(e2e): E2E-021 passes — 50/50 gate green`)
**Companion:** [`TEST_E2E.md`](../../../TEST_E2E.md) — acceptance gate

> Written in English to match the companion rewrite spec. **UI copy stays pt-BR** and existing
> accessible names are preserved verbatim wherever a test binds to them.

---

## 1. Context

The web frontend rewrite shipped at `34c445d` with the 50/50 `TEST_E2E.md` gate green. Operating
the delivered UI surfaced six defects that the gate does not cover, because each is a layout or
information-architecture problem rather than a behavioural one:

1. The Loops faceplate scrolls. Measured on the running app (1920×1080, admin, loop `TIC-E2E`):
   content is **1121 px** in a **572 px** box — **549 px of overflow**.
2. The executive dashboard is reachable only from the wordmark and the command palette; it has no
   entry in the top bar.
3. Trend selection lives in `useState` inside `useMultiTrendModel` and dies when the page unmounts.
4. Trend cells carry no visible title, and the Trends page knows loops only by numeric id, so a
   chart cannot be attributed to a loop by looking at it.
5. The `[k]` command-palette affordance is a bracketed abbreviation bound to a bare single-key
   shortcut.
6. `[cfg]` is a bracketed abbreviation, in two distinct places with two distinct destinations.

All measurements in this document were taken with CDP against the live instance at
`http://127.0.0.1:5173` (backend `127.0.0.1:8000`, four loops, simulator running), not estimated.

## 2. Goals

- The Loops faceplate occupies a full-height left column and does not scroll at any supported
  desktop viewport.
- Every primary surface, including the executive dashboard, is reachable from the top bar.
- Trend selection survives navigation, reload and browser restart.
- Every trend cell names its loop.
- No bracketed-abbreviation controls remain in the chrome.

## 3. Non-goals

- The 394 px card-strip height. Out of scope.
- A resizable / collapsible faceplate column.
- Persisting `paused` or the history-query window.
- Changing `GET /controllers/stats` to return loop names. The id→tag join happens client-side
  against the already-cached `GET /controllers` query.
- Any backend change. This work is frontend-only.

## 4. Change 1 — Faceplate as a full-height left rail

### 4.1 Current

`DashboardPage` renders three stacked bands inside `flex min-h-0 flex-1 flex-col`:
`section[aria-label="Malhas"]` (card strip, 394 px), then
`div[data-testid="dashboard-detail"]` (`lg:flex-row`) holding `TrendPanel` + `Faceplate`, then
`AlarmFooterBar`. `Faceplate` is `w-full shrink-0 … lg:w-80 lg:overflow-y-auto lg:border-l`.

### 4.2 Target

At `lg` and above the page becomes two columns; below `lg` the current stacked behaviour is
unchanged and the **page** scrolls, which is correct on a narrow viewport.

```
┌──────────────────────────────────────────────┐
│ header (AppShell)                            │
├──────────────────────────────────────────────┤
│ ConnectionBanner (AppShell)                  │
├──────────────────────────────────────────────┤
│ SimulationModeBanner (only when twin runs)   │
├───────────┬──────────────────────────────────┤
│ FACEPLATE │ card strip (horizontal scroller) │
│  320 px   ├──────────────────────────────────┤
│  full     │ TrendPanel                       │
│  height   │                                  │
├───────────┴──────────────────────────────────┤
│ AlarmFooterBar                               │
└──────────────────────────────────────────────┘
```

`SimulationModeBanner` and `AlarmFooterBar` stay full width. They are page-level bands, not loop
detail.

- `Faceplate` loses `lg:border-l` and gains `lg:border-r` (it is now the left edge of the content).
- `Faceplate` keeps `overflow-y-auto` strictly as a safety valve for geometries outside the
  supported set. In every designed state it must not engage.
- The card strip and `TrendPanel` move into a right-hand column that owns its own
  `flex min-h-0 flex-1 flex-col`.

### 4.3 Height budget

Measured decomposition of the current 1121 px faceplate (admin, `p-3` = 12 px, `gap-3` = 12 px):

| Child | px |
|---|---|
| `header` (tag, description, mode badge) | 35 |
| PV / SP / CO bars | 68 |
| IAE and 2σ/Range row | 46 |
| AUTO / MAN buttons | 44 |
| Setpoint entry | 67 |
| Manual CO (label, slider, numeric entry, button) | 137 |
| `section[aria-label="Otimização IA"]` | 629 |
| padding (24) + 6 gaps (72) | 96 |
| **Total** | **1121** |

The AI section decomposes as: status 47, **config form 417**, Start/Pause/Stop 44, LOG.AI box 33
(empty) to 128 (`max-h-32`, full), Apply tuning 44, plus 4 internal gaps (32) and `pt-3` (12).

After §5 moves the 417 px config form out (removing one 8 px internal gap with it):

| | px |
|---|---|
| Faceplate fixed content (everything except the LOG.AI box) | **664** |
| LOG.AI box | 33 empty → 128 full |

Available column height is `viewport − 57 (header) − 57 (AlarmFooterBar) − 40 (twin banner, when shown)`:

| Viewport | Available with banner | 664 + 128 fits? |
|---|---|---|
| 1920×1080 | 926 | yes, 134 px spare |
| 1600×900 | 746 | no, short 46 px |
| 1440×900 | 746 | no, short 46 px |
| 1024×768 | 614 | no, short 178 px |

Moving the AI config form is therefore **necessary but not sufficient**. The remaining deficit is
closed by compaction inside the rail, using these measured levers:

| Lever | Saving |
|---|---|
| LOG.AI box: `max-h-32` (fixed 128 px cap) → `flex-1 min-h-0` with a **32 px** floor | elastic; frees up to 96 |
| Start/Pause/Stop and Apply tuning share one row instead of two | 52 |
| Faceplate `gap-3` → `gap-2` (6 gaps) | 24 |
| Faceplate `p-3` → `p-2` | 8 |

Worst supported case is 1024×768 with the twin banner: 614 px available against 664 px of fixed
content. The last three levers (84 px) bring fixed content to 580 px, leaving 34 px for the log
box. Hence the 32 px floor (one line plus padding): 580 + 32 = 612 ≤ 614.

Implementation must re-measure rather than trust this arithmetic: the acceptance criterion below is
the contract, not the table.

### 4.4 Acceptance

Measured with CDP on the running app, for roles `admin` and `user`, with and without the simulator
banner, at viewports 1920×1080, 1600×900, 1440×900 and 1024×768:

```js
const fp = document.querySelector('aside[aria-label^="Faceplate"]');
fp.scrollHeight === fp.clientHeight   // must be true in all 16 combinations
```

And: the page itself must not gain a vertical scrollbar
(`document.documentElement.scrollHeight === document.documentElement.clientHeight`) at those sizes.

Interactive targets inside the rail must remain ≥44×44 CSS px after compaction (E2E-050). Any lever
that would breach this is rejected; reduce the log floor instead.

## 5. Change 2 — Move the AI configuration form into the loop config dialog

### 5.1 Split

`AiPanel` (`features/loop-config/AiPanel.tsx`) renders five blocks. Exactly one moves:

| Block | Lines (baseline) | Destination |
|---|---|---|
| Lifecycle badge + `engine · Ki · γ` | 180–199 | stays in `Faceplate` |
| **Motor / Objetivo / Velocidade / Tempo morto L / Limite mín. / Limite máx. + "Salvar IA"** | **201–328** | **moves to `LoopConfigDialog`** |
| Start / Pause / Stop | 330–356 | stays |
| LOG.AI terminal | 358–374 | stays, becomes the flexible element |
| Apply tuning + `ConfirmApplyTuningDialog` | 376–403 | stays |

### 5.2 Target shape

`LoopConfigDialog` is not tabbed; it is a sequence of `<Section label="…">` blocks
(`PID Tuning`, `Scaling & Limits`, `Filters & IO`, `Shed & Safety`, `PID Structure`,
`Integral Type`). The AI fields become one more: **`<Section label="AI Optimization">`**, placed
after `Integral Type`.

The moved fields join the dialog's existing single-draft flow:

- `Draft` (`toDraft`) gains `process_speed: ProcessSpeed` and
  `ai: { engine, objective, dead_time_l, limit_min, limit_max }`, defaulted exactly as `AiPanel`
  defaults them today (`NONE`, `DISTURBANCE_REJECTION`, `MEDIUM`, `1`, `0.1`, `100`) so a roster row
  that predates `ai_config` still renders.
- The dialog's `save()` adds `process_speed` and `ai_config` to its single `PATCH /controllers/{id}`.
- `blocked` gains `hasErrors(validateAiConfig(...))`.
- The standalone **"Salvar IA" button is deleted.** Two save buttons writing the same PATCH from one
  dialog is a defect, not a feature.
- Fields are `disabled={readOnly}` like every other field in the dialog.

Unlike the AI section in the faceplate, these fields are **not** gated on `ai_config` engine state;
they are the thing that sets it.

### 5.3 Permissions — unchanged

`tuning.edit` and `controllers.manage` are both admin-only (`useCan.ts`: `USER_ACTIONS` holds only
`view`, `alarms.ack`, `loop.operate`, `export.data`). The moved section inherits the dialog's
`readOnly = !canManage`, which for both roles produces exactly today's behaviour. `AiPanel` already
returns `null` entirely for a `user` (`visible = canControl || canTune`), so the faceplate rail for
a `user` is unaffected by §5 and trivially satisfies §4.4.

### 5.4 Structural note

The moved JSX is extracted as a named component in `features/loop-config/` rather than pasted, so
`LoopConfigDialog.tsx` (718 lines at baseline) does not grow by another ~130 lines of field markup.
`AiPanel` keeps ownership of the lifecycle, log and tuning-apply concerns only.

## 6. Change 3 — Remove the command palette

`k`-as-a-shortcut is hostile on an operating screen: a single stray keypress opens a modal over a
live process. With the executive dashboard in the top bar (§8), the palette reaches no destination
the visible chrome does not.

Removed:

- The `[k]` `Button` and its `aria-keyshortcuts` in `AppShell`.
- The `keydown` listener and `isEditableTarget` helper in `AppShell`.
- The `<CommandDialog>` mount and `runCommand` callback in `AppShell`.
- `AppRoute.command` and `commandRoutes()` in `app/routes.tsx`, plus every `command:` literal in
  `appRoutes`.
- `src/components/Command.tsx` and `src/components/Command.test.tsx` (orphaned).
- The `cmdk` dependency in `package.json`.

`WithCommand` and the palette ordering comment go with them. `navRoutes` and `cfgRoutes` are
untouched.

## 7. Change 4 — Icons instead of `[cfg]`

`lucide-react` is already a dependency and already used by `Command`, `Dialog`, `DropdownMenu`,
`Select` and `Toast`.

| Location | Current glyph | Target | Accessible name |
|---|---|---|---|
| `AppShell` dropdown trigger | `[cfg]` | `<Settings>` (gear) | `Configurações` — **unchanged** |
| `LoopCard` config button | `[cfg]` | `<SlidersHorizontal>` | `Configurar {tag}` — **unchanged** |

Two destinations get two glyphs: the top bar configures the *application*, the card configures a
*loop*, and both are on screen simultaneously. Icons are `aria-hidden="true"`, matching the spans
they replace; the accessible name continues to come from the button's `aria-label`, so every test
that locates by role + name stays valid.

Copy update: `LoopConfigDialog.tsx:656` reads "O restante da configuração fica disponível no [cfg]
da malha criada." It must stop naming a control that no longer exists.

Icon size follows the existing `Button` icon convention; the ≥44×44 px target is a property of the
button, not the glyph, and must not regress.

## 8. Change 5 — Executive dashboard in the top bar

`app/routes.tsx`: the `/executive` entry gains `nav: { label: 'Executivo', order: 50 }`, producing
`Loops · Trends · Alarms · Sim · Executivo`. The route stays non-`adminOnly`, so both roles keep it,
which is today's behaviour.

`AppShell`: the wordmark `NavLink` target changes from `/executive` to `/`. With a visible nav entry
the wordmark link is redundant, and pointing the brand at the landing route is the convention.

The nav container is already `overflow-x-auto`; the 320 px floor must be re-verified (§11) because
a fifth item was added and commit `bab300a` fixed a 4 px header overflow at that width.

## 9. Change 6 — Trends: persisted selection and titled cells

### 9.1 Persistence

New module `features/multitrend/trendSelectionStore.ts`, exporting two pure functions —
`readTrendSelection(): TrendSlot[]` and `writeTrendSelection(slots: readonly TrendSlot[]): void`.

**Deliberately not a `useSyncExternalStore` store.** `useSettings.ts` uses that pattern because
preferences are read by many components; the trend selection has exactly one reader. A subscription
store here would be ceremony. `useMultiTrendModel` keeps its `useState`, lazily initialised from
`readTrendSelection()`, and persists via an effect on `slots`.

- Key `spid.multitrend` in `localStorage`, sibling to the existing `spid.theme` and
  `spid.preferences`. **Not** folded into `AppPreferences`: that is a user-facing form with a
  "Restaurar padrões" button, and a reset must not wipe a trend layout.
- Persisted payload: the four slots only — `{ controllerId: number | null, series: { pv, sp, co } }`.
- **Not persisted:** `paused`. Restoring a paused chart would render frozen data with no indication
  it is frozen — the same failure class as E2E-047. It resets to `false` on mount.
- **Not persisted:** the 60 s window buffers. Charts restore empty and refill from live frames.
- Read is defensive, exactly like `useSettings.load()`: `JSON.parse` inside `try`, unreadable or
  malformed storage falls back to four free slots, and a write failure (quota, private mode)
  degrades to session-only without surfacing an error.
- Shape validation on read: anything that is not four entries of the expected shape is discarded
  wholesale rather than partially trusted.

### 9.2 Reconciliation

The hook signature changes to `useMultiTrendModel(roster: readonly number[] | null)`, where `null`
means "the roster query has not resolved yet". `MultiTrendPage` passes
`stats.isPending ? null : stats.loops`.

**Three call sites** must be updated: `pages/MultiTrendPage.tsx:28`,
`features/multitrend/useMultiTrendModel.test.tsx:17` and `realtime/multiLoopFanout.test.tsx:157`.
The two tests pass `null` unless they are specifically exercising reconciliation, which preserves
their current behaviour exactly.

Reconciliation runs in an effect, once, on the first non-`null` roster:

- A slot whose `controllerId` is absent from the roster is released to a free slot, and its window
  buffer is dropped.
- A slot with no signal enabled is released.
- While `roster` is `null` nothing is reconciled — an unresolved query must never be read as
  "every loop is gone".

Restoring a chart for a loop that no longer exists would render a permanently empty cell; that is
the failure this prevents.

### 9.3 Titles

`MultiTrendPage` mounts `useControllers()` (already cached; the dashboard uses the same query) and
builds an id→`{ name }` lookup.

- Each cell gains a visible header, format **`#3 · TIC-E2E`**.
- The chart's `aria-label` changes from `Tendência Loop 3` to `Tendência #3 · TIC-E2E`, matching the
  Loops page which already names its chart `Tendência ${tag}`. No E2E binds the current string;
  `MultiTrendChart.test.tsx` passes `ariaLabel` explicitly as a prop and is unaffected.
- `SeriesSelector` row labels change from `Loop 3` to the same `#3 · TIC-E2E`, so the selector and
  the grid map onto each other by sight. The `w-16` label column widens to fit.
- Fallback when the name has not loaded or the loop is absent from `/controllers`: `Loop {id}`.
  Never blank.

**Frozen, must not change:** the checkbox `aria-label` `Loop {id} · {SIGNAL}`. It is asserted by
`SeriesSelector.test.tsx` (4 names) and by `e2e/multitrend.spec.ts:150,151,214`. Only visible text
changes.

## 10. Test impact

### 10.1 Unit / component (Vitest, 746 passing at baseline)

| File | Change |
|---|---|
| `app/AppShell.test.tsx` | Delete the palette tests (`k` opens, `Comandos` button visible). Keep every `Configurações` menu test — the accessible name is unchanged. |
| `components/Command.test.tsx` | Deleted with the component. |
| `features/loop-config/__tests__/AiPanel.test.tsx` | Two cases move out verbatim: the field-inventory case (`Motor` options, `Tempo morto L`, `Limite mín.`, `Limite máx.`, `Velocidade do processo`, lines 239–250) and `refuses to save an inverted guardrail band` (252–257). Lifecycle, log, `Start`/`Apply tuning` and the `user`-sees-nothing case stay. |
| `features/loop-config/__tests__/LoopConfigDialog.test.tsx` | Receives those two cases, retargeted: the guardrail case now asserts the dialog's single `Salvar` is disabled, not `Salvar IA`. Adds: `readOnly` disables the AI fields, and `save()` sends `ai_config` + `process_speed` in the single PATCH. |
| `features/dashboard/Faceplate.test.tsx` | No change. Verified: it asserts none of the moved field labels. |
| `features/multitrend/SeriesSelector.test.tsx` | Visible-text assertions updated; the four `getByLabelText('Loop N · SIGNAL')` assertions unchanged. |
| `features/multitrend/useMultiTrendModel.test.tsx` | Signature update (pass `null`), plus new cases: restore from storage, persist on change, drop an id absent from the roster, ignore malformed storage, `paused` not restored, `null` roster reconciles nothing. |
| `realtime/multiLoopFanout.test.tsx` | Signature update only — passes `null`, behaviour unchanged. |

There is no `app/routes.test.*`; `routes.tsx` is covered indirectly through `AppShell.test.tsx`,
which is where the `Executivo` nav assertion goes.

New logic requiring new tests: trend-selection persistence and roster reconciliation. Everything
else in this work is a move, a deletion or a style change.

### 10.2 Playwright (79 passing at baseline)

| Spec | Change |
|---|---|
| `e2e/login-dashboard.spec.ts` | Remove the `Comandos` button assertion and the `k`-opens-palette step. |
| `e2e/responsive.spec.ts` | Replace the `Comandos` target-size assertion; add the rail no-scroll assertion at each viewport. |
| `e2e/target-size.spec.ts` | Remove `Comandos`; keep `Configurações`. |
| `e2e/user-role.spec.ts` | Binds by accessible name only — unchanged. |
| `e2e/themes.spec.ts` | Binds `Configurações` by name — unchanged. |
| `e2e/multitrend.spec.ts` | Unchanged (`getByLabel('Loop 1 · PV')` preserved). New spec for persistence across a reload. |

### 10.3 `TEST_E2E.md`

The 50-procedure gate is the project's declared stop condition. Four procedures are affected.

| # | Procedure | Resolution |
|---|---|---|
| **E2E-006** | *Command palette* | **Repurposed.** The feature is removed, so the procedure cannot pass or fail as written. The number is reused for: navigate to the executive dashboard from the top bar. This covers the risk the change actually introduces and keeps the gate at 50. |
| **E2E-036** | Executive KPIs | Steps say "open `/executive` from wordmark/palette" → becomes "from the top bar". Expected outcome unchanged. |
| **E2E-049** | Responsive | "≥1024 trend/faceplate side-by-side" remains true (faceplate is now the left column). Gains a **new, stricter** assertion: the faceplate rail's `scrollHeight === clientHeight`. |
| E2E-015 / E2E-043 | Faceplate consistency / user forbidden | Assertions remain valid; the evidence PNGs must be re-captured against the new layout. |

E2E-006's new text:

> **E2E-006 — Executive dashboard from the top bar**
> **Steps:** As `admin` and as `operador`, click `Executivo` in the top bar; confirm the route; click
> the wordmark.
> **Expected:** `Executivo` is present for both roles and navigates to `/executive`; the wordmark
> navigates to `/`.

No assertion anywhere in `TEST_E2E.md` is weakened. E2E-049 is strengthened.

## 11. Verification plan

Ordered. Each step must pass before the next.

1. `npm --prefix packages/smart_pid_web run typecheck` and `run lint`.
2. Vitest full run — must be green, with the amended and new tests described in §10.1.
3. Playwright — `cd packages/smart_pid_web && env -u CI npx playwright test`. **Not** the `browser`
   tool: it does not deliver CDP input to the page (documented harness defect) and has previously
   produced false "dead control" reports.
4. CDP measurement sweep for §4.4: 16 combinations (4 viewports × 2 roles × banner on/off),
   asserting `scrollHeight === clientHeight` on the rail and no page-level vertical scrollbar.
5. Header horizontal-overflow check at 320 px width with the fifth nav item (§8).
6. Manual re-run of the four affected `TEST_E2E.md` procedures with fresh evidence PNGs.
7. Full backend suite is **not** re-run: this work touches no Python. Frontend-only.

## 12. Risks

| Risk | Mitigation |
|---|---|
| 1024×768 rail does not fit even after compaction — §4.3 leaves only **2 px** of margin (612 of 614) | The log-box floor is the adjustable term. If it still overflows, cut the floor further before touching any 44 px target, and report rather than silently shipping a scrollbar. |
| Compaction breaches the 44×44 px target (E2E-050) | Target size is a hard constraint. §4.4 rejects any lever that breaches it. |
| Moving AI config changes what an operator can reach | Both capabilities are admin-only and the dialog is read-only for `user`; §5.3 shows the role matrix is unchanged. Verified by the existing `user-role.spec.ts`. |
| `localStorage` restore resurrects a deleted loop | §9.2 reconciles against the live roster before rendering. |
| Reconciliation misfires while the roster query is pending | §9.2 gates on the roster having loaded. Explicit test case. |
| Removing `cmdk` or `Command.tsx` breaks an unrelated import | **Verified, not assumed:** `cmdk` is imported only by `components/Command.tsx`, and `Command.tsx` only by `app/AppShell.tsx` and its own test. Both deletions are closed. |

## 13. Decisions recorded

| # | Decision | Rationale |
|---|---|---|
| D1 | AI *config* moves to the loop dialog; AI *operation* stays on the faceplate | Only cut that fits the height budget without breaking touch targets; also puts configuration where configuration already lives. |
| D2 | Command palette removed entirely, not hidden behind Ctrl+K | A feature with no visible affordance and no exclusive destination is dead weight. |
| D3 | Distinct icons for the two `[cfg]` controls | Both are on screen at once and lead to different places. |
| D4 | `Executivo` last in the nav; wordmark → `/` | Loops is the operator's routine surface and the `/` route; the executive view is consultative. |
| D5 | `localStorage`, own key, reconciled | Matches `spid.theme`/`spid.preferences`; "persisted" that a reload erases is not persisted. |
| D6 | Title format `#3 · TIC-E2E` in both chart and selector | Tag for recognition, id to match URLs (`/?loop=3`) and toasts (`Malha #3`) and to disambiguate duplicate tags. |
| D7 | E2E-006 repurposed rather than deleted | Keeps the gate at 50 and covers the navigation path that replaced the palette. |
