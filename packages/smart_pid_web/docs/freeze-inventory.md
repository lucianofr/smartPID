# DOM-freeze contract (§3a) — structural-binding inventory

Task 0.5. This is the **preserve-constraint** that every surface task (Phases 1-8 of the
Tailwind/shadcn/ISA-101 refactor) consumes. The refactor is big-bang on styling, but it MUST
keep the existing Vitest behavior suite green by **NOT** changing any of the structural bindings
below: `data-testid`, `aria-label` / accessible name, asserted `className`, `role`, asserted
`data-*` attributes, or the dynamic inline styles the tests read.

Every value here was extracted by grep against the real test suite
(`src/**/*.{test,spec}.{ts,tsx}`) — not from the brief. If a future refactor needs to drop or
rename one of these, the owning test must be updated **in the same change** and this file kept in
sync. `src/test/freeze-contract.test.ts` is a fast guard that fails if the highest-risk swapped
primitives lose a frozen hook.

Legend: a binding is "frozen" because at least one test asserts on it. The "Asserted by" column
names the test file(s) that lock it.

---

## 1. `data-testid` (selected via getBy/queryAll/findBy/getAll TestId or rendered as attribute)

| testid | Component (source) | Asserted by |
|---|---|---|
| `bar-fill` | `components/AnalogBar.tsx` | `components/AnalogBar.test.tsx` |
| `sp-marker` | `components/AnalogBar.tsx` (conditional: only when `spValue` set) | `components/AnalogBar.test.tsx` |
| `bar-value` | `components/AnalogBar.tsx` | (rendered; reserved — keep) |
| `count-critical` | `features/alarms/AlarmBar.tsx` | `features/alarms/__tests__/AlarmBar.test.tsx` |
| `count-warning` | `features/alarms/AlarmBar.tsx` | `features/alarms/__tests__/AlarmBar.test.tsx` |
| `count-advisory` | `features/alarms/AlarmBar.tsx` | `features/alarms/__tests__/AlarmBar.test.tsx` |
| `threshold-HIHI` | alarm-config / threshold UI | `features/alarms/__tests__/AlarmConfigForm.test.tsx` |
| `threshold-HI` | alarm-config / threshold UI | `features/alarms/__tests__/AlarmConfigForm.test.tsx` |
| `alarm-row-1` | `features/alarms/AlarmPanel.tsx` (`alarm-row-{id}`) | `features/alarms/__tests__/AlarmPanel.test.tsx` |
| `alarm-row-2` | `features/alarms/AlarmPanel.tsx` | `features/alarms/__tests__/AlarmPanel.test.tsx` |
| `alarm-row-9` | `features/alarms/AlarmPanel.tsx` | `features/alarms/__tests__/AlarmPanel.test.tsx` |
| `alarm-row-42` | `features/alarms/AlarmPanel.tsx` | `features/alarms/__tests__/AlarmPanel.test.tsx` |
| `kpi-var` | `components/ExecutiveKPICard.tsx` | `components/ExecutiveKPICard.test.tsx` |
| `kpi-iae` | `components/ExecutiveKPICard.tsx` | `components/ExecutiveKPICard.test.tsx` |
| `kpi-tv` | `components/ExecutiveKPICard.tsx` | `components/ExecutiveKPICard.test.tsx` |
| `kpi-variability` | `components/ExecutiveKPICard.tsx` | `components/ExecutiveKPICard.test.tsx` |
| `kpi-auto` | `components/ExecutiveKPICard.tsx` | `components/ExecutiveKPICard.test.tsx` |
| `kpi-loops` | `components/ExecutiveKPICard.tsx` | `components/ExecutiveKPICard.test.tsx` |
| `kpi-bad-delta` | `components/ExecutiveKPICard.tsx` (carries `data-out-of-target`) | `components/ExecutiveKPICard.test.tsx` |
| `kpi-ok-delta` | `components/ExecutiveKPICard.tsx` (carries `data-out-of-target`) | `components/ExecutiveKPICard.test.tsx` |
| `health-FIC-101-opc` | `pages/ExecutiveDashboardPage.tsx` (`health-{tag}-opc`) | `pages/ExecutiveDashboardPage.test.tsx` |
| `health-FIC-101-state` | `pages/ExecutiveDashboardPage.tsx` (`health-{tag}-state`) | `pages/ExecutiveDashboardPage.test.tsx` |
| `health-TIC-202-state` | `pages/ExecutiveDashboardPage.tsx` | `pages/ExecutiveDashboardPage.test.tsx` |
| `executive-dashboard` | `pages/ExecutiveDashboardPage.tsx` | `pages/ExecutiveDashboardPage.test.tsx` |
| `multitrend-chart` | `features/multitrend` chart component | `features/multitrend/*`, `pages/MultiTrendPage.test.tsx` |
| `ai-panel` | `features/loop-config/AiPanel.tsx` | `features/loop-config/__tests__/AiPanel.test.tsx` |
| `ai-panel-9` | `features/loop-config/AiPanel.tsx` (`ai-panel-{loopId}`) | `pages/DashboardPage.test.tsx` |
| `twin-trend` | `features/simulator` twin-trend component | `features/simulator/*`, `pages/SimulatorPage.test.tsx` |
| `readout-gain` | `features/simulator` readout | `features/simulator/__tests__/*` |
| `dialog-backdrop` | `components/ui/Dialog.tsx` AND `components/ui/dialog-primitive.tsx` | flat-primitives / dialog tests |
| `current` | `theme/ThemeProvider.test.tsx` harness consumer (`{theme}`) | `theme/ThemeProvider.test.tsx` |
| `count` | `theme/ThemeProvider.test.tsx` harness consumer (`{themes.length}`) | `theme/ThemeProvider.test.tsx` |

