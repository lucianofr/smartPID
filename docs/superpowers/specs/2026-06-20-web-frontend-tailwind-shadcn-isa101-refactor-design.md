# Web Frontend Refactor — Tailwind v4 + shadcn, ISA-101-first (Design)

- **Date:** 2026-06-20
- **Status:** Design (approved in brainstorming; pending user review of this written spec)
- **Branch:** `refactor/web-tailwind-shadcn-isa101` (off `main`, in worktree `.worktrees/web-isa101-refactor`)
- **Authority doc this refactor amends:** `docs/superpowers/specs/2026-06-18-web-frontend-design-system-design.md` (the web UI token/component/theme authority per `CLAUDE.md`)
- **Related:** `docs/identidade_visual_ISA101.md`, `docs/superpowers/specs/2026-06-18-web-hmi-react-migration-design.md`

---

## 1. Problem & current state

`packages/smart_pid_web/` is a mature React + Vite + TS app (≈227 tracked files) that already implements all 8 web fatias and 5 ISA-101-derived themes. Styling today is **plain per-component CSS** (`NavRail.css`, `AlarmBar.css`, …) keyed on a **CSS-custom-property token contract**, with **Playwright visual-regression snapshots** (5 themes × {320, 768, 1024, 1440}) and Vitest behavior tests.

The user wants the frontend **modernized and more beautiful** using Tailwind, shadcn, and Magic UI — **while remaining ISA-101 compliant**. The driver is twofold (confirmed): **re-engineer the styling layer** (plain CSS → Tailwind + shadcn) **and raise visual execution to instrument-grade**, keeping the ISA-101 visual language.

### Central tension (resolved)

ISA-101 §2 and the design-system spec **forbid exactly what Magic UI provides**: gradients, shadows, bevels, glows, decorative animation, and color in the normal state (color is reserved for alarms; never green for "ok"). Magic UI's catalog (gradient borders, beams, shimmer, marquee, particles) is the prohibited list.

**Decisions taken in brainstorming (user choices):**

1. **Visual stance — "ISA-101 wins everywhere."** Both operator and peripheral screens stay strictly ISA-101. "Modern" = precision, spacing, tabular type, flawless states — not ornament. *Instrumento, não dashboard.*
2. **Driver — "Both."** Migrate the engine to Tailwind + shadcn **and** lift execution to premium/instrument-grade.
3. **Sequencing — "C, big-bang."** Rebuild all surfaces on the new engine at once, remove all plain `.css` together, regenerate all visual snapshots as one gated batch. (User overrode the recommended pilot-first option; accepted with the mitigations in §9.)

## 2. Goals / Non-goals

**Goals**

- Replace plain per-component CSS with **Tailwind v4 (CSS-first)** utilities **bound to the existing token contract** — Tailwind is tooling, not a look.
- Adopt **shadcn** primitives (Radix-backed: a11y, keyboard, focus) **restyled flat** to ISA-101 tokens.
- Preserve the **5 themes** (Dark Room, ISA-101, MD3 dark, MD3 light, Ocean) via `data-theme`, unchanged in behavior.
- Raise visual execution to a defined **instrument-grade standard** (§6).
- Keep all behavior/unit tests green; regenerate visual snapshots as a reviewed batch; keep the **contrast matrix** as a build gate.

**Non-goals**

- No Magic UI (rejected — see §10).
- No change to PID / fuzzy / RL / OPC logic, EventBus, persistence, or REST/WS contracts.
- No new features, routes, or screens. No renaming of token contract names.
- No change to data layer (TanStack Query, WebSocket envelope, uPlot integration).
- No desktop wrapper. Browser/localhost only (unchanged).

## 3. Engine architecture

**Tailwind v4 + shadcn, both bound to the existing CSS-var token contract.**

- **Token bridge.** Tailwind v4 `@theme inline` maps utilities onto the existing CSS vars:
  `--color-bg: var(--bg)`, `--color-surface: var(--surface)`, `--color-surface-container-high: var(--surface-container-high)`, `--color-text: var(--text)`, alarm/state/trend/bar tokens likewise; spacing → `--sp-*`; radius → `--radius-card/-control/-pill`; type → `--font-ui/--font-data` + the clamp scale; motion → `--dur-*` / `--ease-*`. The **5 themes keep working unchanged via `[data-theme]` on `<html>`** — Tailwind reads the vars; it never owns the palette.
