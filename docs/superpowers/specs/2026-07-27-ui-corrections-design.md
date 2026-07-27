# Design — UI corrections and the `neon` theme

**Documento:** Design / Spec (saída de brainstorming)
**Data:** 2026-07-27
**Autor:** Luciano França Rocha — LFR Automação
**Status:** Proposto (aguardando revisão)
**Branch:** `docs/web-frontend-rewrite-spec`
**Baseline:** commit `34c445d` (`test(e2e): E2E-021 passes — 50/50 gate green`)
**Companion:** [`TEST_E2E.md`](../../../TEST_E2E.md) — acceptance gate
**Skill:** `ui-ux-pro-max` — the §10 theme is derived from it; queries and rejected recommendations are recorded in §10.1

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

A seventh item is not a defect but a directive: the delivered look is commercially weak. §10 adds a
fourth theme — vibrant, neon, glowing — that explicitly discards the ISA-101 premises the other
themes obey, and makes it the default.

All measurements in this document were taken with CDP against the live instance at
`http://127.0.0.1:5173` (backend `127.0.0.1:8000`, four loops, simulator running), not estimated.
Colour figures are computed (WCAG 2.x relative luminance; OKLCH chroma), not eyeballed.

**Scope note.** Sections 4–9 (the UI corrections) and §10 (the theme) are independent: neither
blocks the other, and they touch disjoint files apart from `Faceplate.tsx`. The implementation plan
should phase them separately so the corrections can ship without waiting on a font vendoring step.

## 2. Goals

- The Loops faceplate occupies a full-height left column and does not scroll at any supported
  desktop viewport.
- Every primary surface, including the executive dashboard, is reachable from the top bar.
- Trend selection survives navigation, reload and browser restart.
- Every trend cell names its loop.
- No bracketed-abbreviation controls remain in the chrome.
- A fourth theme, `neon`, ships as the default: neon palette, semantic glow, its own display face,
  passing the existing WCAG gate without relaxing a single floor.

## 3. Non-goals

- The 394 px card-strip height. Out of scope.
- A resizable / collapsible faceplate column.
- Persisting `paused` or the history-query window.
- Changing `GET /controllers/stats` to return loop names. The id→tag join happens client-side
  against the already-cached `GET /controllers` query.
- Any backend change. This work is frontend-only.
- Restyling `recorder`, `phosphor` or `isa101`. Their values are untouched; they gain only the four
  glow tokens (as `none`) and an explicit `--font-display` the contract now requires per theme.
- Scanlines, glitch effects or a CRT overlay. The source skill suggests them; a process display that
  simulates signal corruption is a support call.

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

**320 px floor — measured, not deferred.** At 320 px the nav is already a horizontal scroller today:
`clientWidth` 61 px against `scrollWidth` 188 px (4 links × 44 px + 3 gaps × 4 px), while
`header.scrollWidth === header.clientWidth === 320` and page `scrollWidth - clientWidth === 0`. Flex
shrinks every link to its `min-w-11` (44 px) touch floor, and `overflow-x-auto` absorbs the rest. A
fifth link takes `scrollWidth` to 236 px inside the same 61 px window — **structurally identical, no
page overflow introduced.** The `bab300a` regression is not reachable this way, because the nav, not
the header, is what gives.

Observation, deliberately not fixed here: a 61 px window onto a 188 px strip is a poor nav at 320 px.
That is pre-existing and orthogonal to this work. E2E-049 only requires no horizontal page overflow
at 320 px, which holds before and after.

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

## 10. Change 7 — the `neon` theme

### 10.1 Directive and what it displaces

Operator directive, verbatim: a new theme, derived from the `ui-ux-pro-max` skill, **discarding
every ISA-101 premise**, whose goal is commercial appeal.

The premise being discarded is named in `contract.ts:22` — *"State (gray in normal operation —
green never means ok)"*. Under ISA-101 the normal state is colourless and saturation is reserved
for abnormal conditions. `neon` abandons that: `--state-running` becomes neon green.