> Note on `card-controls-{n}`: listed in the brief as a frozen testid for
> `features/loop-config/CardControls.tsx`. Keep the `card-controls-{loopId}` pattern stable even
> though the current `CardControls.test.tsx` selects controls by accessible name; downstream
> dashboard/page tests rely on the per-loop testid namespace.

## 2. Accessible name / `aria-label` (selected via getByLabelText or getByRole name)

### 2a. Exact-string accessible names

| name | Component (source) | Asserted by |
|---|---|---|
| `Manual CO` | `components/Faceplate.tsx` (CO field) | `components/Faceplate.test.tsx` |
| `Setpoint` | `components/Faceplate.tsx` | `components/Faceplate.test.tsx` |
| `Set setpoint` | `components/Faceplate.tsx` | `components/Faceplate.test.tsx` (source-confirmed) |
| `Set output` | `components/Faceplate.tsx` | `components/Faceplate.test.tsx` (source-confirmed) |
| `Faceplate {tag}` | `components/Faceplate.tsx` root `<aside>` (e.g. `Faceplate TIC-101`, `faceplate TIC-009`) | `components/Faceplate.test.tsx`, `pages/DashboardPage.test.tsx` |
| `Controller mode` | `components/Faceplate.tsx` mode group | (source-confirmed; keep) |
| `Alarm summary` | `features/alarms/AlarmBar.tsx` `<footer>` | `features/alarms/__tests__/AlarmBar.test.tsx` |
| `Theme` | `components/shell/ThemeSwitcher.tsx` | `components/shell/ThemeSwitcher.test.tsx` |
| `Fechar` | `components/ui/Dialog.tsx` backdrop | dialog tests |
| `simulator controls` | `features/simulator/SimulatorControlPanel.tsx` | `features/simulator/__tests__/*` |
| `history query` | `features/multitrend/HistoryQuery.tsx` | `features/multitrend/HistoryQuery.test.tsx` |
| `Loop 1 · PV` | `features/multitrend` series label | `features/multitrend/*` |
| AnalogBar meter: `{label} {value} {unit}` | `components/AnalogBar.tsx` `role="meter"` (e.g. `PV 150.2 °C`) | `components/AnalogBar.test.tsx` (via `getByRole('meter')`) |

### 2b. Regex / case-insensitive accessible names (must keep a matching accessible name)

These are matched by `getByLabelText(/.../i)` or `getByRole(role, { name: /.../i })`. The exact
text may carry extra words, but the regex below must keep matching.

