# Web Frontend Refactor — Tailwind v4 + shadcn, ISA-101-first — Implementation Plan

> For agentic workers: execute with the **subagent-driven-development** skill (independent tasks, current session) or **executing-plans** (separate session + review checkpoints). Work the `- [ ]` steps top to bottom; do not skip the run-fails / run-passes verification sub-steps. One commit per task (or per checkpoint where noted). Mark each box `[x]` as you finish it.

- **Date:** 2026-06-20
- **Authority spec (follow exactly):** `docs/superpowers/specs/2026-06-20-web-frontend-tailwind-shadcn-isa101-refactor-design.md`
- **Amends:** `docs/superpowers/specs/2026-06-18-web-frontend-design-system-design.md` (design-system authority of tokens/components/themes)
- **Review record:** `.claude/reports/review/review-web-refactor-spec-20260620.md` (NOTE: file is present but **empty/0 bytes** on this branch — the binding review constraints are folded into the spec §3a/§4/§9 and into this plan's Global Constraints; treat the spec as the constraint source)
- **App root:** `packages/smart_pid_web/`
- **Worktree:** `.worktrees/web-isa101-refactor/`

## Goal

Re-engineer the `smart_pid_web` styling layer from **121 inline `style={{}}` blocks across 19 components + 24 per-component `.css` files** to **Tailwind v4 (CSS-first) utilities/`@apply` bound to the existing CSS-var token contract**, plus **shadcn primitives restyled flat (ISA-101)**, while (a) preserving every behavior test green via the hardened DOM-freeze rule (§3a), (b) raising execution to the instrument-grade craft standard (§6) including mandated missing-states (§6a), and (c) keeping the 5 themes (`isa101`, `dark-room`, `md3-dark`, `md3-light`, `ocean`) working through `[data-theme]` on `<html>`. Big-bang sequencing hardened with per-surface Vitest-green checkpoints.

## Architecture

- **Token bridge.** A single global stylesheet (`src/index.css`) does `@import "tailwindcss"` then a `@theme inline { … }` block mapping Tailwind utility namespaces onto the **existing** vars from `src/theme/tokens.css` + `src/theme/themes.css` (e.g. `--color-bg: var(--bg)`, `--color-surface: var(--surface)`, `--color-text: var(--text)`, `--color-alarm-critical: var(--alarm-critical)`, `--radius-card: var(--radius-card)`, `--font-ui: var(--font-ui)`, spacing `--spacing-*` ← `--sp-*`). `@theme inline` (never plain `@theme`) is mandatory so utilities resolve to `var(--…)` at runtime and theme swap keeps working.
- **Primitives.** shadcn components (Dialog, DropdownMenu, Tabs, Select, Tooltip, Switch, Slider, Command, Toast) installed and restyled flat at install (`--radius: 0` default, MD3 radius via token override; remove every `shadow-*`; recolor to token utilities). Hand-rolled `src/components/ui/Dialog.tsx` is replaced by the shadcn Dialog (the existing Dialog hardcodes `boxShadow: '0 8px 32px rgba(0,0,0,0.5)'` + `background: rgba(0,0,0,0.6)` backdrop → fails flat-lint day one; the swap is the fix).
- **Data layer untouched.** TanStack Query, WS realtime envelope, uPlot, REST contract, routes — no change. uPlot styled via JS opts in `src/lib/uplotTheme.ts` only.
- **Freeze.** All `data-testid` / `aria-label` / asserted `className` / dynamic inline-style hooks preserved (full inventory in Task 0.5).

## Tech Stack

- React **18.3.1** (pinned; not 19). `react`/`react-dom` `^18.3.1` already in `package.json`. `@types/react@^18.3.x`.
- **Tailwind v4** CSS-first: `tailwindcss@^4` + `@tailwindcss/vite@^4` (Vite plugin, not PostCSS). Activated via `@import "tailwindcss"` + `@theme inline`.
- **shadcn** (CLI `shadcn@latest`, style `new-york`, `cssVariables: true`, `tailwind.config: ""`). Deps: `class-variance-authority@^0.7.1`, `clsx@^2.1.1`, `tailwind-merge@^3.0.1`, unified **`radix-ui@^1.4.3`** (React-18-compatible line — keep `forwardRef` on wrapped primitives), `cmdk` (Command), `lucide-react` (icons). `cn` util at `src/lib/utils.ts`.
- Contrast gate tool: **`wcag-contrast`** (npm) + an **APCA** cross-check (`apca-w3`), run in the existing Vitest+jsdom job.
- Existing toolchain: Vite 5.4, Vitest 2.0.5 (jsdom 24), Playwright 1.46, TypeScript 5.5, ESLint 9 flat config (`eslint.config.js`), `@vitejs/plugin-react`.
- Test setup: `src/test/setup.ts` (jest-dom, canvas/ResizeObserver/matchMedia stubs).

## Global Constraints (copied from spec — non-negotiable)

1. **React 18.3, not 19.** Pin **Radix versions compatible with React 18**; keep `forwardRef` on every wrapped primitive.
2. **Tailwind v4 CSS-first `@theme inline`** for ALL color/radius/font tokens. A non-inline `@theme` token emits a fixed build-time value and silently breaks runtime theme swap — forbidden for color/radius/font.
3. **No raw color/hex utilities in markup.** Token utilities only (`bg-surface text-text border-border`). A lint rule blocks non-token color utilities and hex.
4. **Flat — zero `box-shadow`/gradient/bevel** anywhere **except the single modal backdrop scrim** (the one sanctioned `rgba`). Lint-enforced.
5. **Token-contract names are law** — refactor *consumes*, never *renames* any `--token`. 5 themes preserved; MD3 radius/font overrides resolve through the token layer. Self-hosted IBM Plex Sans/Mono (MD3 → Roboto), no CDN.
6. **Hardened DOM-freeze rule (§3a):** preserve every asserted `className` (via `@apply`), every `data-testid`/`aria-label`/`data-*`, keep dynamic inline styles (`AnalogBar width:${pct}%`, fill markers), map native semantics lost in composites (Radix Slider `disabled` → `aria-disabled`/`data-disabled` so `getByLabelText('Manual CO').toBeDisabled()` still passes), add no new wrapper `<div>`s that break role/structure queries.
7. **Branch:** `refactor/web-tailwind-shadcn-isa101` (off `main`, this worktree). **Never commit to `main`.**
8. **Spec-first governance:** update the design-system authority spec + touched identity docs **in the same change set** as the UI change. No UI commit without it.
9. **Per-surface green checkpoints**, fixed order Shell → Cards/AnalogBar → Faceplate → Alarms → Trends → Exec → Login → Peripheral → Polish; each phase independently Vitest-green; snapshots blessed group-by-group; rollback = revert-to-last-green-commit.
10. **Two-tier visual stance:** operator situational-awareness screens (dashboard, faceplate, alarms, trends) = strict ISA-101; **only login + executive dashboard** get modern latitude (§6b). Everything else strict.

### Commands (project npm scripts)

| Purpose | Command | Expected |
|---|---|---|
| Unit/integration tests | `npm run test` (`vitest run`) | all suites pass |
| Single file | `npm run test -- src/path/File.test.tsx` | that suite passes |
| Lint | `npm run lint` (`eslint .`) | 0 errors |
| Typecheck + build | `npm run build` (`tsc -b && vite build`) | build OK, bundle within §12 budget |
| E2E / visual snapshots | `npm run test:e2e` (`playwright test`) | snapshots match |
| Re-bless snapshots | `npm run test:e2e -- --update-snapshots` | regenerated |

Run all commands from `packages/smart_pid_web/`.

---

# Phase 0 — Foundation (must end fully green before any surface work)

## Task 0.1 — Pre-req 0: reconcile desynced specs + verify branch/tooling (BLOCKING)

**This is a HARD precondition (spec §8 Pre-req 0). No implementation task may start until it is done.**

**Files**
- Verify (no edit): `packages/smart_pid_web/package.json`, `packages/smart_pid_web/vite.config.ts`
- Doc (Modify on `main`, via separate PR/cherry-pick): bring the design-system authority spec `docs/superpowers/specs/2026-06-18-web-frontend-design-system-design.md` (+ the refactor spec) onto `main`.

**Interfaces** — Consumes: governance rule §8. Produces: a `main` that contains the design-system authority spec so the spec-first rule is satisfiable.

- [ ] Confirm current branch is `refactor/web-tailwind-shadcn-isa101` in this worktree: `git rev-parse --abbrev-ref HEAD` → expect `refactor/web-tailwind-shadcn-isa101` (if not, `git switch -c refactor/web-tailwind-shadcn-isa101` off `main`).
- [ ] Verify build tooling present: `test -f packages/smart_pid_web/package.json && grep -q '"vite"' packages/smart_pid_web/package.json && echo OK` → `OK`.
- [ ] Check whether the design-system authority spec exists on `main`: `git ls-tree -r --name-only main -- docs/superpowers/specs/ | grep design-system` → if **absent**, this is the blocking gap.
- [ ] **Resolve the blocking gap (documented, off this branch):** open a PR/cherry-pick that lands `docs/superpowers/specs/2026-06-18-web-frontend-design-system-design.md` and `docs/superpowers/specs/2026-06-20-web-frontend-tailwind-shadcn-isa101-refactor-design.md` onto `main`. Do not merge UI code until this lands. Record completion here with the PR/commit SHA: `__________`.
- [ ] Note in `.claude/docs/estado-atual.md` that Pre-req 0 is satisfied (CLAUDE.md state-save rule).
- [ ] Commit (docs only): `docs(web): satisfy Pre-req 0 — land design-system + refactor specs on main`.

## Task 0.2 — Install + wire Tailwind v4 (CSS-first) with the `@theme inline` token bridge

**Files**
- Modify: `packages/smart_pid_web/package.json` (deps)
- Modify: `packages/smart_pid_web/vite.config.ts` (add `@tailwindcss/vite`)
- Create: `packages/smart_pid_web/src/index.css` (global: `@import "tailwindcss"` + `@theme inline` bridge + `@import` of existing `theme/tokens.css` & `theme/themes.css`)
- Modify: `packages/smart_pid_web/src/main.tsx` (add `import './index.css'`)
- Create/Test: `packages/smart_pid_web/src/theme/tokenBridge.test.ts`

**Interfaces** — Consumes: existing vars in `src/theme/tokens.css` (`--sp-1..12`, `--radius-card/control/pill`, `--font-ui/--font-data`, `--text-2xs..3xl`, `--fw-*`, `--dur-*`, `--ease-*`, `--border-w`) and `src/theme/themes.css` (`[data-theme='…'] { --bg --surface --text --alarm-critical … }`). Produces: Tailwind utility namespaces resolving to `var(--…)` at runtime.

- [ ] Write failing test `tokenBridge.test.ts`: assert `src/index.css` exists, contains `@import "tailwindcss"`, contains a `@theme inline` block (regex `/@theme\s+inline\s*\{/`), and that the block maps at least `--color-bg: var(--bg)`, `--color-surface: var(--surface)`, `--color-text: var(--text)`, `--color-alarm-critical: var(--alarm-critical)`, `--radius-card: var(--radius-card)`, `--font-ui: var(--font-ui)`. Also assert there is **no** plain `@theme {` (non-inline) defining a color/radius/font token.
- [ ] Run `npm run test -- src/theme/tokenBridge.test.ts` → **fails** (file absent).
- [ ] Install: `npm i -D tailwindcss@^4 @tailwindcss/vite@^4`.
- [ ] Edit `vite.config.ts`: add `import tailwindcss from '@tailwindcss/vite'` and put `tailwindcss()` first in `plugins: [tailwindcss(), react()]`. Leave `server`/`proxy` untouched.
- [ ] Create `src/index.css`: line 1 `@import "tailwindcss";`, then `@import "./theme/tokens.css";` and `@import "./theme/themes.css";`, then a `@theme inline { … }` block bridging the contract (colors → `var(--bg|surface|surface-container|surface-container-high|field-bg|text|text-secondary|text-disabled|border|border-strong|divider|alarm-critical|alarm-warning|alarm-diag|bar-fill|bar-track)`, radius → `var(--radius-card|--radius-control|--radius-pill)`, fonts → `var(--font-ui|--font-data)`, spacing `--spacing-*` ← `--sp-*`, durations/eases). Do not redefine any contract var; only map utility names onto them.
- [ ] Add `import './index.css';` to `src/main.tsx` (before `App`). Keep `App`'s own stylesheet imports working.
- [ ] Run `npm run test -- src/theme/tokenBridge.test.ts` → **passes**.
- [ ] Run `npm run build` → builds; Tailwind compiles; no PostCSS error. Confirm `dist` produced.
- [ ] Commit: `feat(web): add Tailwind v4 CSS-first with @theme inline token bridge`.

## Task 0.3 — Install + restyle-flat shadcn primitives (React-18-compatible Radix)

**Files**
- Modify: `package.json` (shadcn deps)
- Create: `src/lib/utils.ts` (`cn`), `components.json`
- Create: `src/components/ui/dialog.tsx`, `dropdown-menu.tsx`, `tabs.tsx`, `select.tsx`, `tooltip.tsx`, `switch.tsx`, `slider.tsx`, `command.tsx`, `toast.tsx` (+ `toaster.tsx`/`use-toast` as the CLI emits)
- Create/Test: `src/components/ui/__tests__/flat-primitives.test.tsx`

**Interfaces** — Produces: flat, token-colored, `radius-0`-default shadcn primitives keeping `forwardRef`. Consumes: token bridge from 0.2.

- [ ] Write failing test `flat-primitives.test.tsx`: render shadcn `Dialog` (open) + `Slider` + `Switch`; assert (a) no rendered element has an inline/class `box-shadow` except an element carrying `data-testid="dialog-backdrop"` or the scrim role; (b) `Slider` thumb exposes `aria-disabled` when `disabled`; (c) wrapped primitives still forward refs (`expect(ref.current).not.toBeNull()`).
- [ ] Run `npm run test -- src/components/ui/__tests__/flat-primitives.test.tsx` → **fails**.
- [ ] Install deps: `npm i class-variance-authority@^0.7.1 clsx@^2.1.1 tailwind-merge@^3.0.1 radix-ui@^1.4.3 cmdk lucide-react`. (Unified `radix-ui` line is React-18-compatible; do NOT pull `@radix-ui/*@latest` which may require React 19.) Verify peer resolution: `npm ls react` → single `react@18.3.x`.
- [ ] Create `src/lib/utils.ts` with `cn` (`twMerge(clsx(inputs))`).
- [ ] Create `components.json` per shadcn Vite+v4 shape: `style:"new-york"`, `rsc:false`, `tsx:true`, `tailwind.config:""`, `tailwind.css:"src/index.css"`, `cssVariables:true`, aliases `ui:"@/components/ui"`, `lib:"@/lib"`, `utils:"@/lib/utils"`. Add `@`→`src` path alias in `vite.config.ts` (`resolve.alias`) and `tsconfig` `paths` if not present.
- [ ] Add each primitive: `npx shadcn@latest add dialog dropdown-menu tabs select tooltip switch slider command toast`.
- [ ] **Restyle flat at install** in each generated `ui/*.tsx`: remove every `shadow-*`/`drop-shadow-*` class; set default radius to `rounded-none` (token `--radius:0`; MD3 picks up radius via the token override, no per-component override); replace any literal color classes (`bg-white`, `text-zinc-*`, `bg-black/80`, etc.) with token utilities (`bg-surface`, `text-text`, `bg-surface-container-high`, `border-border`). **Dialog overlay/scrim is the ONE allowed `rgba`** — keep it; tag it `data-testid="dialog-backdrop"` (see Task 8.x) and exempt it from flat-lint.
- [ ] Run `npm run test -- src/components/ui/__tests__/flat-primitives.test.tsx` → **passes**.
- [ ] Run `npm run lint` and `npm run build` → green.
- [ ] Commit: `feat(web): add shadcn primitives restyled flat (radius 0, no shadow, token colors)`.

## Task 0.4 — Lint rules: no-raw-color + flat/no-box-shadow

**Files**
- Modify: `packages/smart_pid_web/eslint.config.js`
- Create/Test: `packages/smart_pid_web/scripts/lint-rules.test.ts` (or a Vitest that shells `eslint` against fixtures) + fixtures under `packages/smart_pid_web/src/__lintfixtures__/`

**Interfaces** — Consumes: ESLint 9 flat config (`tseslint.config(...)`). Produces: two enforced rules — (a) no raw color/hex utility or hex literal in JSX `className`/`style`; (b) no `box-shadow`/`shadow-*`/gradient except files explicitly allow-listed (the shadcn Dialog scrim).

- [ ] Write failing test: a fixture component with `className="bg-[#fff] text-red-500"` and one with `style={{ boxShadow: '0 1px 2px #000' }}` must each produce an eslint error; a fixture using `className="bg-surface text-text"` must produce none; the Dialog scrim element (allow-listed) must produce none.
- [ ] Run the lint-rules test → **fails** (rules not present).
- [ ] Implement via `no-restricted-syntax` selectors in `eslint.config.js`: block JSX `className` `Literal`/`TemplateLiteral` matching hex `#[0-9a-fA-F]{3,8}`, arbitrary color utilities `(?:bg|text|border|fill|stroke|ring|from|via|to)-\[`, named tailwind palette utilities `(?:bg|text|border|fill|stroke|ring)-(?:red|blue|green|zinc|slate|gray|neutral|…)-\d`; and block `box-shadow`/`boxShadow`/`shadow-(sm|md|lg|xl|2xl)`/`drop-shadow`/`linear-gradient`/`radial-gradient` in `className` and inline `style`. Allow-list the scrim via an `overrides`/`files` block scoped to `src/components/ui/dialog.tsx` (or a marked line-disable on the single scrim element only).
- [ ] Run the lint-rules test → **passes**. Run `npm run lint` on the whole repo → expect (intentionally) the pre-existing inline-style/`Dialog.tsx` violations to surface; document the count (this is the "fails day one" baseline that surface tasks clear). Do not block this task on those.
- [ ] Commit: `feat(web): enforce no-raw-color + flat (no box-shadow) lint rules`.

## Task 0.5 — Structural-binding assert inventory (DOM-freeze contract, §3a)

**Files**
- Create: `packages/smart_pid_web/docs/freeze-inventory.md` (machine-checkable list)
- Create/Test: `packages/smart_pid_web/src/test/freeze-contract.test.ts`

**Interfaces** — Produces: a frozen list of every structural binding asserted in tests; each surface task consumes it as a preserve-constraint. The contract test fails if any frozen hook disappears.

- [ ] Generate the inventory by grep (already mapped): the complete asserted-hook set is —
  - `data-testid`: `bar-fill`, `sp-marker`, `bar-value`, `count-critical`, `count-warning`, `count-advisory`, `threshold-HIHI`, `threshold-HI`, `alarm-row-{n}`, `kpi-var`, `kpi-iae`, `kpi-tv`, `kpi-variability`, `kpi-auto`, `kpi-loops`, `kpi-bad-delta`, `kpi-ok-delta`, `health-FIC-101-opc`, `health-FIC-101-state`, `health-TIC-202-state`, `executive-dashboard`, `multitrend-chart`, `ai-panel`, `ai-panel-{n}`, `card-controls-{n}`, `twin-trend`, `readout-gain`, `dialog-backdrop`, `current`, `count` (ThemeProvider).
  - `aria-label`: `"Manual CO"`, `"Setpoint"`, `"Set setpoint"`, `"Alarm summary"`, `"Theme"`, `"Fechar"`, `"Faceplate {tag}"`, `"simulator controls"`, `"history query"`, AnalogBar meter `"{label} {value} {unit}"`.
  - asserted `className`: `is-unacked` (on `count-critical` bucket), `analog-bar`, `analog-bar__label`, `analog-bar__track`.
  - `getByRole('dialog')`: ConfirmApplyTuning, LoopConfigDialog, WelcomeDialog.
  - data-attr asserts: `data-out-of-target` on `kpi-bad-delta`/`kpi-ok-delta`; `data-testid` ordering on `alarm-row-9` first.
  - regex-label getters (must keep an accessible name matching): `/limit/i`, `/endpoint/i`, `/mode/i`, `/setpoint/i`, `/output/i`, `/gain/i`, `/reset/i`, `/rate/i`, `/learning rate/i`, `/train interval/i`, `/fallback kp/i`, `/objective/i`, `/dead time/i`, `NONE`/`FUZZY`/`RL` radios, `/filter.*state/i`, `/number decimals/i`, `/trend window/i`, `/confirm destructive/i`, `/start/i`, `/limit/i`, `Loop 1 · PV`, buttons `/apply tuning/i`, `/Salvar/i`, `/remove/i`, `/apply output/i`.
- [ ] Write `freeze-contract.test.ts` that imports the rendered output of the high-risk swapped components (AnalogBar, AlarmBar, Faceplate CO field, shadcn Dialog) and asserts the testids/aria-labels above are present — a fast guard that runs in the normal Vitest job.
- [ ] Run `npm run test -- src/test/freeze-contract.test.ts` → **passes against current code** (proves the inventory is accurate before any refactor).
- [ ] Commit: `test(web): freeze-contract inventory of structural bindings (§3a)`.

## Task 0.6 — Harness: harden the contrast-matrix gate, add target-size helper + token-resolve test

**Files**
- Modify: `packages/smart_pid_web/src/theme/themeContrast.test.ts` (existing gate — HARDEN, do not replace) and `src/theme/themeContrast.ts` (`PALETTES`)
- Create/Test: `packages/smart_pid_web/src/theme/tokenResolve.test.ts`
- Create: `packages/smart_pid_web/e2e/helpers/targetSize.ts` (Playwright bbox helper) + `packages/smart_pid_web/e2e/target-size.spec.ts`
- Modify: `package.json` (add `wcag-contrast`, `apca-w3` dev deps)

**Interfaces** — Consumes: existing `PALETTES[themeId]` (hex per theme) and `THEMES = ['isa101','dark-room','md3-dark','md3-light','ocean']`. Produces: an enforceable gate matching spec §4 thresholds + an APCA cross-check + a per-theme token re-resolve test + a ≥44×44 target-size Playwright helper.

- [ ] Install: `npm i -D wcag-contrast apca-w3`.
- [ ] Write the **hardened** assertions in `themeContrast.test.ts` (extend the existing suite; keep the current hand-rolled `contrast()` as a cross-check but make `wcag-contrast` the source of truth). For each `[data-theme]` enumerate the **exact pairs** from §4:
  - text pairs: `--text` and `--text-secondary` each on `{--bg, --surface, --surface-container-high}` → **fail if `<4.5:1`, and `<5:1` for the `isa101` theme**.
  - alarm pairs: `--alarm-critical` / `--alarm-warning` / `--alarm-diag` each on `{--bg, --surface, --surface-container-high}` → fail if below the non-text 3:1 floor **AND** assert pairwise alarm **hue-delta ≥ threshold** (reuse existing `deltaHue`, floor e.g. 25°) so CRIT/WARN/DIAG stay distinguishable.
  - **ΔL gate:** fail if luminance delta `ΔL < 0.2` for any required text pair.
  - **APCA cross-check:** for the text-on-surface pairs, assert `Math.abs(APCAcontrast(text, surface)) >= 60` (Lc 60 ≈ body-text floor) using `apca-w3`.
- [ ] Add `PALETTES` entries for any pair not yet covered (`--surface-container-high`, `--text-secondary`) so the matrix is complete; keep hex values synced to `themes.css` (add a comment linking each to its `[data-theme]` block).
- [ ] Run `npm run test -- src/theme/themeContrast.test.ts` → **passes** for all 5 themes (fix any palette that fails by correcting `themes.css` + `PALETTES` together — a contract change requires spec note).
- [ ] Write `tokenResolve.test.ts` (jsdom): for each theme, set `document.documentElement.setAttribute('data-theme', id)`, then assert representative bridged tokens re-resolve (e.g. `getComputedStyle(document.documentElement).getPropertyValue('--bg')` is non-empty and differs across at least two themes) — proves `@theme inline` swap works. Loop all 5 ids.
- [ ] Run `npm run test -- src/theme/tokenResolve.test.ts` → **passes**.
- [ ] Write `e2e/helpers/targetSize.ts`: `assertMinTarget(locator, min=44)` reads `boundingBox()` and asserts `width>=min && height>=min`. Write `e2e/target-size.spec.ts` asserting the focus ring is ≥2px and ≥3:1 (read computed `outline`/`box-shadow`-free ring) and that representative interactive controls (mode buttons, ack-all, theme switch) meet ≥44×44 — this spec is fleshed out per-surface but the helper + one smoke assertion land now.
- [ ] Run `npm run test:e2e -- e2e/target-size.spec.ts` → passes (smoke).
- [ ] Run full `npm run test` → **all green** (Phase 0 exit gate). Run `npm run build` → green.
- [ ] Commit: `test(web): harden contrast-matrix gate (wcag-contrast+APCA), token-resolve + target-size helpers`.

**Phase 0 DONE when:** Tailwind builds, `@theme inline` bridge resolves all 5 themes (tokenResolve green), shadcn flat primitives in place, lint rules active, freeze-contract + hardened contrast gate + target-size helper all green.

---

# Phase 1 — Shell (strict ISA-101)

## Task 1.1 — AppShell + NavRail + TopBar + StatusIndicator + ThemeSwitcher

**Files**
- Modify: `src/components/shell/AppShell.tsx`, `NavRail.tsx`, `TopBar.tsx`, `StatusIndicator.tsx`, `ThemeSwitcher.tsx`
- Remove: `src/components/shell/NavRail.css` (41 lines → utilities/`@apply`, classes preserved)
- Tests (existing, must stay green): `src/components/shell/__tests__/AppShell.test.tsx`, `src/components/shell/ThemeSwitcher.test.tsx`

**Interfaces** — Consumes: token bridge, freeze inventory (`aria-label="Alarm summary"`, `aria-label="Theme"`). Produces: rail 64px collapsed / 224px expanded (`--nav-rail-w` / `--nav-rail-w-expanded`), alarm bar present on every route.

- [ ] **Freeze sub-step:** confirm `AppShell.test.tsx` asserts `getByLabelText('Alarm summary')` and `ThemeSwitcher.test.tsx` asserts `getByLabelText('Theme')` as `HTMLSelectElement`. Keep the AlarmBar mounted in AppShell and keep ThemeSwitcher a real `<select>` with `aria-label="Theme"` (do NOT swap to shadcn Select here — the test reads `HTMLSelectElement.value`; if swapping, map to a native select or update only after Task 8 confirms a Select with matching label semantics). Decision: **keep native `<select>` for ThemeSwitcher** to preserve the test.
- [ ] Convert `NavRail.tsx` inline styles + `NavRail.css` to Tailwind utilities; preserve any class hooks via `@apply` in a small `@layer components` block in `index.css` if a class is referenced elsewhere. Rail widths from `--nav-rail-w`/`--nav-rail-w-expanded`; heights from `--appbar-h`/`--alarmbar-h`. No shadow; hairline borders `border-border`.
- [ ] Convert `AppShell`/`TopBar`/`StatusIndicator` inline styles to token utilities. Apply §6 craft: tabular numerals where numbers appear, 4px-grid spacing from `--sp-*`, hairline dividers `--divider`, hierarchy by scale+weight+gray only.
- [ ] Apply 5 control-states (rest/hover one tonal step/focus ring §4/active step-down/disabled `--text-disabled`) to nav items and top-bar buttons; motion compositor-only (`transform`/`opacity`, `--dur-*`).
- [ ] Run `npm run test -- src/components/shell` → **green** (AppShell + ThemeSwitcher).
- [ ] Run `npm run lint` (shell files now token-only) and `npm run build` → green.
- [ ] **Checkpoint commit:** `refactor(web): shell to Tailwind+tokens, flat ISA-101 (NavRail.css removed)`.

---

# Phase 2 — Cards / AnalogBar (strict; AnalogBar = boldness budget)

## Task 2.1 — AnalogBar (7 inline blocks; dynamic fill MUST stay inline)

**Files**
- Modify: `src/components/AnalogBar.tsx`
- Test (existing, stay green): `src/components/AnalogBar.test.tsx`

**Interfaces** — Consumes: freeze inventory. Produces: same DOM contract, token-driven static styling, dynamic fill/marker inline.

- [ ] **Freeze sub-step (preserve exactly):** `className="analog-bar"`, `analog-bar__label`, `analog-bar__track`; `data-testid="bar-fill"` (with `data-alarm={alarm}`), `data-testid="sp-marker"`, `data-testid="bar-value"`; `role="meter"` + `aria-label={`${label} ${display} ${scale.unit}`}` + `aria-valuemin/max/now`. The test reads `fill.style.width || fill.style.transform` and asserts `bar-value` text `'—'` / `'12.35'` / `'12.3'`.
- [ ] Replace the **static** inline-style objects (the container `{display:'flex',alignItems:'center',gap:8}`, label `{width:24,color:'var(--text-secondary)'}`, track `{position,flex,height,background:'var(--bar-track)',borderRadius:'var(--radius-pill,0)',overflow}`) with Tailwind utilities/`@apply` on the preserved classes: `analog-bar` → `@apply flex items-center gap-2`, `analog-bar__label` → `@apply w-6 text-text-secondary`, `analog-bar__track` → `@apply relative flex-1 bg-bar-track overflow-hidden rounded-pill`. Track height stays a token-driven value (8px card / 14px faceplate via `data-size`).
- [ ] **Keep inline** the dynamic `bar-fill` `width:`${pct}%`` + `background: ALARM_FILL[alarm]` and the `sp-marker` `left:`${spPct}%`` — runtime values Tailwind can't express. (This is mandated by §3a.)
- [ ] Apply §6 optical alignment: right-aligned tabular decimal column on `bar-value` (`font-data tabular-nums text-right`), fixed-width so no reflow.
- [ ] Run `npm run test -- src/components/AnalogBar.test.tsx` → **green**.
- [ ] `npm run lint` (AnalogBar) → only the two sanctioned dynamic inline styles remain (allow-listed: dynamic value, not a color literal/shadow).

## Task 2.2 — ControllerCard (10 inline blocks) + LoopHealthRow

**Files**
- Modify: `src/components/ControllerCard.tsx`, `src/components/LoopHealthRow.tsx` (if present in tree)
- Tests (existing, stay green): `ControllerCard.test.tsx`, DashboardPage tests that mount cards

**Interfaces** — Consumes: AnalogBar (Task 2.1). Produces: flat card, no sparklines, token utilities.

- [ ] **Freeze sub-step:** preserve any `data-testid`/`aria-label` the card emits and the DashboardPage stubs (`card-controls-{n}`, `ai-panel-{n}` are stubbed in DashboardPage.test, not ControllerCard internals — but verify ControllerCard renders them via children). No new wrapper divs around AnalogBar (keeps `bar-*` queries flat).
- [ ] Convert 10 inline-style blocks to token utilities (`bg-surface border border-border`, radius `rounded-card`, spacing `--sp-*`). Flat: no card shadow/lift on hover (hover = one tonal step `bg-surface-container`). Card width via `--card-w`.
- [ ] Hierarchy: PV dominant (scale+weight), SP/CO secondary, labels `text-text-secondary`. No color-coded hierarchy.
- [ ] Run `npm run test -- src/components/ControllerCard.test.tsx src/pages/DashboardPage.test.tsx` → **green**.
- [ ] `npm run lint` + `npm run build` → green.
- [ ] **Checkpoint commit:** `refactor(web): cards + AnalogBar to Tailwind/tokens (dynamic fill kept inline)`.

---

# Phase 3 — Faceplate (strict, vitrine §6c; 26 inline blocks)

## Task 3.1 — Faceplate readouts, segmented mode control, CO slider, AI + apply-tuning

**Files**
- Modify: `src/components/Faceplate.tsx`
- Use: shadcn `Slider` (Task 0.3)
- Test (existing, stay green): `src/components/Faceplate.test.tsx`

**Interfaces** — Consumes: shadcn Slider, AnalogBar, token bridge, freeze inventory. Produces: vitrine-grade faceplate, behavior unchanged.

- [ ] **Freeze sub-step (preserve exactly):** `aria-label="Setpoint"` (numeric input), `aria-label="Set setpoint"` (button), `aria-label="Manual CO"`, `aria-label={`Faceplate ${tag}`}` (the no-status `<aside>`), the 8 mode buttons with the active mode encoded, and the apply-tuning button matching `getByRole('button', { name: /apply tuning/i })` + its `disabled` when no pending recommendation. Test at `Faceplate.test.tsx:111/119` asserts `getByLabelText('Manual CO').toBeDisabled()` toggles with MAN mode; `:129` reads `getByLabelText('Setpoint')`; `:137` asserts apply-tuning disabled.
- [ ] Convert the 26 inline-style objects (`rootStyle`, `tagStyle`, `descStyle`, `controlRowStyle`, `controlLabelStyle`, `fieldStyle`, `errorStyle`, `readoutStyle`, `readoutLabelStyle`, `readoutValueStyle`, `readoutValuePrimaryStyle`, mode-button styles, etc.) to token utilities/`@apply`. PV hero at `--text-3xl` mono tabular, optical centering, fixed decimal column; SP/CO at `--text-xl`.
- [ ] Build the **segmented AUTO/MAN/CAS…** control as flat tactile buttons (≥44×44 each): inactive `bg-surface-container-high text-text-secondary`, active `bg-field-bg text-text border border-border-strong` (Dark Room) — MD3 segmented look resolves via token overrides. The 8 modes fit a 2-row segmented group (RCas/ROut may collapse to a flat dropdown). Keep each mode a focusable button with its existing accessible name.
- [ ] **CO control → shadcn `Slider` (MAN-only)** with precise flat track/thumb. Keep the existing numeric `aria-label="Manual CO"` field as the labelled focusable target **and** map slider `disabled`→`aria-disabled`/`data-disabled`; keep `aria-label="Manual CO"` on the focusable thumb so `getByLabelText('Manual CO').toBeDisabled()` still resolves. (If the test targets the numeric input specifically, keep the input as the primary labelled element and add the slider beside it sharing the MAN gate.)
- [ ] AI controls: `[ RUN | PAUSE | STOP ]` in the same flat toggle language + live gamma/Ki chip (`ai` token). apply-tuning = **strong-border** button (`border-2 border-border-strong`, NOT alarm color) → opens ConfirmApplyTuning modal (Task 8.x). Side-sheet width 360–420px; full-screen `<1024`.
- [ ] Missing states on this surface (§6a): waiting/no-status `<aside>` uses static placeholder + `aria-busy` (keep the existing "Waiting for data…" but greyed last-known where available; no shimmer).
- [ ] Run `npm run test -- src/components/Faceplate.test.tsx` → **green** (all: tag/PV/SP/CO readouts, 8 modes, mode command payload, MAN gate on Manual CO, setpoint, apply-tuning disabled).
- [ ] `npm run lint` + `npm run build` → green.
- [ ] **Checkpoint commit:** `refactor(web): faceplate vitrine (segmented modes, shadcn Slider CO, flat apply-tuning)`.

---

# Phase 4 — Alarms (strict; 3 redundant channels)

## Task 4.1 — AlarmBar + AlarmPanel + AlarmConfigForm

**Files**
- Modify: `src/features/alarms/AlarmBar.tsx`, `AlarmPanel.tsx`, `AlarmConfigForm.tsx`
- Remove: `src/features/alarms/AlarmBar.css` (24 lines), `AlarmPanel.css` (37), `AlarmConfigForm.css` (7) → utilities/`@apply`, classes preserved
- Tests (existing, stay green): `__tests__/AlarmBar.test.tsx`, `AlarmPanel.test.tsx`, `AlarmConfigForm.test.tsx`

**Interfaces** — Consumes: token bridge, freeze inventory. Produces: 3-channel redundancy (color + shape/icon + count/weight), reduced-motion hardened path.

- [ ] **Freeze sub-step (preserve exactly):** `className="alarm-bar"` + `aria-label="Alarm summary"`; bucket `data-testid` `count-critical`/`count-warning`/`count-advisory`; the `is-unacked` class toggled on the bucket when it has unacked alarms (asserted `toHaveClass('is-unacked')` / `not.toHaveClass`); `threshold-HIHI`/`threshold-HI` testids + `/limit/i` label in AlarmConfigForm; `alarm-row-{n}` testids + CRITICAL-first ordering + `/filter.*state/i` in AlarmPanel. Note current CSS classes `alarm-bar__bucket`, `alarm-bar__n`, `sev-icon` carry the blink — keep these classes via `@apply` since the keyframe targets them.
- [ ] Migrate `AlarmBar.css` into `index.css` `@layer components` keeping the exact selectors (`.alarm-bar`, `.alarm-bar__counts`, `.alarm-bar__bucket`, `.alarm-bar__n`, `.alarm-bar__bucket.is-unacked .sev-icon`, `… .alarm-bar__n`) and the `@keyframes alarm-blink` + `@media (prefers-reduced-motion: reduce)` block. **Fix the stale token refs:** the current CSS uses `--space-4`, `--space-3`, `--surface-2`, `--text-muted`, `--divider` (with fallbacks) — remap to contract tokens (`--sp-4`/`--sp-3`, `--surface-container`, `--text-secondary`, `--divider`) so styling actually resolves. (`--divider` is in the contract; the others are not.)
- [ ] **Reduced-motion hardened path (§4):** default motion-on = blink animates icon/counter **opacity only** (already present). For `prefers-reduced-motion: reduce`: no blink; unacked shown via `font-weight:700` + underline + filled icon (present) **PLUS add** (a) a persistent unacked **count badge** distinct from the total count, and (b) `aria-live="assertive"` region announcing new CRITICAL unacked. Keep both encodings so new-vs-seen survives without motion.
- [ ] Convert AlarmPanel + AlarmConfigForm inline/CSS to token utilities; tabular numerals on counts/limits; hairline rows; CRITICAL-first ordering preserved.
- [ ] Write/extend a **3-channel test** in `AlarmBar.test.tsx`: assert an unacked CRITICAL bucket simultaneously exposes (1) the alarm color token, (2) the shape/icon (`sev-icon` present), and (3) the weight/count redundancy (`is-unacked` class + count). Add a **reduced-motion test**: with `matchMedia('(prefers-reduced-motion: reduce)')` → matches=true (override the setup stub in-test), assert the badge + `aria-live` assertive region are present and the blink animation is suppressed.
- [ ] Run `npm run test -- src/features/alarms` → **green** (counts, is-unacked toggle, ack-all POST, panel ordering/filter, config thresholds, new 3-channel + reduced-motion).
- [ ] `npm run lint` + `npm run build` → green.
- [ ] **Checkpoint commit:** `refactor(web): alarms to Tailwind/tokens, 3-channel + reduced-motion hardened (css removed)`.

---

# Phase 5 — Trends (strict; uPlot via JS opts)

## Task 5.1 — RealtimeTrend + MultiTrendChart + selectors + ExportButton + readout §6d

**Files**
- Modify: `src/features/multitrend/MultiTrendChart.tsx`, `RealtimeTrend.tsx` (or equivalent), `SeriesSelector.tsx`, `HistoryQuery.tsx`, `ExportButton.tsx`
- Modify: `src/lib/uplotTheme.ts` (`readTrendTokens`/`buildUplotTheme`)
- Remove: `src/features/multitrend/MultiTrend.css` (93 lines) → utilities/`@apply`
- Tests (existing, stay green): `MultiTrendPage.test.tsx` (`multitrend-chart` stub), `SeriesSelector.test.tsx` (`Loop 1 · PV`), `HistoryQuery.test.tsx` (`/start/i`,`/limit/i`), `uplotTheme.test.ts`

**Interfaces** — Consumes: `buildUplotTheme(readTrendTokens(getComputedStyle(el)))`. Produces: tabular hover readout (PV/SP/CO at cursor time), defined line weights via trend tokens, neutral gray plot bg, crosshair.

- [ ] **Freeze sub-step:** preserve `data-testid="multitrend-chart"` (page test stubs the chart by this id), `aria-label` matching `/history query/i`, the `Loop 1 · PV` series checkbox label, `/start/i` + `/limit/i` inputs. Do not rename `multitrend-chart`.
- [ ] Convert MultiTrend.css + inline styles (chart container, selector list, toolbar) to token utilities. Chart wrapper neutral gray plot bg via `--bar-track`/a trend bg token; surrounding chrome `bg-surface border-border`.
- [ ] In `uplotTheme.ts`: ensure `readTrendTokens` pulls trend line tokens (PV/SP/CO colors + line weights) from CSS vars and `buildUplotTheme` sets `series[].stroke`/`width`, axis label font (`--font-data`), grid hairline color, and a **crosshair cursor** (`cursor: { x:true, y:true }`). Keep the existing `uplotTheme.test.ts` green; extend it to assert line weights + axis font come from tokens.
- [ ] Implement the **§6d hover readout**: a tabular tooltip showing PV/SP/CO at the cursor time (uPlot `cursor` + a token-styled readout DOM node, tabular-nums, fixed decimal column). Add a Vitest that mounts the chart and asserts the readout node exists with tabular formatting (canvas is stubbed in `setup.ts`, so assert the DOM readout, not pixels).
- [ ] Run `npm run test -- src/features/multitrend src/lib/uplotTheme.test.ts src/pages/MultiTrendPage.test.tsx` → **green**.
- [ ] `npm run lint` + `npm run build` → green.
- [ ] **Checkpoint commit:** `refactor(web): trends to Tailwind/tokens, uPlot token theme + §6d readout (css removed)`.

---

# Phase 6 — Executive Dashboard (LATITUDE §6b)

## Task 6.1 — ExecutiveKPICard + TuningRecommendationCard (+ ExecutiveDashboardPage)

**Files**
- Modify: `src/components/ExecutiveKPICard.tsx`, `src/components/TuningRecommendationCard.tsx`, `src/pages/ExecutiveDashboardPage.tsx`
- Remove: `src/components/ExecutiveKPICard.css` (40), `src/pages/ExecutiveDashboardPage.css` → utilities/`@apply`
- Tests (existing, stay green): `ExecutiveKPICard.test.tsx`, `ExecutiveDashboardPage.test.tsx`

**Interfaces** — Consumes: token bridge. Produces: modern-latitude exec layout (bento/editorial allowed) that is still flat (no shadow/gradient/bevel — latitude is layout/typography/hierarchy, NOT shadows) and still token-colored.

- [ ] **Freeze sub-step (preserve exactly):** `data-testid` `kpi-var`, `kpi-iae`, `kpi-tv`, `kpi-variability`, `kpi-auto`, `kpi-loops`, `kpi-bad-delta`, `kpi-ok-delta` + `data-out-of-target` attr (`'true'`/`'false'`); `executive-dashboard`; `health-FIC-101-opc`/`-state`, `health-TIC-202-state` with their text content. Keep all.
- [ ] Apply §6b latitude: stronger scale contrast on hero KPIs, intentional bento/editorial composition, but **still flat** (no `box-shadow`/gradient — lint enforces) and token colors only. `data-out-of-target` drives a token-based emphasis (weight/border), not a raw color.
- [ ] Convert ExecutiveKPICard.css + page CSS to utilities; tabular numerals on all KPI values; fixed decimal columns.
- [ ] Run `npm run test -- src/components/ExecutiveKPICard.test.tsx src/pages/ExecutiveDashboardPage.test.tsx` → **green**.
- [ ] `npm run lint` + `npm run build` → green.
- [ ] **Checkpoint commit:** `refactor(web): executive dashboard latitude §6b, flat token-colored (css removed)`.

---

# Phase 7 — Login (LATITUDE §6b)

## Task 7.1 — LoginPage

**Files**
- Modify: `src/pages/LoginPage.tsx` (+ its CSS if present)
- Tests (existing, stay green): login-related Vitest + `e2e/login-dashboard.spec.ts`

**Interfaces** — Consumes: token bridge, shadcn form primitives. Produces: modern-latitude login, flat, both light & dark intentional.

- [ ] **Freeze sub-step:** preserve any login form field labels asserted by tests and the submit affordance; keep `data-theme`-driven styling so the e2e themes snapshot stays valid.
- [ ] Convert inline/CSS to token utilities; apply §6b latitude (editorial composition, scale contrast) while flat + token-colored. Use shadcn inputs/Button restyled flat.
- [ ] Missing states (§6a): error state on bad login uses desaturated `--alarm-diag` + text (NOT critical red), with a clear retry affordance.
- [ ] Run `npm run test` (login Vitest) → green. Run `npm run test:e2e -- e2e/login-dashboard.spec.ts` → passes (re-bless its snapshot in Phase 9 group regen).
- [ ] `npm run lint` + `npm run build` → green.
- [ ] **Checkpoint commit:** `refactor(web): login latitude §6b, flat token-colored`.

---

# Phase 8 — Peripheral (strict; shadcn forms/dialogs/menus, flat)

## Task 8.1 — Primitive swap: ConfirmApplyTuningDialog + LoopConfigDialog + WelcomeDialog → shadcn Dialog

**Files**
- Modify: `src/features/loop-config/ConfirmApplyTuningDialog.tsx`, `LoopConfigDialog.tsx`, `src/features/projects/WelcomeDialog.tsx`
- Replace usage of: `src/components/ui/Dialog.tsx` (hand-rolled) → shadcn `dialog.tsx`. Delete the old `Dialog.tsx` once no importers remain.
- Tests (existing, stay green): `ConfirmApplyTuning.test.tsx` (`getByRole('dialog')`), `LoopConfigDialog.test.tsx` (`getByRole('dialog')`, `NONE`/`FUZZY`/`RL` radios, `/gain|reset|rate|objective|dead time|learning rate|train interval|fallback kp/i`, `/Salvar/i`), `WelcomeDialog.test.tsx` (`getByRole('dialog')`)

**Interfaces** — Consumes: shadcn Dialog. Produces: same `role="dialog"`/`aria-modal`/labelled-by contract; the scrim is the single sanctioned `rgba`.

- [ ] **Freeze sub-step (preserve exactly):** `getByRole('dialog')` must still resolve (Radix Dialog content has `role="dialog"` — verified); keep `aria-label="Fechar"` + `data-testid="dialog-backdrop"` on the close/scrim element (Radix `Dialog.Close` on the overlay, or a dedicated close button carrying both attrs); keep the footer button names `/Salvar/i`, `/Cancelar|Escrever/` as rendered; keep all radio/field accessible names.
- [ ] Swap each dialog's wrapper from `<Dialog open onClose title footer>` to the shadcn Dialog composition, mapping `title`→`DialogTitle` (keep `aria-labelledby`), `footer`→`DialogFooter`, `onClose`→`onOpenChange`. **Carry `data-testid="dialog-backdrop"` and `aria-label="Fechar"` onto the overlay/close** so `AlarmBar`/dialog tests and the freeze-contract test pass. Add **no extra wrapper divs** that would break `getByRole('dialog')` or `within(dialog)` queries.
- [ ] Restyle flat: dialog panel `bg-surface-container border border-border-strong rounded-none` (MD3 radius via token), **no `box-shadow`** (the old `0 8px 32px rgba` is gone); the **overlay scrim** keeps its `rgba` (sole exception, lint allow-listed in Task 0.4).
- [ ] Run `npm run test -- src/features/loop-config/__tests__/ConfirmApplyTuning.test.tsx src/features/loop-config/__tests__/LoopConfigDialog.test.tsx src/features/projects/WelcomeDialog.test.tsx src/test/freeze-contract.test.ts` → **green**.
- [ ] Delete `src/components/ui/Dialog.tsx` if no importers (`grep -rn "ui/Dialog" src` empty), then re-run those tests + `npm run build`.
- [ ] **Checkpoint commit:** `refactor(web): dialogs to shadcn Dialog (flat, scrim-only rgba; Fechar/backdrop preserved)`.

## Task 8.2 — LoopConfigDialog body, AiPanel, CardControls form fields

**Files**
- Modify: `src/features/loop-config/LoopConfigDialog.tsx` (18 inline blocks), `AiPanel.tsx` (11), `CardControls.tsx` (12)
- Tests (existing, stay green): `LoopConfigDialog.test.tsx`, `AiPanel.test.tsx`, `CardControls.test.tsx`

**Interfaces** — Consumes: shadcn Tabs/Select/Switch/Slider where they fit. Produces: token-styled flat forms.

- [ ] **Freeze sub-step (preserve exactly):** `data-testid="ai-panel"`; `getByRole('button', { name: /apply tuning/i })` disabled state in AiPanel; CardControls `/mode/i` `HTMLSelectElement`, `/setpoint/i` input, `/output/i` input disabled-on-mode; LoopConfigDialog `NONE`/`FUZZY`/`RL` radios + all numeric field labels + `/Salvar/i` disabled when reset=0. **CardControls `/mode/i` is read as `HTMLSelectElement`** → keep a native `<select>` (or shadcn Select only if the test is updated to a combobox query — default: keep native to preserve the test).
- [ ] Convert the 18+11+12 inline-style blocks to token utilities/`@apply`. Use shadcn `Tabs` for the NONE/FUZZY/RL panel switching only if it preserves the radio accessible names (`getByLabelText('RL')` etc.) — safer: keep radios, restyle flat; use shadcn `Switch`/`Slider` for boolean/range fields where no label-query depends on a native input.
- [ ] Apply §6 craft (tabular numerals on all numeric fields, 4px grid, hairlines, 5 control-states, focus ring).
- [ ] Run `npm run test -- src/features/loop-config` → **green** (all AiPanel/CardControls/LoopConfigDialog + validation/useAiControls suites).
- [ ] `npm run lint` + `npm run build` → green.
- [ ] **Checkpoint commit:** `refactor(web): loop-config forms (LoopConfigDialog/AiPanel/CardControls) to Tailwind/tokens`.

## Task 8.3 — ConnectionPanel + TagBrowser + Settings + Projects + Simulator

**Files**
- Modify: `src/features/connection/ConnectionPanel.tsx`, `TagBrowser.tsx`; `src/features/settings/SettingsForm.tsx`; `src/features/projects/*` (`ProjectImportDropzone`, `ProjectList`, `WelcomeDialog` body); `src/features/simulator/*` (`DynamicsSliders`, `SimulationModeBanner`, `SimulatorControlPanel`, disturbance/output/mode controls); page CSS for these.
- Remove: `ConnectionPanel.css` (99), `TagBrowser.css` (84), `SettingsForm.css`, `ProjectImportDropzone.css`, `ProjectList.css`, `WelcomeDialog.css`, `DynamicsSliders.css`, `SimulationModeBanner.css`, `SimulatorControlPanel.css`, `ConnectionPage.css`, `ProjectsPage.css`, `SettingsPage.css`, `SimulatorPage.css` → utilities/`@apply`.
- Tests (existing, stay green): `ConnectionPanel.test.tsx` (`/endpoint/i`), `SettingsForm.test.tsx` (`/number decimals|trend window|confirm destructive/i`), `simulator/__tests__/*` (`readout-gain` `'1.20'`, `/remove/i`, `/apply output/i`, `simulator controls`), `SimulatorPage.test.tsx` (`twin-trend`), `ProjectsPage`/`WelcomeDialog` tests.

**Interfaces** — Consumes: shadcn forms/Slider/Select. Produces: token-styled flat peripheral surfaces.

- [ ] **Freeze sub-step (preserve exactly):** `/endpoint/i` with value, `/number decimals/i`/`/trend window/i`/`/confirm destructive/i` labels, `data-testid="readout-gain"` (text `'1.20'`), buttons `/remove/i` + `/apply output/i` disabled states, `aria-label` matching `/simulator controls/i`, `data-testid="twin-trend"`. Simulator `DynamicsSliders` → shadcn `Slider` but keep `readout-gain` testid + tabular `1.20` formatting.
- [ ] Convert each component's inline/CSS to token utilities; remove the 14 listed `.css` files; preserve any class hooks via `@apply`. Apply §6 craft uniformly.
- [ ] Run `npm run test -- src/features/connection src/features/settings src/features/projects src/features/simulator src/pages/SimulatorPage.test.tsx` → **green**.
- [ ] `npm run lint` + `npm run build` → green.
- [ ] **Checkpoint commit:** `refactor(web): peripheral surfaces (connection/settings/projects/simulator) to Tailwind/tokens (css removed)`.

---

# Phase 9 — Missing states, responsive, perf/CI, snapshot regen, final gate

## Task 9.1 — Mandated missing states §6a across all surfaces

**Files**
- Modify: dashboard/faceplate/alarms/trends/exec pages + their loading/empty/error branches
- Create/Test: `src/test/missing-states.test.tsx`

**Interfaces** — Produces: loading (static placeholder bars + last-known greyed + `aria-busy`, NO shimmer), empty (explicit per-surface), error/WS-disconnect (desaturated `--alarm-diag` + text + reconnect affordance + stale indication).

- [ ] Write failing `missing-states.test.tsx`: for Dashboard (no loops), AlarmPanel (no alarms), MultiTrend (no history), and a WS-disconnect state — assert (a) loading branch sets `aria-busy` and renders static (non-animated) placeholders, (b) empty branch renders an explicit empty message, (c) disconnect branch uses the diag token treatment + exposes a reconnect control + a stale-data indicator. Run → **fails**.
- [ ] Implement the three states per surface using token utilities; loading = static bars (no `animate-*`/skeleton shimmer — lint/test guards), empty = explicit text, error/disconnect = desaturated `--alarm-diag` + reconnect button + stale badge.
- [ ] Run `npm run test -- src/test/missing-states.test.tsx` → **passes**.
- [ ] Commit: `feat(web): mandated missing states (loading/empty/error-disconnect) §6a`.

## Task 9.2 — Responsive <1024 rules

**Files**
- Modify: `AppShell`/`NavRail` (rail→icons), card grid (→single column), `Faceplate` (→full-screen), interactive targets (≥44×44)
- Test: `e2e/responsive.spec.ts` (new) + extend `e2e/target-size.spec.ts`

**Interfaces** — Produces: nav-rail collapses to icons <1024; cards reflow to single column; faceplate full-screen; all touch targets ≥44×44.

- [ ] Write `e2e/responsive.spec.ts` at 320/768/1024/1440: assert at <1024 the nav-rail is icon-only (width ≈64px), the card grid is single-column (one card per row), the faceplate opens full-screen, and `assertMinTarget` passes for nav items, mode buttons, ack-all, slider thumb. Run → **fails** where rules absent.
- [ ] Implement responsive breakpoints with Tailwind (`max-[1023px]:` / container queries) on the listed components; verify no overflow.
- [ ] Run `npm run test:e2e -- e2e/responsive.spec.ts e2e/target-size.spec.ts` → **passes**.
- [ ] Commit: `feat(web): responsive <1024 rules + ≥44×44 targets`.

## Task 9.3 — Perf budget + CI gate order (§12)

**Files**
- Modify: `vite.config.ts` (manualChunks/lazy-load heavy-rare surfaces), route-level `React.lazy` for Simulator/MultiTrend/Exec/Projects
- Create: `packages/smart_pid_web/scripts/check-bundle.mjs` + wire into CI
- Modify: CI workflow (repo `.github/workflows/*` if present) to run gate order: lint → typecheck → Vitest (incl. contrast/target-size/token-resolve/missing-states) → build (bundle budget) → Playwright snapshots

**Interfaces** — Produces: app-page JS ≤300kb gzip, CSS ≤50kb; regression fails CI.

- [ ] Add `React.lazy` + `Suspense` for heavy/rare routes (Simulator, MultiTrend, Executive, Projects) so the dashboard entry stays lean. Verify Tailwind purge is on (v4 default content scan) and Radix is tree-shaken.
- [ ] Write `scripts/check-bundle.mjs`: after `vite build`, gzip-measure the app-page JS + CSS chunks, compare to budgets (JS ≤300kb, CSS ≤50kb) and to a committed `bundle-baseline.json` (pre-refactor delta); exit non-zero on breach. Run `node scripts/check-bundle.mjs` → passes within budget (capture the baseline first if absent).
- [ ] Update CI to the §12 gate order. If no CI workflow exists in-repo, document the order in `packages/smart_pid_web/README` and the authority spec; do not invent infra.
- [ ] Run `npm run build && node scripts/check-bundle.mjs` → green.
- [ ] Commit: `chore(web): perf budget check + CI gate order §12`.

## Task 9.4 — Snapshot regeneration (per-surface group) + final full gate + docs

**Files**
- Update: `e2e/**/*-snapshots/*.png` (re-bless per group, reviewed)
- Modify (same change set, §8 governance): `docs/superpowers/specs/2026-06-18-web-frontend-design-system-design.md` (authority — reflect Tailwind+shadcn engine, flat ISA-101, missing-states, contrast gate), `docs/identidade_visual_ISA101.md`, and the refactor spec status → implemented. Update `.claude/docs/estado-atual.md`.

**Interfaces** — Produces: blessed visual baselines + synced spec/identity docs (no UI merge without them).

- [ ] Re-bless snapshots group-by-group (do NOT bulk-update blindly): `npm run test:e2e -- --update-snapshots e2e/faceplate.spec.ts` then visually diff; repeat for `themes.spec.ts` (5 themes × {320,768,1024,1440}), `alarms`, `executive-dashboard`, `multitrend`, `login-dashboard`, `simulator`, fatia2/fatia7 specs. Review each diff before committing.
- [ ] Run the **full CI gate** end to end: `npm run lint` (0 errors — confirms the day-one inline-style/Dialog violations are now cleared) → `npm run build` → `node scripts/check-bundle.mjs` → `npm run test` (ALL Vitest incl. contrast matrix all 5 themes, token-resolve, target-size, freeze-contract, missing-states, 3-channel alarm) → `npm run test:e2e` (all snapshots match). Everything green.
- [ ] Update the authority spec + identity docs + estado-atual in this change set (§8). Confirm: Magic UI absent (`grep -rn "magicui\|magic-ui" src package.json` empty); zero `box-shadow`/gradient/bevel except the Dialog scrim (`grep -rn "box-shadow\|boxShadow\|gradient" src` → only the allow-listed scrim).
- [ ] **Final checkpoint commit:** `refactor(web): bless visual baselines + sync authority/identity docs (§8) — refactor complete`.

**Acceptance (spec §11) — all must hold at the end:** inline-style + listed `.css` migrated; no raw color/hex in markup (lint); §3a freeze honored + Vitest green; 5 themes via `data-theme` + token re-resolve passes; contrast-matrix gate passes every theme + focus ring ≥3:1/≥2px + all targets ≥44×44; reduced-motion path (badge + aria-live) + 3-channel alarm test pass; §6 craft + §6a missing states + responsive <1024 met; login + exec latitude §6b, operator screens strict, both themes intentional; baselines regenerated + reviewed; perf budget §12 met; authority + identity docs updated same change set; Pre-req 0 satisfied; Magic UI absent; zero shadow/gradient/bevel except modal scrim.