This is safe to do **because it is an additional theme, not a replacement.** `recorder` and
`isa101` stay in the picker untouched, so a customer who requires ISA-101 conformance still has a
conforming surface. That is the entire mitigation, and it is why the directive costs nothing
irreversible.

**One gate does not fall with ISA-101:** `themeContrast.test.ts` runs WCAG 1.4.3 (4.5:1 text) and
1.4.11 (3:1 non-text) in CI over every palette in `GateThemeId`. WCAG is a different standard from
ISA-101, and it is also priority 1 of the skill this theme is derived from. `neon` joins that gate.

Skill provenance (`ui-ux-pro-max`):

| query | result used |
|---|---|
| `--design-system "industrial control room HMI dashboard neon glow vibrant dark"` | *Modern Dark (Cinema Mobile)* — deep near-black, glow, avoid pure `#000000` (OLED smear) |
| `--domain style "dark neon glow cyberpunk premium commercial"` | *Cyberpunk UI* — neon cyan/magenta on `#0D0D0D`; skill rates its own accessibility ⚠ *Limited* |
| `--domain typography "technical monospace data futuristic"` | Orbitron / JetBrains Mono |

Skill recommendations **not** adopted, with reason: scanlines and glitch keyframes (a process
display that simulates signal corruption is a support call, not a style); Google Fonts CDN import
(this product can be deployed on an isolated network — fonts are self-hosted, §10.6); JetBrains
Mono (Geist Mono is already vendored and already the numeric face; a second mono buys nothing).

### 10.2 Identity

`id: 'neon'`, label `Neon`, and it becomes `DEFAULT_THEME`. The sibling names are instruments
(Recorder = paper chart recorder, Phosphor = CRT phosphor); `Neon` breaks that pattern deliberately
because it needs no explanation and matches the directive's own word.

### 10.3 Palette

The 41 non-type contract tokens. `CONTRACT_TOKENS` holds **44** today (41 + the three `--font-*`);
§10.5 adds four glow tokens, taking it to **48**, and the `[data-theme="neon"]` block declares
**46** of them — the 41 below, the 4 glow tokens, and `--font-display` (§10.6). `--font-ui` and
`--font-data` stay in `:root`. Every colour pair below was checked against the 43 assertions
`themeContrast.test.ts` actually makes; all pass.

| Token | Value | Note |
|---|---|---|
| `--bg` | `#07070E` | not `#000000` — pure black smears on OLED |
| `--surface` | `#101226` | |
| `--surface-sunk` | `#0A0B18` | chart wells, inputs |
| `--rule` | `#1E2038` | hairlines, decorative only |
| `--rule-strong` | `#5A60A8` | control boundaries, ≥3:1 on surface and sunk |
| `--text` | `#E9ECFF` | 17.12:1 on `--bg` |
| `--text-soft` | `#A6ADDC` | ≥4.5:1 on all three surfaces |
| `--text-disabled` | `#5A5F85` | |
| `--focus-ring` | `#00E5FF` | |
| `--selection` | `#1B2A5C` | |
| `--scrim` | `rgba(3,3,8,0.72)` | |
| `--accent` | `#00E5FF` | |
| `--accent-hover` | `#66F2FF` | |
| `--accent-sunk` | `#0088A0` | pressed |
| `--accent-soft` | `#0A2A38` | tinted accent surface |
| `--on-accent` | `#04040A` | 13.29:1 on accent |
| `--alarm-crit` | `#FF2D6F` | 5.60:1 on `--bg` |
| `--alarm-crit-bg` | `#3A0A1C` | |
| `--alarm-warn` | `#FFB020` | |
| `--alarm-warn-bg` | `#3A2600` | |
| `--alarm-adv` | `#C77DFF` | |
| `--alarm-adv-bg` | `#28123E` | |
| `--alarm-log` | `#A6ADDC` | |
| `--on-alarm` | `#04040A` | ≥4.5:1 on all four fills |
| `--state-running` | `#39FF88` | **the discarded ISA-101 premise, made visible** |
| `--state-stopped` | `#A6ADDC` | |
| `--state-error` | `#FF2D6F` | |
| `--state-oos` | `#4A4E6E` | contrast-exempt: faded IS the signal |
| `--trace-pv` | `#00F0FF` | |
| `--trace-sp` | `#B8BEE8` | |
| `--trace-co` | `#FFA630` | |
| `--trend-grid` | `#1A1C33` | |
| `--trend-axis` | `#5A5F85` | |
| `--trend-bg` | `#07070E` | |
| `--trend-pv-width` | `2px` | unchanged from the other themes |
| `--trend-sp-width` | `1.5px` | |
| `--trend-co-width` | `1.5px` | |
| `--trend-sp-dash` | `4 3` | |
| `--bar-track` | `#12142A` | |
| `--bar-fill` | `#00E5FF` | |
| `--bar-marker` | `#FFFFFF` | |

