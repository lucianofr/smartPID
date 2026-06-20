# Web Frontend Refactor — Tailwind v4 + shadcn, ISA-101-first (Design v2)

- **Date:** 2026-06-20 · **Rev:** v2 (post 4-agent review — architect/react/a11y/ux)
- **Status:** Design (revised after review; pending user approval of v2)
- **Branch:** `refactor/web-tailwind-shadcn-isa101` (off `main`, worktree `.worktrees/web-isa101-refactor`)
- **Amends authority:** `docs/superpowers/specs/2026-06-18-web-frontend-design-system-design.md`
- **Review record:** `.claude/reports/review/review-web-refactor-spec-20260620.md`
- **Related:** `docs/identidade_visual_ISA101.md`, `docs/superpowers/specs/2026-06-18-web-hmi-react-migration-design.md`

---

## 1. Problem & current state

`packages/smart_pid_web/` is a mature React 18 + Vite + TS app (≈227 tracked files) implementing all 8 web fatias and 5 ISA-101-derived themes.

**Styling layer (corrected after review):** the dominant styling mechanism is **inline React `style={{}}` objects — 121 blocks across 19 components** (Faceplate 26, LoopConfigDialog 18, CardControls 12, AiPanel 11, ControllerCard 10, AnalogBar 7, …), **plus** 13 plain per-component `.css` files. The migration's primary target is the **inline-style layer**; `.css` removal is a subset. Effort is ~2–3× a CSS-only swap. Token contract is CSS custom properties; Playwright visual snapshots exist (5 themes × {320,768,1024,1440}); Vitest behavior tests exist.

Goal: modernize and make the frontend **beautiful** using Tailwind + shadcn, **ISA-101 compliant**. Driver (confirmed): **re-engineer the styling layer AND raise execution to instrument-grade**.

### Central tension (resolved)

ISA-101 §2 + the design-system spec forbid what Magic UI provides (gradients, shadows, bevels, glows, decorative animation, color in normal state). Magic UI is therefore **dropped** (see §10).

### Decisions (user choices)

1. **Visual stance — two-tier (revised v2).** **Operator situational-awareness screens** (live dashboard, faceplate, alarms, trends) = **strict ISA-101**. **Non-operator screens** = strict ISA-101 EXCEPT **login + executive dashboard**, which get **modern latitude** (§6b). Settings, connection/OPC, simulator, projects/welcome stay strict.
2. **Driver — both:** engine migration (Tailwind+shadcn) **and** instrument-grade polish.
3. **Sequencing — big-bang "C"**, hardened with per-surface green checkpoints (§9).

## 2. Goals / Non-goals

**Goals**

- Migrate inline-style + `.css` → **Tailwind v4 (CSS-first)** utilities bound to the existing token contract (tooling, not a look) + **shadcn** primitives restyled flat.
- Preserve the 5 themes via `[data-theme]`, behavior unchanged.
- Meet the **measurable craft standard** (§6) and **missing-state coverage** (§6a).
- Deliver **modern latitude** on login + exec (§6b) without operator-safety impact.
- Keep behavior tests green via the **hardened DOM-freeze rule** (§3a); regenerate snapshots in gated per-surface batches; keep the **contrast matrix** an enforceable CI gate (§4).

**Non-goals**

- No Magic UI (§10). No changes to PID/fuzzy/RL/OPC logic, EventBus, persistence, REST/WS contracts.
- No new features/routes. No renaming of token-contract names. No data-layer change (TanStack Query, WS envelope, uPlot). Browser/localhost only.

## 3. Engine architecture

**Tailwind v4 + shadcn, bound to the existing CSS-var token contract.**