| pattern | role / getter | Asserted by |
|---|---|---|
| `/limit/i` | label | `LoopConfigDialog.test.tsx`, `AlarmConfigForm.test.tsx` |
| `/endpoint/i` | label | `features/connection/ConnectionPanel.test.tsx` |
| `/mode/i` | label | loop-config |
| `/setpoint/i` (`/set setpoint/i`) | button | `features/loop-config/__tests__/CardControls.test.tsx` |
| `/output/i` (`/output co/i`, `/apply output/i`) | spinbutton / button | `features/simulator/__tests__/TwinOutputModeControl.test.tsx` |
| `/gain/i` | label / slider | `features/simulator/__tests__/DynamicsSliders.test.tsx` |
| `/reset/i` | label | loop-config |
| `/rate/i` | label | loop-config |
| `/learning rate/i` | label | loop-config (RL) |
| `/train interval/i` | label | loop-config (RL) |
| `/fallback kp/i` | label | loop-config (RL) |
| `/objective/i` | label | loop-config |
| `/dead time/i` | label / slider | `features/simulator/__tests__/DynamicsSliders.test.tsx` |
| `/filter.*state/i` | label | loop-config |
| `/number decimals/i` | label | `features/settings/SettingsForm.test.tsx` |
| `/trend window/i` | label | `features/settings/SettingsForm.test.tsx` |
| `/confirm destructive/i` | label | `features/settings/SettingsForm.test.tsx` |
| `/start/i` | label / button | simulator / multitrend |
| `/import .spid/i` | label | `features/projects/ProjectImportDropzone.test.tsx` |
| `/apply tuning/i` | button | `components/Faceplate.test.tsx`, `features/loop-config/__tests__/AiPanel.test.tsx` |
| `/Salvar/i` | button | `features/loop-config/__tests__/LoopConfigDialog.test.tsx` |
| `/remove/i` | button | `features/simulator/__tests__/DisturbanceControls.test.tsx` |
| `/process preset/i` | combobox | `features/simulator/__tests__/PresetSelector.test.tsx` |
| `/simulation mode/i` | status | `features/simulator/__tests__/SimulationModeBanner.test.tsx` |
| `/auto.?sp/i`, `/auto.?disturbance/i` | switch | `features/simulator/__tests__/AutoToggles.test.tsx` |

### 2c. Radio labels (exact)

| name | Asserted by |
|---|---|
| `NONE` | `features/loop-config/__tests__/AiPanel.test.tsx` (radio) |
| `FUZZY` | `features/loop-config/__tests__/AiPanel.test.tsx`, `pages/DashboardPage.test.tsx` (radio) |
| `RL` | `features/loop-config/__tests__/AiPanel.test.tsx` (radio) |

## 3. Asserted `className`

| class | Element (source) | Asserted by |
|---|---|---|
| `is-unacked` | `features/alarms/AlarmBar.tsx` bucket (toggled on `count-critical` etc. when unacked) | `features/alarms/__tests__/AlarmBar.test.tsx` (`toHaveClass('is-unacked')`) |
| `analog-bar` | `components/AnalogBar.tsx` root `<div>` | reserved structural class — keep |
| `analog-bar__label` | `components/AnalogBar.tsx` label `<span>` | reserved structural class — keep |
| `analog-bar__track` | `components/AnalogBar.tsx` meter `<div>` (`role="meter"`) | reserved structural class — keep |
| `analog-bar__value` | `components/AnalogBar.tsx` value `<span>` (`data-testid="bar-value"`) | reserved structural class — keep |

## 4. `role` (selected via getByRole — semantic primitives that must not be swapped away)