### 10.4 What the palette costs, measured

Discarding "green never means ok" inverts the salience ordering. OKLCH chroma:

| token | chroma | class |
|---|---|---|
| `--alarm-crit` `#FF2D6F` | 0.240 | alarm |
| **`--state-running` `#39FF88`** | **0.221** | chrome |
| `--alarm-adv` `#C77DFF` | 0.193 | alarm |
| `--alarm-warn` `#FFB020` | 0.165 | alarm |
| `--trace-co` `#FFA630` | 0.161 | chrome |

Salience headroom `min(alarm) − max(chrome)` = **−0.056**, against **+0.029** in Phosphor today.
A steady "running" loop is now louder than an ADVISORY and a WARNING alarm.

This is recorded, not litigated — it is the direct consequence of an explicit instruction. §10.5 is
the compensating mechanism.

### 10.5 Glow is the salience channel, not decoration

Glow is a visual dimension independent of hue and chroma. Reserving bloom for alarms and focus, and
denying it to steady state, keeps the alarm the only blooming thing on screen while the chrome stays
vibrant. This is priority 7 of the source skill: motion and emphasis must convey meaning.

Four new contract tokens. The contract requires every theme to declare every token, so `recorder`,
`phosphor` and `isa101` declare them too — three lines each.

| Token | `neon` | others |
|---|---|---|
| `--glow-alarm` | `0 0 12px rgba(255,45,111,0.55)` | `0 0 #0000` |
| `--glow-focus` | `0 0 10px rgba(0,229,255,0.65)` | `0 0 #0000` |
| `--glow-accent` | `0 0 14px rgba(0,229,255,0.45)` | `0 0 #0000` |
| `--glow-trace` | `8px` | `phosphor: 4px`, `recorder`/`isa101`: `0px` |

**The off-value is `0 0 #0000`, not `none`.** Corrected during planning after an agent compiled the
real `index.css` with `@tailwindcss/cli`. The `box-shadow` grammar is `none | <shadow>#`: `none` is
only valid as the *sole* value, so it cannot sit in a comma-separated list. Tailwind composes
`.ring-2` from five shadow variables, so a `none` glow token would make the whole declaration
invalid at computed-value time and **delete the focus ring in the three non-neon themes** — an
accessibility regression introduced by a token meant to be inert. `0 0 #0000` is Tailwind's own
registered initial value: valid in a list, renders nothing. `--glow-trace` is unaffected; it is a
`parseFloat` length and `0px` is correct.

Applied to: active and unacknowledged alarm rows, severity badges, the focus ring, the PV trace, and
primary-button hover/active. **Not** applied to: state dots, body text, card borders, headers, or
any static chrome.

`--glow-trace` carries `px` so `parseFloat` can read it, matching the existing `--trend-*-width`
convention that `tokenResolve.test.ts` already asserts.

**This deletes a hardcoded theme name.** `TrendPanel.tsx:170` and `TwinTrend.tsx:73` currently pass
`glow={theme === 'phosphor'}`. With `--glow-trace` as a token, glow becomes "the token is non-zero",
and neither component needs to know a theme id. One mechanism instead of two.