- **No raw colors in markup.** Components use token utilities (`bg-surface text-text border-border`), never `bg-zinc-800` or hex. A **lint rule blocks non-token color utilities** so "color = alarm only" cannot leak in.
- **shadcn, restyled flat at install.** Pull primitives (Dialog, DropdownMenu, Tabs, Select, Tooltip, Switch, Slider, Command, Toast) for a11y/keyboard/focus, then strip to ISA-101: `--radius: 0` by default (MD3 themes override via token), remove every `shadow-*`, recolor to tokens. Replaces the hand-rolled `src/components/ui/Dialog.tsx`.
- **Exact Tailwind v4 + shadcn setup pinned via context7 at plan time** (CSS-first config, `@theme inline`, shadcn Tailwind-v4 init) — not guessed during design.

## 4. Tokens, themes, contrast gate

- **Token contract is the law.** Existing token names stay verbatim (the stable contract the design-system spec defines). The refactor **consumes** tokens; it does not rename. Tailwind utilities are generated *from* them.
- **5 themes preserved**, each a `[data-theme="…"]` block of var overrides. MD3 radius/font overrides resolve through the token layer (Tailwind `--radius` → `var(--radius-card)` which MD3 sets to 12px). No theme logic moves into Tailwind config.
- **Self-hosted fonts unchanged:** IBM Plex Sans / Mono (MD3 → Roboto / Roboto Mono). No CDN.
- **Contrast matrix = build gate (kept).** ISA-101 §8.4: CRIT/WARN distinguishable in hue **and** luminance, ≥4.5:1 (ISA-101 ≥5:1) per theme. Programmatic check stays a CI gate; new snapshots are blessed only after it passes.
- **Reduced-motion path kept.** `prefers-reduced-motion: reduce` → no blink (weight 700 + underline + filled icon); transitions → opacity/≈0ms. Tailwind motion utilities wired to respect it.

## 5. Scope & component map (big-bang — all surfaces)

Every surface migrates plain `.css` → Tailwind utilities + shadcn primitives. **DOM structure, `data-testid`, ARIA, and props are frozen.**

| Group | Components | Notes |
|---|---|---|
| Shell | AppShell, NavRail, TopBar, StatusIndicator, ThemeSwitcher | nav rail 64/224px tokens; persistent alarm bar = safety chrome on every route |
| Cards/bars | ControllerCard, AnalogBar, LoopHealthRow | **AnalogBar = the boldness budget**: real tick scale, on-scale SP/limit markers, right-aligned tabular numerals, fixed decimal column. No sparklines. |
| Faceplate | Faceplate (vitrine) | PV `--text-3xl` mono; segmented AUTO/MAN/CAS; AI RUN/PAUSE/STOP; CO slider (shadcn Slider, MAN-only); apply-tuning = strong-border button → confirm modal (NOT alarm color) |
| Alarms | AlarmBar, AlarmPanel, AlarmConfigForm | 3 redundant channels (color + icon shape + text); abrupt value change; icon-only blink |
| Trends | RealtimeTrend, MultiTrendChart (uPlot), Period/Series selectors, ExportButton | uPlot stays; its colors read trend tokens via JS opts; neutral gray plot bg |
| Exec | ExecutiveKPICard, TuningRecommendationCard | only sanctioned big-number hero; color only when off-target |
| Peripheral | LoginPage, ConnectionPanel, TagBrowser, loop-config dialogs (LoopConfigDialog, AiPanel, CardControls, ConfirmApplyTuningDialog), Simulator | shadcn forms/dialogs/menus; central login card, no hero; flat ISA-101 (per "everywhere") |
| Primitives | `src/components/ui/*` | hand-rolled Dialog → shadcn; add Select/Tabs/Tooltip/Switch/Slider/Command/Toast as needed |

**CSS files removed** (→ utilities / `@apply`): `NavRail.css`, `AlarmBar.css`, `AlarmPanel.css`, `AlarmConfigForm.css`, `MultiTrend.css`, `ConnectionPanel.css`, `TagBrowser.css`, `ExecutiveKPICard.css`.

## 6. Instrument-grade polish standard (verifiable)

- **Tabular numerals** everywhere process data appears — fixed decimal column; values never reflow/jump (`font-variant-numeric: tabular-nums`, `--font-data`).
- **4px rhythm enforced** — all spacing from `--sp-*`; intentional hierarchy, no uniform padding, no magic pixel values.
- **Hierarchy from scale + weight + gray only** — never color. PV dominant; SP/CO secondary; labels `--text-secondary`.
- **All 5 interactive states designed** for every control: rest / hover (one tonal surface step up, **no shadow/lift**) / focus (`--focus-ring` always visible, keyboard) / active (surface step down, `translateY(0)` — no fake displacement) / disabled (`--text-disabled`).
- **Pixel-grid alignment** — cards, bars, baselines align to a strict grid; AnalogBar ticks align to the real scale.
- **Motion compositor-only** — `transform` / `opacity` / `clip-path`; never `width/height/top/left/margin`. Durations from `--dur-*`.
- **Flat enforced** — zero `box-shadow`, zero gradient, zero bevel (lint-blocked).