- **Token bridge.** Tailwind v4 `@theme inline` maps utilities onto existing vars: `--color-bg: var(--bg)`, surfaces, text, alarm/state/trend/bar tokens; spacing → `--sp-*`; radius → `--radius-*`; type → `--font-ui/--font-data` + clamp scale; motion → `--dur-*`/`--ease-*`. **All color/radius/font tokens MUST use `@theme inline` (never plain `@theme`)** — a non-inline token emits a fixed build-time value and silently breaks runtime theme swap. Themes keep working via `[data-theme]` on `<html>`.
- **No raw colors in markup.** Token utilities only (`bg-surface text-text border-border`); a **lint rule blocks non-token color utilities** and hex.
- **shadcn, restyled flat at install.** Pull Dialog, DropdownMenu, Tabs, Select, Tooltip, Switch, Slider, Command, Toast for a11y/keyboard/focus; strip to ISA-101 (`--radius:0` default, MD3 overrides via token; remove every `shadow-*`; recolor to tokens). Replaces hand-rolled `src/components/ui/Dialog.tsx`.
- **React 18 (not 19).** `react@^18.3.1` — pin **Radix versions compatible with React 18**, keep `forwardRef` on wrapped primitives. Exact Tailwind v4 + shadcn + Radix versions pinned via **context7** at plan time.
- **Flat-lint vs existing code.** Current `Dialog.tsx` hardcodes `boxShadow` + rgba backdrop → fails the flat lint day one; the shadcn Dialog swap is the fix. The **modal backdrop scrim is the single sanctioned `rgba`**; everything else flat (no box-shadow/gradient/bevel).

### 3a. Hardened DOM-freeze rule (load-bearing — reconciles §7/§9)

"Tests stay green" is only true if these are preserved exactly (class removal + primitive swaps ARE contract changes otherwise):

- **Preserve className hooks via `@apply`** — keep classes that tests assert (e.g. `is-unacked` in `AlarmBar`); do not delete them with the `.css` file.
- **Keep dynamic inline styles** — runtime values Tailwind can't express stay inline (`AnalogBar` `width:${pct}%`, fill markers).
- **Preserve every `data-testid` / `aria-label` / `data-*`** on swapped primitives: `dialog-backdrop`, `aria-label="Fechar"`, `Manual CO`, `bar-fill`/`sp-marker`/`bar-value`, `multitrend-chart`, alarm `count-*`.
- **Map native semantics** lost in composites: Radix Slider `disabled` → `aria-disabled`/`data-disabled` so `getByLabelText('Manual CO').toBeDisabled()` keeps working (keep `aria-label` on the focusable thumb).
- **No new wrapper `<div>`s** from `clsx`/portal churn (Radix portals are query-agnostic for existing `getByRole('dialog')` asserts — verified).
- **Inventory before coding:** grep all structural-binding asserts (`toHaveClass`, `style.width`, `getByLabelText(...).toBeDisabled`, `dialog-backdrop`, `Fechar`) and treat each as a preserve-constraint.

## 4. Tokens, themes, gates

- **Token contract is law** — names unchanged; refactor consumes, never renames. 5 themes preserved (MD3 radius/font overrides resolve via the token layer). Self-hosted IBM Plex Sans/Mono (MD3 → Roboto). No CDN.
- **Contrast-matrix gate (enforceable).** Enumerate exact pairs: `--alarm-critical/-warning/-diag` × `{--bg, --surface, --surface-container-high}`, and `--text/--text-secondary` on each surface. Tool: `wcag-contrast` (+ APCA cross-check) in a Vitest+jsdom job looping every `[data-theme]`. **Fail build if** any pair <4.5:1 (ISA-101 theme <5:1) OR ΔL <0.2 OR alarm hue-delta below threshold.
- **Focus ring (specified).** Always visible on keyboard focus; **≥3:1 vs adjacent colors, ≥2px solid** (WCAG 2.2 SC 2.4.11/2.4.13); verified per-theme in the same gate.
- **Reduced-motion (hardened).** `prefers-reduced-motion: reduce` → no blink; unacked shown via weight 700 + underline + filled icon **PLUS** `aria-live="assertive"` for new CRITICAL **and a persistent unacked count badge**, so new-vs-seen stays encoded without motion. Default (motion-on) blink animates icon/counter opacity only.

## 5. Scope & component map (big-bang — all surfaces)

Migrate **inline `style={{}}` + `.css` → Tailwind utilities/`@apply` + restyled shadcn**, under §3a freeze.