Any pulse on unacknowledged alarms must be suppressed under `prefers-reduced-motion`.

### 10.6 Typography

Only `--font-display` becomes per-theme. `--font-ui` (Archivo) and `--font-data` (Geist Mono) stay
in `tokens.css :root` — numerals and body text are identical in all four themes.

`--font-display` moves out of `:root` into all four `[data-theme]` blocks: three declare the current
Archivo stack verbatim, `neon` declares `'Orbitron Variable', 'Archivo Variable', system-ui, sans-serif`.

`type-display` reach, so the cost is justified: the wordmark (`AppShell.tsx:89`), every
`DialogTitle` (`Dialog.tsx:71`), and the `<h1>` of Login, Projects, Settings, Users, Connection and
Executive. Not a two-element change.

- Vendored as `src/assets/fonts/orbitron-latin-var.woff2`, `wght 400–900`, matching the
  `archivo-latin-var.woff2` naming convention. **No CDN import** — this product can run on an
  isolated network, so a Google Fonts `@import` would be a defect, not a style choice.
- **SIL OFL 1.1.** Redistributable in a commercial product, but the licence file must be committed
  alongside the font.
- Preloaded in `index.html` like the other three: `neon` is the default theme, so Orbitron is needed
  on first paint for a user with no stored preference.
- `.type-display` keeps `font-stretch: 125%`. Orbitron has no width axis, so it is inert there. Left
  as-is with a comment rather than introducing a token to express "this face has no width axis" —
  the token would cost more than the harmless no-op.

### 10.7 Touchpoints

| # | File | Change |
|---|---|---|
| 1 | `theme/contract.ts` | `THEME_IDS` gains `'neon'`; `CONTRACT_TOKENS` gains the four glow tokens |
| 2 | `theme/ThemeProvider.tsx` | `THEMES` gains the entry; `DEFAULT_THEME` becomes `'neon'` |
| 3 | `theme/themes.css` | new `[data-theme="neon"]` block; glow tokens and `--font-display` added to the other three |
| 4 | `theme/tokens.css` | `--font-display` removed from `:root` |
| 5 | `theme/themeContrast.ts` | `GateThemeId` gains `'neon'`; mirrored palette entry |
| 6 | `theme/themeContrast.test.ts:7` | gate theme list |
| 7 | `theme/isa101Mapping.test.ts:256` | expects exactly `['recorder','phosphor','isa101']`; `:192-200` forces every new contract token into `ISA101_EXPECTED` and `:213-215` into `MAPPING` as DERIVED — the four glow tokens and `--font-display` all trip these |
| 8 | `theme/isa101Mapping.test.ts:193` | type-token exception list drops to `--font-ui`, `--font-data` |
| 9 | `theme/fonts.test.ts:27` | counts `font-display: swap` — 3 becomes 4 |
| 10 | `index.html` | static `data-theme`, pre-paint `valid` array and fallback, font preload |
| 11 | `App.test.tsx:33` | default is no longer `recorder` |
| 12 | `e2e/themes.spec.ts:28` | `recorder is the default when nothing is stored` |
| 13 | `e2e/themes.spec.ts` | `THEMES` loop, `THEME_LABEL`, and new `dashboard-neon-<width>.png` baselines |
| 14 | `e2e/user-role.spec.ts:165` and `:185` | `:185` is the `menuitemradio` count 3 → 4; `:165` asserts the user menu's exact label array and breaks identically |
| 15 | `features/dashboard/TrendPanel.tsx:170`, `features/simulator/TwinTrend.tsx:73` | drop `theme === 'phosphor'` in favour of the token |
| 16 | `app/AppShell.test.tsx:171`, `:202` | theme `menuitemradio` list and length assertions |

### 10.8 Acceptance

- `themeContrast.test.ts` passes with `neon` in `GateThemeId` — no assertion relaxed, no floor lowered.
- `tokenResolve.test.ts` resolves all 48 contract tokens non-empty under all four themes.
- A fresh profile with empty `localStorage` paints `neon` before React mounts, with no flash of
  another theme.