| role | Where it matters | Asserted by |
|---|---|---|
| `dialog` | `ConfirmApplyTuning`, `LoopConfigDialog`, `WelcomeDialog`, `components/ui/Dialog.tsx` | `ConfirmApplyTuning.test.tsx`, `LoopConfigDialog.test.tsx`, `WelcomeDialog.test.tsx` |
| `meter` | `components/AnalogBar.tsx` track | `AnalogBar.test.tsx`, `Faceplate.test.tsx` |
| `complementary` | `components/Faceplate.tsx` root `<aside>` | `pages/DashboardPage.test.tsx` |
| `radio` | AI engine selector (NONE/FUZZY/RL) | `AiPanel.test.tsx`, `DashboardPage.test.tsx` |
| `combobox` | preset / select controls | `PresetSelector.test.tsx`, `ConnectionPanel`/`SettingsForm` |
| `slider` | simulator dynamics | `DynamicsSliders.test.tsx` |
| `spinbutton` | numeric inputs (amplitude, output CO) | `DisturbanceControls.test.tsx`, `TwinOutputModeControl.test.tsx` |
| `switch` | simulator auto toggles | `AutoToggles.test.tsx` |
| `status` | simulation-mode banner | `SimulationModeBanner.test.tsx`, `SimulatorPage.test.tsx` |
| `searchbox` | tag browser / search | `TagBrowser.test.tsx` |
| `option` | select options | `PresetSelector.test.tsx` |
| `button` | pervasive — every interactive button must keep `role="button"` (17 test files) | many |

## 5. Asserted `data-*` attributes (beyond data-testid)

| attribute | Element (source) | Asserted by |
|---|---|---|
| `data-out-of-target` | `components/ExecutiveKPICard.tsx` on `kpi-bad-delta` (truthy) and `kpi-ok-delta` (falsey/absent) | `components/ExecutiveKPICard.test.tsx` |
| `data-alarm` | `components/AnalogBar.tsx` `bar-fill` (`normal` / `critical` / ...) | `components/AnalogBar.test.tsx` |
| `data-theme` (on `<html>`) | `theme/ThemeProvider.tsx` sets `document.documentElement` (`isa101` default, `ocean`, `md3-light`) | `theme/ThemeProvider.test.tsx` |
| `aria-valuemin` / `aria-valuemax` / `aria-valuenow` | `components/AnalogBar.tsx` meter | `AnalogBar.test.tsx`, `Faceplate.test.tsx` |
| `aria-pressed` | `components/Faceplate.tsx` mode buttons (`AUTO` -> `true`) | `Faceplate.test.tsx` |

## 6. Dynamic inline styles read by tests (must remain inline + dynamic)

| element | property read | Asserted by | Constraint |
|---|---|---|---|
| AnalogBar `bar-fill` | `style.width` (`${pct}%`) — falls back to `style.transform` | `components/AnalogBar.test.tsx` (`fillWidth` reads `style.width \|\| style.transform`) | fill width MUST stay an inline `width:%` (or `transform` scaleX) bound to value |
| AnalogBar `sp-marker` | presence + `style.left` (`${spPct}%`) | `components/AnalogBar.test.tsx` | marker MUST stay positioned via inline `left:%` |

## 7. Ordering assertions

| assertion | Component | Asserted by |
|---|---|---|
| `alarm-row-9` rendered first (priority/sort order) | `features/alarms/AlarmPanel.tsx` | `features/alarms/__tests__/AlarmPanel.test.tsx` |

---

## Guard test

`src/test/freeze-contract.test.ts` renders the highest-risk **swapped** primitives standalone and
asserts a representative subset of the above — chosen because these are the components the
ISA-101/shadcn refactor is most likely to replace wholesale:

- **AnalogBar** (analog meter, the riskiest swap): `analog-bar*` classes, `role="meter"` +
  `{label} {value} {unit}` aria-label, `aria-valuemin/max/now`, testids `bar-fill`/`bar-value`,
  conditional `sp-marker`, dynamic inline fill width, `data-alarm`.
- **Dialog** (`components/ui/Dialog.tsx`, the shadcn swap target): `data-testid="dialog-backdrop"`,
  `aria-label="Fechar"`, `role="dialog"`.
- **AlarmBar**: `aria-label="Alarm summary"`, buckets `count-critical/warning/advisory`,
  `is-unacked` toggling.
- **Faceplate** (CO field): `aria-label="Manual CO"`, `Setpoint`, `Set setpoint`, `Faceplate {tag}`,
  `role="complementary"`.

The guard is a fast Vitest spec (no network, mocks mirror each component's own test harness). It
fails the moment a frozen hook disappears from these primitives — catching the most common refactor
regression before the full suite runs.