| Tier | Group | Components | Notes |
|---|---|---|---|
| Strict | Shell | AppShell, NavRail, TopBar, StatusIndicator, ThemeSwitcher | rail 64/224px; alarm bar = safety chrome on every route |
| Strict | Cards/bars | ControllerCard(10), AnalogBar(7), LoopHealthRow | AnalogBar = boldness budget; dynamic fill stays inline; no sparklines |
| Strict | Faceplate | Faceplate(26) (vitrine) | own polish sub-section §6c |
| Strict | Alarms | AlarmBar, AlarmPanel, AlarmConfigForm | 3 redundant channels; keep `is-unacked`, `count-*` |
| Strict | Trends | RealtimeTrend, MultiTrendChart (uPlot), selectors, ExportButton | uPlot via JS opts (`lib/uplotTheme.ts`); readout spec §6d |
| **Latitude** | Exec | ExecutiveKPICard, TuningRecommendationCard | modern latitude §6b |
| **Latitude** | Login | LoginPage | modern latitude §6b |
| Strict | Peripheral | ConnectionPanel, TagBrowser, loop-config (LoopConfigDialog 18, AiPanel 11, CardControls 12, ConfirmApplyTuningDialog), Simulator | shadcn forms/dialogs/menus, flat |
| — | Primitives | `src/components/ui/*` | hand-rolled Dialog → shadcn; add Select/Tabs/Tooltip/Switch/Slider/Command/Toast |

**`.css` removed** (→ utilities/`@apply`, classes preserved per §3a): `NavRail`, `AlarmBar`, `AlarmPanel`, `AlarmConfigForm`, `MultiTrend`, `ConnectionPanel`, `TagBrowser`, `ExecutiveKPICard`.

**Responsive <1024 (specified):** nav-rail collapses to icons; cards reflow to single column; faceplate goes full-screen; all touch targets ≥44×44.

## 6. Instrument-grade craft standard (measurable)

- **Type:** modular scale ratio **1.20**, anchored to the existing clamp tokens; tabular numerals on all process data (fixed decimal column, no reflow); defined letter-spacing for caps labels.
- **Grid:** explicit **4px baseline grid**; all spacing from `--sp-*`; intentional rhythm, no uniform padding, no magic numbers.
- **Hairlines:** 1px borders at `--border` with a defined min contrast delta vs surface; dividers via `--divider`.
- **Hierarchy from scale + weight + gray only** — never color (PV dominant, SP/CO secondary, labels `--text-secondary`).
- **Optical alignment** for AnalogBar numerals and PV hero (right-aligned decimal column, optical centering).
- **5 states per control:** rest / hover (one tonal step up, no shadow/lift) / focus (§4 ring) / active (step down, `translateY(0)`) / disabled (`--text-disabled`).
- **Motion compositor-only:** `transform`/`opacity`/`clip-path`; never layout props; durations `--dur-*`.
- **Flat enforced** — zero box-shadow/gradient/bevel except the §3 modal scrim (lint-blocked).

### 6a. Missing states (mandated, ISA-101-legal)

- **Loading:** static placeholder bars + last-known value greyed + `aria-busy` (NO shimmer/skeleton animation).
- **Empty:** explicit per-surface empty state (no loops, no alarms, no history).
- **Error / WS-disconnect:** treatment using **desaturated `--alarm-diag`** + text; reconnect affordance; stale-data indication.

### 6b. Non-operator latitude (login + executive dashboard ONLY)

Permitted beyond strict ISA-101, no operator-safety impact: disciplined larger type scale, generous spacing, refined composition, and **one restrained motion/depth affordance** (e.g. a subtle entrance fade/transform respecting `prefers-reduced-motion`). Still: token-driven colors, no marketing gradients/glows; color still not used to assert process state. Operator screens are unaffected.

### 6c. Faceplate (vitrine) polish

PV hero optical sizing at `--text-3xl` mono; segmented AUTO/MAN/CAS as flat tactile control (≥44×44 per option); CO slider (shadcn Slider, MAN-only) with precise track/thumb; AI RUN/PAUSE/STOP + live gamma/Ki; apply-tuning = strong-border button (NOT alarm color) → confirm modal. Side-sheet 360–420px, full-screen <1024.

### 6d. Trend (uPlot) interaction

Crosshair + hover readout with **tabular tooltip** (PV/SP/CO at cursor time), axis-label craft, defined line weights via trend tokens, neutral gray plot bg.

## 7. Testing strategy