- Orbitron renders in the wordmark and dialog titles; numerals stay Geist Mono in all four themes.
- No network request to `fonts.googleapis.com` or `fonts.gstatic.com` on any route.
- Glow appears on alarm rows, focus ring, PV trace and primary-button hover; it appears on no state
  dot, no card border and no header.
- `prefers-reduced-motion: reduce` suppresses any alarm pulse.

## 11. Test impact

### 11.1 Unit / component (Vitest, 746 passing at baseline)

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
| `theme/ThemeProvider.test.tsx` | Registry gains `neon`; the `defaults to recorder` case becomes `defaults to neon`. |
| `theme/themeContrast.test.ts:7` | Gate list gains `neon`. **No floor changes.** |
| `theme/isa101Mapping.test.ts` | `:256` block list becomes four entries and needs a `names[3]` assertion; `:192-200` and `:213-215` require every new contract token in `ISA101_EXPECTED` and `MAPPING`. |
| `theme/isa101Mapping.test.ts:193` | Type-token exception list drops `--font-display`, keeping `--font-ui` and `--font-data`; `ISA101_EXPECTED` gains `--font-display`. |
| `theme/fonts.test.ts:26-27` | `font-display: swap` count 3 → 4; a fourth `@font-face` and its preload are asserted. |
| `theme/tokenResolve.test.ts` | Runs over `THEME_IDS`, so it picks `neon` up automatically; the four glow tokens join `CONTRACT_TOKENS` and must resolve non-empty in all four themes. |
| `App.test.tsx:33` | Default `data-theme` becomes `neon`. |

There is no `app/routes.test.*`; `routes.tsx` is covered indirectly through `AppShell.test.tsx`,
which is where the `Executivo` nav assertion goes.

New logic requiring new tests: trend-selection persistence and roster reconciliation. Everything
else in this work is a move, a deletion or a style change.

### 11.2 Playwright (79 passing at baseline)

| Spec | Change |
|---|---|
| `e2e/login-dashboard.spec.ts` | Remove the `Comandos` button assertion and the `k`-opens-palette step. |
| `e2e/responsive.spec.ts` | Replace the `Comandos` target-size assertion; add the rail no-scroll assertion at each viewport. **Also `:36`**, which pins the faceplate to the RIGHT of the trend (`fp.x > t.x + t.width - 1`) — §4.2 moves it left, so it is restated as `fp.x + fp.width < t.x + 1`. Same strict side-by-side relation, opposite order: a restatement, not a weakening. |
| `e2e/target-size.spec.ts` | Remove `Comandos`; keep `Configurações`. |
| `e2e/user-role.spec.ts` | `:185` `menuitemradio` count 3 → 4; `:165` exact label array gains `Neon`. |
| `e2e/themes.spec.ts` | `THEMES` loop and `THEME_LABEL` gain `neon`; `recorder is the default when nothing is stored` becomes `neon`; new `dashboard-neon-<width>.png` baselines at all four breakpoints. |
| `e2e/multitrend.spec.ts` | Unchanged (`getByLabel('Loop 1 · PV')` preserved). New spec for persistence across a reload. |

### 11.3 `TEST_E2E.md`

The 50-procedure gate is the project's declared stop condition. **Seven** procedures are touched:
**five** have their text re-specified — E2E-006, E2E-036 and E2E-049 by the UI corrections, E2E-045
and E2E-046 by the theme — and **two** more, E2E-015 and E2E-043, keep their assertions verbatim and
need only fresh evidence images. The table below has six rows because the last row covers both
evidence-only procedures.