## 7. Testing strategy

- **Behavior/unit (Vitest) stay green.** DOM, `data-testid`, ARIA, and props frozen → existing asserts (`Faceplate.test.tsx`, `ControllerCard.test.tsx`, alarm/severity, validation, command/api, AuthContext, etc.) keep passing. Any red here = unintended contract change, not expected churn.
- **Playwright visual snapshots regenerated as one batch** — 5 themes × {320, 768, 1024, 1440}. New baselines committed only after manual review of the rendered diffs.
- **Contrast matrix gate** runs and passes before baselines are blessed.
- **a11y** — keyboard nav + reduced-motion verified (Radix helps); focus-order asserts on key dialogs.
- **TDD where logic changes** (rare — mostly styling): red → green → commit.

## 8. Governance & branch strategy

- **Spec-first (CLAUDE.md mandate).** The design-system authority spec (`2026-06-18-web-frontend-design-system-design.md`) is updated **alongside** code: new engine (Tailwind v4 + shadcn), the token-bridge mechanism, flat-shadcn rules, Magic UI as rejected option. Update `docs/smartPIDv2.md` and `docs/identidade_visual_ISA101.md` where touched. **No UI commit without the corresponding spec update.**
- **Branch from `main`** (web app lives there). Work on `refactor/web-tailwind-shadcn-isa101`. Never commit to `main`.

### Pre-req 0 — reconcile desynced specs (blocking, before implementation)

Branch audit (2026-06-20): the web specs are **not on `main`** — `main` has the app + only the fatia2 spec; the full set (design-system authority + 10 web specs) lives on `docs/web-hmi-implementation-plans`; `feat/windows-installers` has the spec files on disk but uncommitted. **Before implementation**, bring the design-system authority spec (and relevant fatia specs) onto the refactor branch (merge or cherry-pick from `docs/web-hmi-implementation-plans`), so the governance "update the spec alongside code" rule is satisfiable. Resolve with the user whether `main` should first absorb those specs.

## 9. Risks & mitigations (big-bang / option C)

| Risk | Mitigation |
|---|---|
| All visual snapshots red at once | Freeze DOM contracts; regenerate + review as one gated batch; contrast gate must pass first |
| ISA-101 leak via Tailwind raw colors | Lint rule blocks non-token color utilities |
| shadcn defaults smuggle shadows/radius | Restyle-at-install (radius 0, no shadow) + flat-enforcement lint gate |
| uPlot canvas not Tailwind-able | Keep uPlot styling via trend tokens in JS opts, not utilities |
| Long "all red" window (inherent to C) | Single cohesive branch; full Vitest + Playwright + contrast suite green before merge |
| Behavior tests break from markup drift | DOM/test-id/ARIA frozen by rule; any red treated as a contract bug, not churn |

## 10. Rejected options

- **Magic UI (all of it).** Its components are gradient/glow/motion-based — the ISA-101 §2 prohibited list. No legitimate home under "ISA-101 wins everywhere." Recorded here so the decision is traceable.
- **Visual stance: "split operator/peripheral" and "modern-first / relax ISA-101."** Rejected in favor of "ISA-101 everywhere."
- **Sequencing: pilot-first (A) and incremental sweep (B).** User chose big-bang (C). A/B noted as lower-risk alternatives if C stalls.

## 11. Acceptance criteria

- All plain per-component `.css` files in §5 removed; styling via Tailwind utilities/`@apply` + restyled shadcn.
- Tailwind utilities resolve entirely through the existing token contract; **no raw color/hex in markup** (lint-enforced).
- 5 themes render correctly via `data-theme`; MD3 radius/font overrides intact.
- Vitest suite green with frozen DOM/test-id/ARIA.
- Playwright visual baselines regenerated and reviewed; **contrast matrix gate passes** for every theme.
- `prefers-reduced-motion` and keyboard a11y verified.
- Design-system authority spec (and touched identity docs) updated in the same change set.
- Magic UI absent; zero `box-shadow`/gradient/bevel in output (lint-enforced).