- **Behavior/unit (Vitest) green** via §3a freeze. Structural-binding asserts inventoried + preserved. Any red = real contract bug.
- **Add tests:** per-severity **3-channel alarm** assert (glyph shape element AND text exist independent of color class); **target-size** Playwright bounding-box (≥44×44 for segmented/slider/ACK/apply-tuning); **token re-resolve** test (a known utility re-resolves after a `data-theme` flip).
- **Visual snapshots** regenerated **per surface group** (not one monolith), blessed only after the contrast gate passes + manual diff review.
- **a11y:** keyboard nav + reduced-motion + focus-order on key dialogs.
- TDD where logic changes (rare): red → green → commit.

## 8. Governance & branch strategy

- **Spec-first (CLAUDE.md).** Update the design-system authority spec + touched identity docs **in the same change set**. No UI commit without it.
- **Branch from `main`**, work on `refactor/web-tailwind-shadcn-isa101`, never commit to `main`.

### Pre-req 0 — reconcile desynced specs (HARD precondition)

Web specs are not on `main` (app there has only the fatia2 spec; the full set incl. the design-system authority lives on `docs/web-hmi-implementation-plans`). **Before any implementation:** `main` must first absorb the design-system authority spec (merge/cherry-pick), so governance is satisfiable. Not optional. Also **verify build tooling present** (`packages/smart_pid_web/package.json`, vite) on the working branch before planning install steps.

## 9. Risks & mitigations (big-bang / C, hardened)

| Risk | Mitigation |
|---|---|
| Inline-style scope (121/19 files) larger than CSS-only | §1/§5 inventory inline-style as primary work; plan effort 2–3× |
| Long "all red" window | **Per-surface commit checkpoints**, fixed order Shell→Cards/AnalogBar→Faceplate→Alarms→Trends→Peripheral; each independently Vitest-green; snapshots blessed group-by-group; **rollback = revert-to-last-green-commit** |
| Tests break from class/primitive swaps | §3a freeze + pre-coding assert inventory |
| ISA-101 leak via raw colors | lint blocks non-token color utilities |
| shadcn defaults smuggle shadow/radius | restyle-at-install + flat-lint gate (scrim exempt) |
| Theme swap breaks (non-inline tokens) | all color/radius/font via `@theme inline` + re-resolve test |
| Radix React-18 peer mismatch | pin compatible versions via context7 |
| Bundle weight from Radix | perf budget §12 |

## 10. Rejected options

- **Magic UI** — gradient/glow/motion catalog = ISA-101 §2 prohibited list. Dropped; traceable.
- **"Modern-first / relax ISA-101 globally"** — rejected; safety rationale holds on operator screens.
- **"ISA-101 strictly everywhere"** — superseded by the v2 two-tier decision (latitude on login + exec only).
- **Sequencing A (pilot-first) / B (incremental sweep)** — user chose C; retained as fallbacks if C stalls.

## 11. Acceptance criteria

- Inline-style + listed `.css` migrated to Tailwind utilities/`@apply` + restyled shadcn; **no raw color/hex in markup** (lint).
- §3a freeze honored: structural-binding asserts preserved; **Vitest green**.
- 5 themes render via `data-theme`; MD3 overrides intact; **token re-resolve test passes**.
- **Contrast-matrix gate passes** every theme (named tool, defined thresholds); focus ring ≥3:1/≥2px; **all targets ≥44×44**.
- Reduced-motion path (badge + `aria-live`) verified; 3-channel alarm test passes.
- Craft standard §6 met (type scale, baseline grid, hairlines, optical); **missing states** §6a present; responsive <1024 rules met.
- Login + exec show modern latitude §6b; operator screens strict; both dark & light feel intentional (per-theme review).
- Visual baselines regenerated per surface group + reviewed; **perf budget** §12 met.
- Authority spec + identity docs updated in the same change set; Pre-req 0 satisfied; Magic UI absent; zero box-shadow/gradient/bevel except modal scrim.

## 12. Performance & CI

- **Bundle budget:** app-page JS ≤ 300kb gzip, CSS ≤ 50kb (Tailwind purge on; Radix tree-shaken; lazy-load heavy/rare surfaces). Track delta vs pre-refactor; regression fails CI.
- **CI gate order:** lint (incl. flat + no-raw-color rules) → typecheck → Vitest (incl. contrast/target-size/token-resolve) → build (bundle budget) → Playwright snapshots. All green before merge.