| # | Procedure | Resolution |
|---|---|---|
| **E2E-006** | *Command palette* | **Repurposed.** The feature is removed, so the procedure cannot pass or fail as written. The number is reused for: navigate to the executive dashboard from the top bar. This covers the risk the change actually introduces and keeps the gate at 50. |
| **E2E-036** | Executive KPIs | Steps say "open `/executive` from wordmark/palette" → becomes "from the top bar". Expected outcome unchanged. |
| **E2E-049** | Responsive | "≥1024 trend/faceplate side-by-side" remains true (faceplate is now the left column). Gains a **new, stricter** assertion: the faceplate rail's `scrollHeight === clientHeight`. |
| **E2E-045** | *Theme switch and persistence* | Steps cycle `Recorder→Phosphor→ISA-101` and expect "Recorder is default in a fresh browser storage profile". Becomes a four-theme cycle with `Neon` as the fresh-profile default. |
| **E2E-046** | *Phosphor-only halo and legacy migration* | Expects "static PV halo appears **only in Phosphor**". With `--glow-trace` as a token (§10.5) the halo is present wherever the token is non-zero — Phosphor **and** Neon. Restated as: halo present in Phosphor and Neon, absent in Recorder and ISA-101, still no `shadowBlur`-style frame collapse. The legacy `ocean` migration half is unaffected. |
| E2E-015 / E2E-043 | Faceplate consistency / user forbidden | Assertions remain valid; the evidence PNGs must be re-captured against the new layout and default theme. |

E2E-006's new text:

> **E2E-006 — Executive dashboard from the top bar**
> **Steps:** As `admin` and as `operador`, click `Executivo` in the top bar; confirm the route; click
> the wordmark.
> **Expected:** `Executivo` is present for both roles and navigates to `/executive`; the wordmark
> navigates to `/`.

No assertion anywhere in `TEST_E2E.md` is weakened. E2E-049 is strengthened, and E2E-046 becomes a
token-driven statement instead of a hardcoded theme name — which is the same tightening §10.5 makes
in the source.

## 12. Verification plan

Ordered. Each step must pass before the next.

1. `npm --prefix packages/smart_pid_web run typecheck` and `run lint`.
2. Vitest full run — must be green, with the amended and new tests described in §11.1.
3. Playwright — `cd packages/smart_pid_web && env -u CI npx playwright test`. **Not** the `browser`
   tool: it does not deliver CDP input to the page (documented harness defect) and has previously
   produced false "dead control" reports.
4. CDP measurement sweep for §4.4: 16 combinations (4 viewports × 2 roles × banner on/off),
   asserting `scrollHeight === clientHeight` on the rail and no page-level vertical scrollbar.
5. Re-confirm §8 after the fifth nav item lands: nav `scrollWidth` should read 236 px at a 320 px
   viewport, with page `scrollWidth - clientWidth` still 0. Any non-zero page overflow is a failure.
6. Theme gate for §10: `themeContrast.test.ts` green with `neon` in `GateThemeId`, and
   `tokenResolve.test.ts` green for all 48 contract tokens across all four themes.
7. Fresh-profile paint check: clear `localStorage`, load `/`, confirm `data-theme="neon"` before
   React mounts and no flash of another theme.
8. Network check on every route: zero requests to `fonts.googleapis.com` / `fonts.gstatic.com`.
9. Glow placement audit: bloom present on alarm rows, focus ring, PV trace and primary-button
   hover; absent on state dots, card borders and headers. Re-check with
   `prefers-reduced-motion: reduce` emulated — no alarm pulse.
10. New visual baselines `dashboard-neon-<width>.png` at the four `themes.spec.ts` breakpoints.
11. Manual re-run of the **seven** touched `TEST_E2E.md` procedures (§11.3, five re-specified plus
    two evidence-only) with fresh evidence PNGs.
12. Full backend suite is **not** re-run: this work touches no Python. Frontend-only.

## 13. Risks

| Risk | Mitigation |
|---|---|
| 1024×768 rail does not fit even after compaction — §4.3 leaves only **2 px** of margin (612 of 614) | The log-box floor is the adjustable term. If it still overflows, cut the floor further before touching any 44 px target, and report rather than silently shipping a scrollbar. |
| Compaction breaches the 44×44 px target (E2E-050) | Target size is a hard constraint. §4.4 rejects any lever that breaches it. |
| Moving AI config changes what an operator can reach | Both capabilities are admin-only and the dialog is read-only for `user`; §5.3 shows the role matrix is unchanged. Verified by the existing `user-role.spec.ts`. |
| `localStorage` restore resurrects a deleted loop | §9.2 reconciles against the live roster before rendering. |
| Reconciliation misfires while the roster query is pending | §9.2 gates on the roster having loaded. Explicit test case. |
| Removing `cmdk` or `Command.tsx` breaks an unrelated import | **Verified, not assumed:** `cmdk` is imported only by `components/Command.tsx`, and `Command.tsx` only by `app/AppShell.tsx` and its own test. Both deletions are closed. |
| Neon chrome buries an alarm — salience headroom is **−0.056** (§10.4) | Accepted consequence of an explicit instruction. Glow (§10.5) is the compensating channel: alarms and focus bloom, steady state never does. If an operator still misses alarms in review, the lever is `--state-running` chroma, not the alarm colours. |
| A neon palette fails WCAG | Already disproven: the §10.3 palette passes all 43 assertions of the existing gate. No floor is relaxed — a future tweak that fails the gate is rejected by CI, not by review. |
| Orbitron hurts legibility | It is display-only: wordmark, dialog titles, page `<h1>`. Numerals and body stay Geist Mono / Archivo in every theme (§10.6). |
| Vendoring a font bloats first paint | One variable `woff2`, latin subset, preloaded because `neon` is the default. `--font-ui` and `--font-data` are unchanged, so the other three themes gain one preload they do not render. Measure; drop the preload if it costs more than it saves. |
| The OFL licence is not shipped | The licence file is committed next to the font. Called out in §10.6 because it is a legal requirement of a commercial product, not a nicety. |

## 14. Decisions recorded

| # | Decision | Rationale |
|---|---|---|
| D1 | AI *config* moves to the loop dialog; AI *operation* stays on the faceplate | Only cut that fits the height budget without breaking touch targets; also puts configuration where configuration already lives. |
| D2 | Command palette removed entirely, not hidden behind Ctrl+K | A feature with no visible affordance and no exclusive destination is dead weight. |
| D3 | Distinct icons for the two `[cfg]` controls | Both are on screen at once and lead to different places. |
| D4 | `Executivo` last in the nav; wordmark → `/` | Loops is the operator's routine surface and the `/` route; the executive view is consultative. |
| D5 | `localStorage`, own key, reconciled | Matches `spid.theme`/`spid.preferences`; "persisted" that a reload erases is not persisted. |
| D6 | Title format `#3 · TIC-E2E` in both chart and selector | Tag for recognition, id to match URLs (`/?loop=3`) and toasts (`Malha #3`) and to disambiguate duplicate tags. |
| D7 | E2E-006 repurposed rather than deleted | Keeps the gate at 50 and covers the navigation path that replaced the palette. |
| D8 | A fourth theme, not a restyle of Phosphor | Keeps `recorder` and `isa101` as an untouched conformance path, which is what makes discarding ISA-101 in `neon` reversible and safe. |
| D9 | `neon` becomes the default | The directive is that the delivered look is weak; a theme nobody selects fixes nothing, and a demo must open on it. |
| D10 | WCAG gate applies to `neon`; ISA-101 doctrine does not | Different standards. ISA-101 is a domain convention the operator chose to drop; WCAG is the accessibility floor and priority 1 of the source skill. |
| D11 | Glow is semantic, never decorative | Compensates the inverted chroma ordering without desaturating the chrome, and satisfies the source skill's own priority-7 rule. |
| D12 | `--glow-trace` as a token replaces `theme === 'phosphor'` | Two components stop hardcoding a theme id; one mechanism serves both the existing Phosphor halo and the new one. |
| D13 | Only `--font-display` becomes per-theme | Smallest change that buys a distinct face. Numerals are the one thing an HMI must not make exotic, so `--font-data` stays global. |
| D14 | No CDN font import | The product can be deployed on an isolated network; a CDN dependency would be a runtime failure mode, not a style preference. |
