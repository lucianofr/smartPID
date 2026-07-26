# Phase 2 — Frontend Foundation (Recorder/Phosphor) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the legacy `packages/smart_pid_web/src/` tree and scaffold the new frontend foundation: the §6.4 token contract with the exact Recorder (§6.5) and Phosphor (§6.6) values, self-hosted fonts, `ThemeProvider` with legacy-value migration, all 17 primitives with component tests, the re-established no-raw-color source guard, the contrast/token/bundle gates (fonts included), and the committed hermetic OpenAPI codegen chain.

**Architecture:** Foundation-only phase — no routes, pages, features, realtime, or data fetching (phases 3+). Everything is either a CSS token layer (`src/theme/`), a pure lib module (`src/lib/`), a presentational primitive (`src/components/`), or a gate (Vitest tests + Node scripts). Primitives are shadcn-style compositions over the `radix-ui` v1.6 monopackage, styled exclusively through §6.4 tokens bridged into Tailwind v4 utilities via `@theme inline`.

**Tech Stack:** React 18.3 (pinned), Vite 5, TypeScript 5.5, Tailwind v4 (`@tailwindcss/vite`, CSS-first), `radix-ui` 1.6, `cmdk` 1.1, `@tanstack/react-virtual` 3, uPlot 1.6.31, Vitest 2 + Testing Library, `wcag-contrast` 3, `openapi-typescript` 7, Python 3.13 + FastAPI (schema dump only).

## Global Constraints

- **Worktree:** all work happens in the `web-frontend-rewrite` worktree. Frontend commands run with cwd `packages/smart_pid_web`; backend commands run with cwd = repo root.
- **Sequencing:** this plan executes **after phases 0 and 1 are merged**. Task 25 (codegen) asserts the phase-0 schema surface (`/users` routes, lowercase `admin`/`user` role enum, `/auth/me`). Running Task 25 before phase 0 lands fails its test by design.
- **E2E is dark in this phase (spec §13):** the 13 Playwright specs in `e2e/` are retained on disk but MUST NOT be run as a phase-2 gate (`npm run test:e2e` would fail — no routes exist). Re-greening starts in phase 4. Task 24 documents this in `docs/ci-gates.md`. Do not delete or edit anything under `e2e/`, and do not delete the `*-snapshots/` directories (old visual baselines are deleted in phase 11, spec §12).
- **Token contract is closed (spec §6.4):** components consume ONLY the 43 contract custom properties (listed in Task 2). Poetic names ("paper", "void") are comments, never selectors. No component may hardcode a color.
- **Exact theme values:** Recorder and Phosphor hex values are copied verbatim from spec §6.5/§6.6 — never "adjusted".
- **UI copy is pt-BR.** Accessible names preserved verbatim where they exist in the retained E2E suite: `Usuário`, `Senha`, `Entrar`, `Salvar`, `Fechar`. In this phase that binds the Dialog/Toast close affordances: `aria-label="Fechar"`.
- **Typography (spec §6.2):** every numeral renders in Geist Mono (`.numeric` → `--font-data`, `font-variant-numeric: tabular-nums`, `font-feature-settings: 'zero' 1`). Archivo Expanded (display) never renders digits. `font-display: swap`, both families preloaded.
- **Budgets:** combined font transfer ≤ 160 KB (raw woff2 — woff2 is pre-compressed); app-page entry JS ≤ 300 KB gzip; CSS ≤ 50 KB gzip.
- **A11y floors (spec §12):** text ≥ 4.5:1; non-text (traces, alarm fills, focus ring, control boundaries, state dots, bar fill) ≥ 3:1; focus ring ≥ 3:1 **and** ≥ 2 px; touch targets ≥ 44×44 (Button-class controls literal `min-h-11 min-w-11`; compact controls — Switch, desktop Slider thumb — carry a pseudo-element hit-area extension and grow to literal 44 px below the 1024 breakpoint, matching the retained e2e enforcement pattern in `e2e/target-size.spec.ts` + `src/components/ui/slider.tsx` history).
- **Motion:** global `prefers-reduced-motion: reduce` kill-switch in base CSS (spec §11). No animation in this phase beyond micro transitions; LoadingState is static (no shimmer).
- **Theme resolution (spec §6.8):** stored `spid.theme` → `recorder`. No `prefers-color-scheme` auto-switch. Legacy migration: `dark-room→phosphor`; `md3-dark`,`md3-light`,`ocean`→`recorder`; unknown→`recorder`.
- **Green never means "ok"** — state tokens are gray in normal operation (inherited rule, spec §6.4).
- **Commits:** conventional commits, matching repo history (`feat(web): …`, `test(web): …`, `feat(core): …`).
- **Run commands:** frontend `npm run test -- <file>`, `npm run typecheck`, `npm run lint`, `npm run build` (cwd `packages/smart_pid_web`); backend `uv run pytest tests/core/... -q` (cwd repo root, pytest `asyncio_mode=auto`).

## Phase position and non-goals

Spec §13 phase 2 row: *"Frontend: scaffold, tokens (§6.4 contract + both value sets), ThemeProvider + persistence migration, all 17 primitives, source guard, contrast/token gates, bundle gate incl. fonts, committed hermetic codegen."*

Non-goals (later phases): routes/router, pages, login, shell/nav, dashboard, realtime (`envelope`, `windowBuffer`, `alarmMachine` — phase 3), `apiClient`/TanStack Query wiring (phase 3), features (phases 4–10), ISA-101 visual retokenisation mapping table (phase 11 — see the interim rule in Task 2), new visual baselines (phase 11).

## Decisions resolved by this plan (spec ambiguities)

1. **ISA-101 interim block:** §6.4's token-resolution gate requires every name to resolve under every `[data-theme]`, including `isa101`, from phase 2 — but the careful 5→3 retokenisation lands in phase 11. Interim rule: Task 2 ships a `[data-theme="isa101"]` block whose values are drawn from the CURRENT ISA-101 palette (mapped 1:1 where names correspond; nearest existing gray where they don't, each marked `/* interim */`). Phase 11a replaces this block with the audited mapping table; visual-output equivalence is *phase 11's* acceptance, not phase 2's.
2. **Contrast gate scope:** the phase-2 contrast gate covers **Recorder + Phosphor** (the values spec §6.5/§6.6 claims). ISA-101 joins the gate in phase 11 with its audited values. `--text-disabled` and `--state-oos` are exempt from the 3:1 floor (WCAG 1.4.11 exempts inactive/disabled indication; Phosphor `--state-oos #3E4A57` measures ~1.9:1 by design — it reads as "faded", which IS the signal). `--rule` is exempt (spec §6.5: "hairlines, engraved grid — decorative only"); `--rule-strong` is gated. `--accent-sunk` (pressed-flash) is not text-gated; `--accent` and `--accent-hover` are.
3. **Source guard scope:** spec §12 names the re-established guard "token-only colors (`no-raw-color`)". The ISA-era box-shadow/gradient/bevel patterns are NOT carried over: the §6.9 card-row edge fade (phase 4) is a `linear-gradient` built from token `var()`s, which a gradient ban would forbid. The guard is color-only; a fixture documents that token-var gradients pass. Note: despite `docs/ci-gates.md` calling it a "lint" rule, the existing enforcement is a **Vitest** source scan (`isa101-guard.test.ts`, "Task 0.4 Vitest pivot") — the successor stays a Vitest gate; `eslint.config.js` has no color rule to port.
4. **Trend glow API:** the Phosphor halo is theme-specific but the token contract is closed (no `--trend-glow` token may be invented). `Trend` exposes `glow?: boolean`; callers decide (phase 4 passes `glow={theme === 'phosphor'}`). The `ctx.shadowBlur` ban (§6.7) is honored by construction here; the automated no-shadowBlur gate is phase-4 acceptance.
5. **AI-tick color:** §6.7 defines tick *placement*, not color. Ticks render in `--accent` (AI is interactive/system chrome; alarm colors are banned for non-alarm meaning, trace colors are banned for non-trace meaning — §6.3/§6.6 leave accent as the only legal channel).
6. **`lib/scale` + `lib/format` land in phase 2** (AnalogBar/Readout consume them); phase 3 owns `envelope`/`windowBuffer`/`alarmMachine` and extends `format`/`scale` additively without changing phase-2 signatures. Agreed with the phase-3 plan (PlanPhase03) — signatures pinned in *Interfaces exported*.
7. **Users-router assertions (Task 25)** pinned with the phase-0 plan (PlanPhase00): paths `/users` (GET+POST) and `/users/{user_id}` (PATCH+DELETE); `UserRole` enum exactly `["admin","user"]`; `GET /auth/me` exists. Do NOT assert per-route `403` response objects in the schema (plain `HTTPException` 403s are not auto-documented by FastAPI).

## File structure (end state of this phase)

```
packages/smart_pid_web/
├── index.html                      # lang=pt-BR, data-theme=recorder, font preloads, pre-paint theme script
├── openapi.json                    # committed hermetic schema dump (Task 25)
├── package.json                    # gen:api / gen:api:check scripts replaced (Task 25)
├── .gitignore                      # src/api/generated/ entry removed (Task 25)
├── bundle-baseline.json            # reset for the new tree, + fontsRawKb (Task 24)
├── docs/ci-gates.md                # rewritten gate order; E2E-dark note (Task 24)
├── docs/freeze-inventory.md        # retirement tombstone (Task 1)
├── scripts/check-bundle.mjs        # + woff2 font budget (Task 24)
├── scripts/check-codegen.mjs       # OpenAPI drift gate (Task 25)
└── src/
    ├── main.tsx  App.tsx  index.css
    ├── assets/fonts/               # fonts.css + 3 woff2 + README.md provenance (Task 3)
    ├── theme/
    │   ├── contract.ts             # THEME_IDS + CONTRACT_TOKENS (43 names)
    │   ├── tokens.css  themes.css  # §6.4 contract; §6.5/§6.6 verbatim + isa101 interim
    │   ├── ThemeProvider.tsx       # + resolveStoredTheme + LEGACY_THEME_MAP
    │   ├── themeContrast.ts        # Recorder/Phosphor hex mirror for the gate
    │   └── *.test.ts(x)            # tokenResolve, tokenBridge, fonts, contrast, provider
    ├── lib/
    │   ├── utils.ts                # cn()
    │   ├── scale.ts  format.ts     # pure modules consumed by AnalogBar/Readout
    │   └── uplotTheme.ts           # --trace-*/--trend-* → uPlot theme bridge
    ├── components/                 # the 17 primitives, PascalCase, one file each (+ .test.tsx)
    │   ├── Button.tsx  Badge.tsx  Readout.tsx  AnalogBar.tsx  Field.tsx
    │   ├── Dialog.tsx  Tooltip.tsx  Switch.tsx  Slider.tsx  Select.tsx
    │   ├── Tabs.tsx  DropdownMenu.tsx  Toast.tsx  Command.tsx
    │   ├── VirtualList.tsx  MissingState.tsx  Trend.tsx
    ├── api/generated/openapi.ts    # COMMITTED codegen output (Task 25)
    ├── test/setup.ts               # jsdom stubs (canvas, ResizeObserver, matchMedia, pointer, scrollIntoView)
    ├── __tests__/token-guard.test.ts
    └── __lintfixtures__/           # raw-color-violation, token-color-clean, gradient-token-allowed
scripts/
└── dump_openapi.py                 # repo root — hermetic app.openapi() dump (Task 25)
tests/core/unit/test_openapi_dump.py
```

No barrel files: later phases import primitives per-file (`@/components/Button`).

---

### Task 1: Delete the legacy source; scaffold the minimal shell

The old `src/` (241 files incl. tests) is deleted wholesale — spec §4: "New identity cannot be reached by patching DOM frozen to old tests". The freeze contract dies with it.

**Files:**
- Delete: `packages/smart_pid_web/src/` (entire directory: `pages/`, `realtime/`, `theme/`, `features/`, `lib/`, `components/`, `api/`, `auth/`, `test/`, `__lintfixtures__/`, `__tests__/`, `App.tsx`, `main.tsx`, `index.css`)
- Replace content: `packages/smart_pid_web/docs/freeze-inventory.md` (tombstone)
- Create: `packages/smart_pid_web/src/main.tsx`
- Create: `packages/smart_pid_web/src/App.tsx`
- Create: `packages/smart_pid_web/src/index.css`
- Create: `packages/smart_pid_web/src/lib/utils.ts`
- Create: `packages/smart_pid_web/src/test/setup.ts`
- Modify: `packages/smart_pid_web/index.html`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `cn(...inputs: ClassValue[]): string` from `@/lib/utils` (every later task uses it); jsdom stubs in `src/test/setup.ts` (already wired via `vitest.config.ts` `setupFiles`); a building `App`/`main` pair that Task 4 extends. Keeps `e2e/`, all configs, `scripts/check-bundle.mjs` untouched.

- [ ] **Step 1: Delete the old tree and retire the freeze contract**

```bash
cd packages/smart_pid_web
git rm -r -q src
```

Write `docs/freeze-inventory.md` with exactly:

```markdown
# DOM-freeze inventory — RETIRED (2026-07-26 rewrite, phase 2)

The freeze contract existed to keep the pre-rewrite Vitest suite green through the
Tailwind/shadcn ISA-101 restyle. That source tree and its suite were deleted in
phase 2 of `docs/superpowers/specs/2026-07-26-web-frontend-rewrite-design.md`.

Per spec §12: the new primitives carry their own component tests, queried by role
and accessible name (`data-testid` only where no semantic query exists). A new,
much smaller structural contract will be derived from the new primitives once
they stabilize. Nothing may cite this file as a binding contract.
```

- [ ] **Step 2: Scaffold the minimal shell**

`src/lib/utils.ts` (verbatim carry-over — it was correct):

```ts
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/** Merge conditional class names, de-duplicating conflicting Tailwind utilities. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
```

`src/index.css` (temporary — Task 2 replaces it with the token bridge):

```css
@import 'tailwindcss';
```

`src/App.tsx`:

```tsx
export function App() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-2">
      <h1 className="text-2xl font-semibold tracking-wide">SMART PID</h1>
      <p className="text-sm">Fundação do rewrite — fase 2. Rotas chegam na fase 4.</p>
    </main>
  );
}
```

`src/main.tsx`:

```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import { App } from './App';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

`src/test/setup.ts` — jsdom stubs proven by the old suite, plus pointer/scroll stubs Radix Select/DropdownMenu need:

```ts
import '@testing-library/jest-dom/vitest';

// jsdom has no canvas 2D context; uPlot defers a draw to a microtask that throws
// on ctx.clearRect after the component's synchronous try/catch has returned.
// Stub a no-op 2D context so charts mount without unhandled async errors in tests.
if (typeof HTMLCanvasElement !== 'undefined') {
  HTMLCanvasElement.prototype.getContext = (() =>
    ({
      canvas: { width: 0, height: 0 },
      clearRect: () => {},
      fillRect: () => {},
      strokeRect: () => {},
      beginPath: () => {},
      moveTo: () => {},
      lineTo: () => {},
      stroke: () => {},
      fill: () => {},
      save: () => {},
      restore: () => {},
      translate: () => {},
      scale: () => {},
      rect: () => {},
      clip: () => {},
      closePath: () => {},
      setLineDash: () => {},
      measureText: () => ({ width: 0 }),
      fillText: () => {},
      arc: () => {},
      lineWidth: 1,
      strokeStyle: '',
      fillStyle: '',
      font: '',
    })) as unknown as typeof HTMLCanvasElement.prototype.getContext;
}

// jsdom lacks ResizeObserver; @tanstack/react-virtual and Trend need one.
if (!('ResizeObserver' in globalThis)) {
  class ResizeObserverStub {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  }
  (globalThis as unknown as { ResizeObserver: typeof ResizeObserverStub }).ResizeObserver =
    ResizeObserverStub;
}

// jsdom lacks matchMedia; reduced-motion checks need it.
if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList;
}

// Radix Select/DropdownMenu call these DOM APIs jsdom does not implement.
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
if (!Element.prototype.hasPointerCapture) {
  Element.prototype.hasPointerCapture = () => false;
  Element.prototype.setPointerCapture = () => {};
  Element.prototype.releasePointerCapture = () => {};
}
```

- [ ] **Step 3: Rebase index.html on the new defaults**

Replace `index.html` content with (Task 3 adds preloads, Task 4 adds the pre-paint script):

```html
<!doctype html>
<html lang="pt-BR" data-theme="recorder">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Smart PID</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

(`lang="pt-BR"` because all UI copy is pt-BR — the old `lang="en"` was wrong for AT pronunciation.)

- [ ] **Step 4: Verify the shell is green**

Run (cwd `packages/smart_pid_web`):

```bash
npm run typecheck && npm run lint && npm run test && npm run build
```

Expected: all four exit 0. `npm run test` prints `No test files found` (vitest `passWithNoTests: true`); `npm run build` emits `dist/` with one entry JS + CSS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(web): delete legacy src, scaffold rewrite shell (spec §13 phase 2)"
```

---

### Task 2: §6.4 token contract — `tokens.css`, `themes.css`, Tailwind bridge, resolution gate

**Files:**
- Create: `packages/smart_pid_web/src/theme/contract.ts`
- Create: `packages/smart_pid_web/src/theme/tokens.css`
- Create: `packages/smart_pid_web/src/theme/themes.css`
- Replace: `packages/smart_pid_web/src/index.css`
- Test: `packages/smart_pid_web/src/theme/tokenResolve.test.ts`
- Test: `packages/smart_pid_web/src/theme/tokenBridge.test.ts`

**Interfaces:**
- Consumes: Task 1 scaffold.
- Produces: `THEME_IDS: readonly ['recorder','phosphor','isa101']`, `type ContractThemeId`, `CONTRACT_TOKENS: readonly string[]` (43 names) from `@/theme/contract`; the 43 CSS custom properties under every `[data-theme]`; Tailwind utilities used by every primitive: color (`bg-bg`, `bg-surface`, `bg-surface-sunk`, `border-rule`, `border-rule-strong`, `text-text`, `text-text-soft`, `text-text-disabled`, `ring-focus-ring`, `bg-selection`, `bg-scrim`, `bg-accent`, `bg-accent-hover`, `bg-accent-sunk`, `bg-accent-soft`, `text-on-accent`, `bg-alarm-crit`, `bg-alarm-crit-bg`, `text-alarm-crit`, … one utility family per contract color), font (`font-display`, `font-ui`, `font-data`), size (`text-2xs … text-2xl`), radius (`rounded-card`, `rounded-control`, `rounded-pill`); CSS classes `.numeric` and `.type-display`; global reduced-motion kill-switch.

- [ ] **Step 1: Write the contract module and the failing resolution test**

`src/theme/contract.ts`:

```ts
/**
 * §6.4 token contract (normative). All themes define ALL of these names.
 * Components consume ONLY these custom properties (guarded by token-guard.test.ts).
 */
export const THEME_IDS = ['recorder', 'phosphor', 'isa101'] as const;
export type ContractThemeId = (typeof THEME_IDS)[number];

export const CONTRACT_TOKENS = [
  // Surfaces
  '--bg', '--surface', '--surface-sunk',
  // Lines
  '--rule', '--rule-strong',
  // Text
  '--text', '--text-soft', '--text-disabled',
  // Focus / selection / overlay
  '--focus-ring', '--selection', '--scrim',
  // Accent
  '--accent', '--accent-hover', '--accent-sunk', '--accent-soft', '--on-accent',
  // Alarm (four severities — CRITICAL/WARNING/ADVISORY/LOG)
  '--alarm-crit', '--alarm-crit-bg', '--alarm-warn', '--alarm-warn-bg',
  '--alarm-adv', '--alarm-adv-bg', '--alarm-log', '--on-alarm',
  // State (gray in normal operation — green never means "ok")
  '--state-running', '--state-stopped', '--state-error', '--state-oos',
  // Trend
  '--trace-pv', '--trace-sp', '--trace-co',
  '--trend-grid', '--trend-axis', '--trend-bg',
  '--trend-pv-width', '--trend-sp-width', '--trend-co-width',
  // Bar
  '--bar-track', '--bar-fill', '--bar-marker',
  // Type
  '--font-display', '--font-ui', '--font-data',
] as const;
```

`src/theme/tokenResolve.test.ts` (successor of the old `tokenResolve.test.ts` — jsdom resolves `[data-theme]` custom properties through `getComputedStyle` once the CSS is injected as a `<style>` element):

```ts
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { CONTRACT_TOKENS, THEME_IDS } from './contract';

const CSS_FILES = ['src/theme/tokens.css', 'src/theme/themes.css'];
let styleEl: HTMLStyleElement;

function resolved(token: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(token).trim();
}

beforeAll(() => {
  styleEl = document.createElement('style');
  styleEl.textContent = CSS_FILES.map((p) => readFileSync(resolve(process.cwd(), p), 'utf8')).join('\n');
  document.head.appendChild(styleEl);
});

afterAll(() => {
  styleEl.remove();
  document.documentElement.removeAttribute('data-theme');
});

describe('§6.4 token contract resolves under every [data-theme]', () => {
  it.each(THEME_IDS)('%s: every contract token resolves non-empty', (id) => {
    document.documentElement.setAttribute('data-theme', id);
    for (const token of CONTRACT_TOKENS) {
      expect(resolved(token), `${id} ${token}`).not.toBe('');
    }
  });

  it('--bg re-resolves on a data-theme flip (runtime swap, not a static snapshot)', () => {
    document.documentElement.setAttribute('data-theme', 'recorder');
    expect(resolved('--bg')).toBe('#F7F8FA');
    document.documentElement.setAttribute('data-theme', 'phosphor');
    expect(resolved('--bg')).toBe('#0A0E14');
  });

  it('trend widths carry px units consumable by parseFloat (uplotTheme contract)', () => {
    document.documentElement.setAttribute('data-theme', 'recorder');
    expect(resolved('--trend-pv-width')).toBe('2px');
    expect(Number.parseFloat(resolved('--trend-sp-width'))).toBe(1.5);
  });
});
```

- [ ] **Step 2: Run it to see it fail**

Run: `npm run test -- src/theme/tokenResolve.test.ts`
Expected: FAIL — first with `Cannot find module './contract'` resolved after writing `contract.ts`, then `ENOENT … src/theme/tokens.css` (CSS not written yet).

- [ ] **Step 3: Write `tokens.css` (theme-agnostic) and `themes.css` (§6.5/§6.6 verbatim + isa101 interim)**

`src/theme/tokens.css`:

```css
/*
 * Theme-agnostic tokens. Theme-varying COLOR tokens live in themes.css under
 * [data-theme]. The §6.4 type tokens resolve here (:root) — one type system,
 * three palettes. The Archivo/Geist files behind these stacks are wired by
 * src/assets/fonts/fonts.css (Task 3); the fallbacks are metric-compatible
 * (§6.2: system-ui / ui-monospace, minor reflow on first paint accepted).
 */
:root {
  /* Type faces (§6.2). --font-display is Archivo used at wdth 125 via .type-display. */
  --font-display: 'Archivo Variable', system-ui, -apple-system, 'Segoe UI', sans-serif;
  --font-ui: 'Archivo Variable', system-ui, -apple-system, 'Segoe UI', sans-serif;
  --font-data: 'Geist Mono', ui-monospace, 'SF Mono', 'Cascadia Mono', monospace;

  /* Type scale */
  --text-2xs: 0.6875rem; --text-xs: 0.75rem; --text-sm: 0.8125rem;
  --text-base: 0.9375rem;
  --text-lg: clamp(1rem, 0.95rem + 0.25vw, 1.125rem);
  --text-xl: clamp(1.25rem, 1.1rem + 0.6vw, 1.5rem);
  --text-2xl: clamp(1.75rem, 1.4rem + 1.2vw, 2.5rem);
  --fw-regular: 400; --fw-medium: 500; --fw-semibold: 600; --fw-bold: 700;

  /* Shape — instrument chrome is square; pills are reserved for count chips. */
  --radius-card: 0px; --radius-control: 0px; --radius-pill: 999px;

  /* Motion */
  --dur-fast: 120ms; --dur-normal: 200ms; --dur-slow: 320ms;
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-standard: cubic-bezier(0.2, 0, 0, 1);
}
```

`src/theme/themes.css` — the Recorder and Phosphor blocks are **copied verbatim from spec §6.5 and §6.6** (values and comments). The isa101 block is the documented interim (decision 1):

```css
/* ============================================================================
 * Theme value sets. Recorder (§6.5) and Phosphor (§6.6) are NORMATIVE — hex
 * values verbatim from the spec; do not "adjust". ISA-101 is an INTERIM block
 * (current-palette values under the new names) until phase 11a lands the
 * audited 5→3 retokenisation with unchanged visual output.
 * ========================================================================= */

[data-theme="recorder"] {
  --bg: #F7F8FA;            /* cool paper */         --surface: #FFFFFF;
  --surface-sunk: #EEF1F5;  /* chart wells, inputs */
  --rule: #DCE2EA;          /* hairlines, engraved grid — decorative only */
  --rule-strong: #7C8894;   /* control boundaries — 3.62:1 on surface */
  --text: #16202B;  --text-soft: #5A6875;  --text-disabled: #8B95A0;
  --focus-ring: #16202B;  --selection: #DCEBEB;  --scrim: rgba(10, 14, 20, 0.5);
  --accent: #0E6B6B;  --accent-hover: #0B5757;  --accent-sunk: #083F3F;
  --accent-soft: #E1EEEE;  --on-accent: #FFFFFF;                /* 6.30:1 */
  --alarm-crit: #C02026;  --alarm-crit-bg: #F7DCDC;
  --alarm-warn: #9E5E00;  --alarm-warn-bg: #F5E3CC;             /* 4.87:1 on bg */
  --alarm-adv:  #6B4FA8;  --alarm-adv-bg:  #E8E1F4;
  --alarm-log:  #5A6875;  --on-alarm: #FFFFFF;                  /* ≥5.18:1 on all fills */
  --state-running: #7C8894;  --state-stopped: #5A6875;          /* gray, never green */
  --state-error: #C02026;    --state-oos: #B0B8C0;
  --trace-pv: #1B4F87;  --trace-sp: #7C8894;  --trace-co: #BC7211;  /* 3.34:1 on sunk */
  --trend-grid: #E4E9EF;  --trend-axis: #9DA9B5;  --trend-bg: #EEF1F5;
  --trend-pv-width: 2px;  --trend-sp-width: 1.5px;  --trend-co-width: 1.5px;
  --bar-track: #EEF1F5;  --bar-fill: #5A6875;  --bar-marker: #16202B;
}

[data-theme="phosphor"] {
  --bg: #0A0E14;            /* void */               --surface: #131A24;  /* panel */
  --surface-sunk: #0E141C;  /* chart wells — new in v2; traces ≥ 3:1 on it */
  --rule: #253040;
  --rule-strong: #54697F;   /* 3.08:1 on surface */
  --text: #D6DEE8;  --text-soft: #8894A3;  /* 5.67:1 on surface (v1 value was 4.46 on raised) */
  --text-disabled: #55616E;
  --focus-ring: #D6DEE8;  --selection: #16304A;  --scrim: rgba(0, 0, 0, 0.6);
  --accent: #23A6A6;  --accent-hover: #2FBDBD;  --accent-sunk: #1A7F7F;
  --accent-soft: #10302F;  --on-accent: #0A0E14;                /* 6.52:1 — white FAILS here */
  --alarm-crit: #FF4D4D;  --alarm-crit-bg: #3A0E0E;
  --alarm-warn: #FFA51F;  --alarm-warn-bg: #3A2A00;
  --alarm-adv:  #A98BFF;  --alarm-adv-bg:  #241A3E;
  --alarm-log:  #8894A3;  --on-alarm: #0A0E14;                  /* ≥5.91:1 on all fills */
  --state-running: #5E7080;  --state-stopped: #8894A3;
  --state-error: #FF4D4D;    --state-oos: #3E4A57;
  --trace-pv: #9FC8F0;  --trace-sp: #6E7B8A;  --trace-co: #E39B3D;
  --trend-grid: #16202E;  --trend-axis: #3E4E63;  --trend-bg: #0A0E14;
  --trend-pv-width: 2px;  --trend-sp-width: 1.5px;  --trend-co-width: 1.5px;
  --bar-track: #0E141C;  --bar-fill: #5E7080;  --bar-marker: #8FB6D6;
}

/*
 * ISA-101 — INTERIM (phase 2). Values are the CURRENT isa101 palette mapped onto
 * the §6.4 names so the theme attribute + token names resolve from phase 2
 * (token-resolution gate). Phase 11a replaces this block with the audited 5→3
 * mapping table; visual-output equivalence is verified there, not here.
 * ISA-101 keeps its own trace rules (§6.3): gray-until-abnormal PV, solid blue SP.
 */
[data-theme="isa101"] {
  --bg: #1E1E1E;  --surface: #2D2D30;
  --surface-sunk: #252526;  /* was --field-bg */
  --rule: #3A3A3D;          /* was --divider */
  --rule-strong: #57575B;   /* was --border-strong */
  --text: #E0E0E0;  --text-soft: #ABABAB;  --text-disabled: #666666;
  --focus-ring: #C8C8C8;  --selection: #3A3A3D;  /* interim */  --scrim: rgba(0, 0, 0, 0.6);  /* interim */
  --accent: #57575B;        /* interim — ISA-101 has no accent; neutral gray chrome */
  --accent-hover: #666666;  /* interim */  --accent-sunk: #454548;  /* interim */
  --accent-soft: #333337;   /* interim */  --on-accent: #FFFFFF;    /* interim */
  --alarm-crit: #FF3333;  --alarm-crit-bg: #3A0E0E;
  --alarm-warn: #FF8800;  --alarm-warn-bg: #3A2200;
  --alarm-adv:  #AA55FF;  --alarm-adv-bg:  #260A3A;
  --alarm-log:  #ABABAB;  --on-alarm: #FFFFFF;
  --state-running: #9A9A9A;  --state-stopped: #ABABAB;
  --state-error: #FF3333;    --state-oos: #666666;
  --trace-pv: #E0E0E0;  --trace-sp: #33AAFF;  --trace-co: #FFB000;
  --trend-grid: #3A3A3D;  --trend-axis: #57575B;  --trend-bg: #252526;
  --trend-pv-width: 1.5px;  --trend-sp-width: 1.5px;  --trend-co-width: 1.5px;
  --bar-track: #252526;  --bar-fill: #9A9A9A;  --bar-marker: #CCCCCC;
}
```

- [ ] **Step 4: Replace `src/index.css` with the bridge + base layer**

```css
@import 'tailwindcss';
@import './theme/tokens.css';
@import './theme/themes.css';

/*
 * Token bridge (Tailwind v4, CSS-first).
 *
 * `@theme inline` maps Tailwind utility namespaces onto the §6.4 contract
 * variables. Because `inline` makes each utility emit `var(--…)` instead of
 * snapshotting a value, every utility re-resolves at runtime when [data-theme]
 * flips. This block ONLY references contract variables; it never redefines them.
 */
@theme inline {
  /* Colors → var(--…) from themes.css ([data-theme]) */
  --color-bg: var(--bg);
  --color-surface: var(--surface);
  --color-surface-sunk: var(--surface-sunk);
  --color-rule: var(--rule);
  --color-rule-strong: var(--rule-strong);
  --color-text: var(--text);
  --color-text-soft: var(--text-soft);
  --color-text-disabled: var(--text-disabled);
  --color-focus-ring: var(--focus-ring);
  --color-selection: var(--selection);
  --color-scrim: var(--scrim);
  --color-accent: var(--accent);
  --color-accent-hover: var(--accent-hover);
  --color-accent-sunk: var(--accent-sunk);
  --color-accent-soft: var(--accent-soft);
  --color-on-accent: var(--on-accent);
  --color-alarm-crit: var(--alarm-crit);
  --color-alarm-crit-bg: var(--alarm-crit-bg);
  --color-alarm-warn: var(--alarm-warn);
  --color-alarm-warn-bg: var(--alarm-warn-bg);
  --color-alarm-adv: var(--alarm-adv);
  --color-alarm-adv-bg: var(--alarm-adv-bg);
  --color-alarm-log: var(--alarm-log);
  --color-on-alarm: var(--on-alarm);
  --color-state-running: var(--state-running);
  --color-state-stopped: var(--state-stopped);
  --color-state-error: var(--state-error);
  --color-state-oos: var(--state-oos);
  --color-trace-pv: var(--trace-pv);
  --color-trace-sp: var(--trace-sp);
  --color-trace-co: var(--trace-co);
  --color-trend-grid: var(--trend-grid);
  --color-trend-axis: var(--trend-axis);
  --color-trend-bg: var(--trend-bg);
  --color-bar-track: var(--bar-track);
  --color-bar-fill: var(--bar-fill);
  --color-bar-marker: var(--bar-marker);

  /* Fonts */
  --font-display: var(--font-display);
  --font-ui: var(--font-ui);
  --font-data: var(--font-data);

  /* Font sizes (text-2xs … text-2xl utilities) */
  --text-2xs: var(--text-2xs);
  --text-xs: var(--text-xs);
  --text-sm: var(--text-sm);
  --text-base: var(--text-base);
  --text-lg: var(--text-lg);
  --text-xl: var(--text-xl);
  --text-2xl: var(--text-2xl);

  /* Radius */
  --radius-card: var(--radius-card);
  --radius-control: var(--radius-control);
  --radius-pill: var(--radius-pill);

  /* Durations / easing */
  --transition-duration-fast: var(--dur-fast);
  --transition-duration-normal: var(--dur-normal);
  --transition-duration-slow: var(--dur-slow);
  --ease-out: var(--ease-out);
  --ease-standard: var(--ease-standard);
}

@layer base {
  html,
  body,
  #root {
    height: 100%;
  }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--font-ui);
    font-size: var(--text-base);
  }
  ::selection {
    background: var(--selection);
  }

  /* §6.2 display face: Archivo Expanded (wdth 125). NEVER for numerals. */
  .type-display {
    font-family: var(--font-display);
    font-stretch: 125%;
    font-weight: var(--fw-semibold);
    letter-spacing: 0.01em;
  }

  /* §6.2 data face: every numeral in the product. Tabular + slashed zero. */
  .numeric {
    font-family: var(--font-data);
    font-variant-numeric: tabular-nums;
    font-feature-settings: 'zero' 1;
    letter-spacing: 0;
  }

  /* §11 global reduced-motion policy (floor, not per-feature). */
  @media (prefers-reduced-motion: reduce) {
    *,
    *::before,
    *::after {
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
      scroll-behavior: auto !important;
    }
  }
}
```

Also update `src/App.tsx` to use the tokens (still no ThemeProvider — Task 4):

```tsx
export function App() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-2 bg-bg text-text">
      <h1 className="type-display text-2xl">SMART PID</h1>
      <p className="text-sm text-text-soft">Fundação do rewrite — fase 2. Rotas chegam na fase 4.</p>
    </main>
  );
}
```

- [ ] **Step 5: Run the resolution test to see it pass**

Run: `npm run test -- src/theme/tokenResolve.test.ts`
Expected: PASS (5 tests: 3 themes × non-empty sweep, flip test, px-width test).

- [ ] **Step 6: Write the bridge source test (guards the `inline` keyword and the import order)**

`src/theme/tokenBridge.test.ts`:

```ts
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

// Vitest runs from the package root (`npm run test` in packages/smart_pid_web).
const css = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8');

describe('Tailwind v4 token bridge (src/index.css)', () => {
  it('imports tailwindcss and the token-contract stylesheets', () => {
    expect(css).toMatch(/@import\s+['"]tailwindcss['"]/);
    expect(css).toMatch(/@import\s+['"]\.\/theme\/tokens\.css['"]/);
    expect(css).toMatch(/@import\s+['"]\.\/theme\/themes\.css['"]/);
  });

  it('declares an @theme inline block (plain @theme would freeze values at build time)', () => {
    expect(css).toMatch(/@theme\s+inline\s*\{/);
    const plainTheme = /@theme\s*\{[^}]*--(?:color|radius|font)-[^}]*\}/;
    expect(css).not.toMatch(plainTheme);
  });

  it('maps every §6.4 color token onto the contract variable', () => {
    for (const name of [
      'bg', 'surface', 'surface-sunk', 'rule', 'rule-strong', 'text', 'text-soft',
      'text-disabled', 'focus-ring', 'selection', 'scrim', 'accent', 'accent-hover',
      'accent-sunk', 'accent-soft', 'on-accent', 'alarm-crit', 'alarm-crit-bg',
      'alarm-warn', 'alarm-warn-bg', 'alarm-adv', 'alarm-adv-bg', 'alarm-log',
      'on-alarm', 'state-running', 'state-stopped', 'state-error', 'state-oos',
      'trace-pv', 'trace-sp', 'trace-co', 'trend-grid', 'trend-axis', 'trend-bg',
      'bar-track', 'bar-fill', 'bar-marker',
    ]) {
      expect(css, name).toMatch(new RegExp(`--color-${name}:\\s*var\\(--${name}\\)`));
    }
  });

  it('bridges fonts, sizes and radii', () => {
    expect(css).toMatch(/--font-display:\s*var\(--font-display\)/);
    expect(css).toMatch(/--font-data:\s*var\(--font-data\)/);
    expect(css).toMatch(/--text-2xs:\s*var\(--text-2xs\)/);
    expect(css).toMatch(/--radius-pill:\s*var\(--radius-pill\)/);
  });

  it('carries the §11 reduced-motion kill-switch and the two type classes', () => {
    expect(css).toMatch(/prefers-reduced-motion:\s*reduce/);
    expect(css).toMatch(/\.type-display\s*\{/);
    expect(css).toMatch(/\.numeric\s*\{/);
    expect(css).toMatch(/font-feature-settings:\s*'zero'\s*1/);
  });
});
```

- [ ] **Step 7: Run all theme tests + typecheck + build**

Run: `npm run test -- src/theme && npm run typecheck && npm run build`
Expected: 2 test files pass; build green (Tailwind v4 compiles the bridge).

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat(web): §6.4 token contract — Recorder/Phosphor verbatim values, isa101 interim, Tailwind inline bridge"
```

---

### Task 3: Self-hosted fonts — Archivo Variable + Geist Mono, swap, preload, provenance

**Files:**
- Create: `packages/smart_pid_web/src/assets/fonts/archivo-latin-var.woff2` (binary)
- Create: `packages/smart_pid_web/src/assets/fonts/geist-mono-latin-400.woff2` (binary)
- Create: `packages/smart_pid_web/src/assets/fonts/geist-mono-latin-500.woff2` (binary)
- Create: `packages/smart_pid_web/src/assets/fonts/fonts.css`
- Create: `packages/smart_pid_web/src/assets/fonts/README.md`
- Modify: `packages/smart_pid_web/src/index.css` (add one `@import`)
- Modify: `packages/smart_pid_web/index.html` (preload links)
- Test: `packages/smart_pid_web/src/theme/fonts.test.ts`

**Interfaces:**
- Consumes: `--font-display`/`--font-ui`/`--font-data` stacks from Task 2 (family names `'Archivo Variable'`, `'Geist Mono'` — must match `font-family` in the `@font-face` rules exactly).
- Produces: loadable font files under `src/assets/fonts/`; every later phase gets working type for free. Nothing else imports these directly.

- [ ] **Step 1: Write the failing fonts gate**

`src/theme/fonts.test.ts`:

```ts
import { readFileSync, statSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const root = process.cwd();
const fontsDir = resolve(root, 'src/assets/fonts');
const FILES = ['archivo-latin-var.woff2', 'geist-mono-latin-400.woff2', 'geist-mono-latin-500.woff2'];
const FONT_BUDGET_BYTES = 160 * 1024; // §6.2: combined font transfer ≤ 160 KB

describe('§6.2 self-hosted fonts', () => {
  it('ships the three committed woff2 files within the 160 KB combined budget', () => {
    let total = 0;
    for (const f of FILES) {
      const size = statSync(resolve(fontsDir, f)).size;
      expect(size, f).toBeGreaterThan(0);
      total += size;
    }
    expect(total, `combined ${Math.round(total / 1024)} KB`).toBeLessThanOrEqual(FONT_BUDGET_BYTES);
  });

  it('fonts.css declares swap-display faces matching the token stacks', () => {
    const css = readFileSync(resolve(fontsDir, 'fonts.css'), 'utf8');
    expect(css).toMatch(/font-family:\s*'Archivo Variable'/);
    expect(css).toMatch(/font-stretch:\s*62\.5%\s+125%/);
    expect(css).toMatch(/font-weight:\s*100\s+900/);
    expect((css.match(/font-family:\s*'Geist Mono'/g) ?? []).length).toBe(2);
    expect((css.match(/font-display:\s*swap/g) ?? []).length).toBe(3);
  });

  it('index.css imports fonts.css and index.html preloads all three files', () => {
    const indexCss = readFileSync(resolve(root, 'src/index.css'), 'utf8');
    expect(indexCss).toMatch(/@import\s+['"]\.\/assets\/fonts\/fonts\.css['"]/);
    const html = readFileSync(resolve(root, 'index.html'), 'utf8');
    for (const f of FILES) {
      expect(html, f).toContain(`/src/assets/fonts/${f}`);
    }
    expect((html.match(/rel="preload"\s+href="\/src\/assets\/fonts\//g) ?? []).length).toBe(3);
    expect(html).toMatch(/as="font"\s+type="font\/woff2"\s+crossorigin/);
  });
});
```

- [ ] **Step 2: Run it to see it fail**

Run: `npm run test -- src/theme/fonts.test.ts`
Expected: FAIL with `ENOENT … archivo-latin-var.woff2`.

- [ ] **Step 3: Obtain and subset the font binaries**

Run (any cwd; final `cp` targets `packages/smart_pid_web/src/assets/fonts/`):

```bash
mkdir -p packages/smart_pid_web/src/assets/fonts
cd packages/smart_pid_web/src/assets/fonts

# Archivo Variable (OFL 1.1) — master VF from the google/fonts repo, subset to
# Latin KEEPING BOTH AXES (wght+wdth). pyftsubset preserves fvar/gvar by default;
# do NOT pass any --instancer flag.
curl -L -o /tmp/Archivo-var.ttf \
  'https://raw.githubusercontent.com/google/fonts/main/ofl/archivo/Archivo%5Bwdth%2Cwght%5D.ttf'
uvx --from 'fonttools[woff]' pyftsubset /tmp/Archivo-var.ttf \
  --unicodes='U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+2074,U+20AC,U+2122,U+2212' \
  --layout-features='*' --flavor=woff2 \
  --output-file=archivo-latin-var.woff2

# Geist Mono (OFL 1.1) — Fontsource ships pre-subset Latin woff2 per weight.
npm pack @fontsource/geist-mono
tar -xzf fontsource-geist-mono-*.tgz \
  package/files/geist-mono-latin-400-normal.woff2 \
  package/files/geist-mono-latin-500-normal.woff2
mv package/files/geist-mono-latin-400-normal.woff2 geist-mono-latin-400.woff2
mv package/files/geist-mono-latin-500-normal.woff2 geist-mono-latin-500.woff2
rm -rf package fontsource-geist-mono-*.tgz

ls -la *.woff2   # sanity: three files, combined well under 160 KB
```

If the combined size exceeds 160 KB (fonts.test.ts fails), narrow the Archivo
`--unicodes` to `U+0020-00FF,U+2013-2014,U+2018-2019,U+201C-201D,U+2212` and re-subset —
pt-BR needs nothing outside Latin-1.

Write `src/assets/fonts/README.md`:

```markdown
# Self-hosted fonts (§6.2)

| File | Family | Axes / weight | License | Source |
|---|---|---|---|---|
| archivo-latin-var.woff2 | Archivo Variable | wght 100–900 · wdth 62.5–125 · Latin | OFL 1.1 | github.com/google/fonts `ofl/archivo/Archivo[wdth,wght].ttf` |
| geist-mono-latin-400.woff2 | Geist Mono | 400 static · Latin | OFL 1.1 | npm `@fontsource/geist-mono` (record version below) |
| geist-mono-latin-500.woff2 | Geist Mono | 500 static · Latin | OFL 1.1 | npm `@fontsource/geist-mono` (record version below) |

Packed @fontsource/geist-mono version: _<record the version `npm pack` resolved>_

Budget: combined ≤ 160 KB raw (woff2 is pre-compressed ≈ transfer size). Enforced
twice: `src/theme/fonts.test.ts` (source tree) and `scripts/check-bundle.mjs`
(dist output, Task 24).

Regeneration commands live in the phase-2 plan (Task 3) and are reproduced here:

    curl -L -o /tmp/Archivo-var.ttf \
      'https://raw.githubusercontent.com/google/fonts/main/ofl/archivo/Archivo%5Bwdth%2Cwght%5D.ttf'
    uvx --from 'fonttools[woff]' pyftsubset /tmp/Archivo-var.ttf \
      --unicodes='U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+2074,U+20AC,U+2122,U+2212' \
      --layout-features='*' --flavor=woff2 --output-file=archivo-latin-var.woff2

    npm pack @fontsource/geist-mono
    tar -xzf fontsource-geist-mono-*.tgz package/files/geist-mono-latin-{400,500}-normal.woff2

pt-BR coverage: U+0000-00FF includes á â ã à ç é ê í ó ô õ ú ü.
Slashed zero: applied via `font-feature-settings: 'zero' 1` (.numeric); Geist Mono
carries the `zero` feature.
```

- [ ] **Step 4: Wire the faces**

`src/assets/fonts/fonts.css`:

```css
/* §6.2 — one Archivo Variable file (wght+wdth), two Geist Mono statics. swap +
 * preload; metric-compatible fallbacks accept minor reflow on first paint. */
@font-face {
  font-family: 'Archivo Variable';
  src: url('./archivo-latin-var.woff2') format('woff2-variations');
  font-weight: 100 900;
  font-stretch: 62.5% 125%;
  font-style: normal;
  font-display: swap;
}
@font-face {
  font-family: 'Geist Mono';
  src: url('./geist-mono-latin-400.woff2') format('woff2');
  font-weight: 400;
  font-style: normal;
  font-display: swap;
}
@font-face {
  font-family: 'Geist Mono';
  src: url('./geist-mono-latin-500.woff2') format('woff2');
  font-weight: 500;
  font-style: normal;
  font-display: swap;
}
```

In `src/index.css`, add as the SECOND line (after `@import 'tailwindcss';`):

```css
@import './assets/fonts/fonts.css';
```

In `index.html`, add inside `<head>` after `<title>`:

```html
    <link rel="preload" href="/src/assets/fonts/archivo-latin-var.woff2" as="font" type="font/woff2" crossorigin />
    <link rel="preload" href="/src/assets/fonts/geist-mono-latin-400.woff2" as="font" type="font/woff2" crossorigin />
    <link rel="preload" href="/src/assets/fonts/geist-mono-latin-500.woff2" as="font" type="font/woff2" crossorigin />
```

- [ ] **Step 5: Run the gate to see it pass, then verify the build hashes the preloads**

Run: `npm run test -- src/theme/fonts.test.ts && npm run build`
Expected: PASS (3 tests). Then:

```bash
grep -o 'assets/archivo-latin-var-[^"]*\.woff2' dist/index.html
```

Expected: one hashed filename (Vite rewrote the preload href; the same hashed URL is used by the CSS `@font-face`).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(web): self-host Archivo Variable + Geist Mono (swap, preload, ≤160KB, provenance)"
```

---

### Task 4: ThemeProvider — persistence, legacy migration, pre-paint script

**Files:**
- Create: `packages/smart_pid_web/src/theme/ThemeProvider.tsx`
- Modify: `packages/smart_pid_web/src/App.tsx`
- Modify: `packages/smart_pid_web/index.html` (pre-paint script)
- Test: `packages/smart_pid_web/src/theme/ThemeProvider.test.tsx`
- Test: `packages/smart_pid_web/src/App.test.tsx`

**Interfaces:**
- Consumes: `THEME_IDS`, `ContractThemeId` from `@/theme/contract` (Task 2).
- Produces (consumed by phases 4–11):
  - `type ThemeId = 'recorder' | 'phosphor' | 'isa101'`
  - `THEMES: ReadonlyArray<{ id: ThemeId; label: string }>` (labels: `Recorder`, `Phosphor`, `ISA-101`)
  - `DEFAULT_THEME: ThemeId` (= `'recorder'`), `STORAGE_KEY` (= `'spid.theme'`)
  - `LEGACY_THEME_MAP: Readonly<Record<string, ThemeId>>`
  - `resolveStoredTheme(raw: string | null): ThemeId` (pure)
  - `ThemeProvider({ children }: { children: ReactNode }): JSX.Element`
  - `useTheme(): { theme: ThemeId; setTheme: (t: ThemeId) => void; themes: typeof THEMES }`

- [ ] **Step 1: Write the failing tests — one row per migration mapping (spec §6.8)**

`src/theme/ThemeProvider.test.tsx`:

```tsx
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { act, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import {
  DEFAULT_THEME,
  LEGACY_THEME_MAP,
  STORAGE_KEY,
  THEMES,
  ThemeProvider,
  resolveStoredTheme,
  useTheme,
} from './ThemeProvider';

function Probe() {
  const { theme, setTheme, themes } = useTheme();
  return (
    <div>
      <span data-testid="current">{theme}</span>
      <span data-testid="count">{themes.length}</span>
      <button onClick={() => setTheme('phosphor')}>phosphor</button>
    </div>
  );
}

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute('data-theme');
});

describe('theme registry (spec §6.8)', () => {
  it('ships exactly recorder, phosphor, isa101 — recorder default', () => {
    expect(THEMES.map((t) => t.id)).toEqual(['recorder', 'phosphor', 'isa101']);
    expect(DEFAULT_THEME).toBe('recorder');
    expect(STORAGE_KEY).toBe('spid.theme');
  });
});

describe('resolveStoredTheme — every §6.8 migration row', () => {
  it.each([
    ['dark-room', 'phosphor'],
    ['md3-dark', 'recorder'],
    ['md3-light', 'recorder'],
    ['ocean', 'recorder'],
  ] as const)('legacy %s → %s', (legacy, target) => {
    expect(resolveStoredTheme(legacy)).toBe(target);
    expect(LEGACY_THEME_MAP[legacy]).toBe(target);
  });

  it.each([['recorder'], ['phosphor'], ['isa101']] as const)('valid %s passes through', (id) => {
    expect(resolveStoredTheme(id)).toBe(id);
  });

  it('unknown and null fall to recorder', () => {
    expect(resolveStoredTheme('banana')).toBe('recorder');
    expect(resolveStoredTheme(null)).toBe('recorder');
  });
});

describe('ThemeProvider behavior', () => {
  it('defaults to recorder and sets data-theme on <html>', () => {
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    expect(screen.getByTestId('current').textContent).toBe('recorder');
    expect(document.documentElement.getAttribute('data-theme')).toBe('recorder');
  });

  it('migrates a legacy stored value ONCE and writes the migrated value back', () => {
    localStorage.setItem(STORAGE_KEY, 'ocean');
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    expect(screen.getByTestId('current').textContent).toBe('recorder');
    expect(localStorage.getItem(STORAGE_KEY)).toBe('recorder'); // write-back
  });

  it('persists setTheme and applies data-theme', () => {
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    act(() => {
      screen.getByText('phosphor').click();
    });
    expect(document.documentElement.getAttribute('data-theme')).toBe('phosphor');
    expect(localStorage.getItem(STORAGE_KEY)).toBe('phosphor');
  });

  it('rehydrates a persisted valid theme on remount', () => {
    localStorage.setItem(STORAGE_KEY, 'isa101');
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    expect(screen.getByTestId('current').textContent).toBe('isa101');
  });
});

describe('index.html pre-paint script stays in sync with LEGACY_THEME_MAP', () => {
  it('contains every mapping row and the valid-id list', () => {
    const html = readFileSync(resolve(process.cwd(), 'index.html'), 'utf8');
    for (const [legacy, target] of Object.entries(LEGACY_THEME_MAP)) {
      expect(html).toContain(`'${legacy}': '${target}'`);
    }
    expect(html).toContain(`['recorder', 'phosphor', 'isa101']`);
  });
});
```

`src/App.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { App } from './App';

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute('data-theme');
});

describe('App shell (phase-2 foundation)', () => {
  it('mounts ThemeProvider (data-theme applied) and shows the wordmark', () => {
    render(<App />);
    expect(screen.getByRole('heading', { name: 'SMART PID' })).toBeInTheDocument();
    expect(document.documentElement.getAttribute('data-theme')).toBe('recorder');
  });
});
```

- [ ] **Step 2: Run to see them fail**

Run: `npm run test -- src/theme/ThemeProvider.test.tsx src/App.test.tsx`
Expected: FAIL — `Cannot find module './ThemeProvider'`; App test fails on missing `data-theme`.

- [ ] **Step 3: Implement `ThemeProvider` and mount it in `App`**

`src/theme/ThemeProvider.tsx`:

```tsx
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { THEME_IDS, type ContractThemeId } from './contract';

export type ThemeId = ContractThemeId;

export const THEMES: ReadonlyArray<{ id: ThemeId; label: string }> = [
  { id: 'recorder', label: 'Recorder' },
  { id: 'phosphor', label: 'Phosphor' },
  { id: 'isa101', label: 'ISA-101' },
];

export const STORAGE_KEY = 'spid.theme';
export const DEFAULT_THEME: ThemeId = 'recorder';

/**
 * §6.8 stored-value migration. Without it a returning user with
 * `spid.theme='ocean'` silently falls to the default constant.
 * Mirrored by the pre-paint script in index.html (test-enforced).
 */
export const LEGACY_THEME_MAP: Readonly<Record<string, ThemeId>> = {
  'dark-room': 'phosphor',
  'md3-dark': 'recorder',
  'md3-light': 'recorder',
  ocean: 'recorder',
};

function isThemeId(v: string | null): v is ThemeId {
  return v !== null && (THEME_IDS as readonly string[]).includes(v);
}

/** Pure resolution: valid passthrough → legacy migration → default. */
export function resolveStoredTheme(raw: string | null): ThemeId {
  if (isThemeId(raw)) return raw;
  if (raw !== null && raw in LEGACY_THEME_MAP) return LEGACY_THEME_MAP[raw];
  return DEFAULT_THEME;
}

function readStored(): ThemeId {
  const raw = localStorage.getItem(STORAGE_KEY);
  const resolved = resolveStoredTheme(raw);
  if (raw !== null && raw !== resolved) {
    localStorage.setItem(STORAGE_KEY, resolved); // migrate once
  }
  return resolved;
}

interface ThemeCtx {
  theme: ThemeId;
  setTheme: (t: ThemeId) => void;
  themes: typeof THEMES;
}

const Ctx = createContext<ThemeCtx | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeId>(readStored);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const setTheme = (t: ThemeId) => {
    setThemeState(t);
    localStorage.setItem(STORAGE_KEY, t);
  };

  return <Ctx.Provider value={{ theme, setTheme, themes: THEMES }}>{children}</Ctx.Provider>;
}

export function useTheme(): ThemeCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider');
  return ctx;
}
```

`src/App.tsx`:

```tsx
import { ThemeProvider } from '@/theme/ThemeProvider';

export function App() {
  return (
    <ThemeProvider>
      <main className="flex min-h-screen flex-col items-center justify-center gap-2 bg-bg text-text">
        <h1 className="type-display text-2xl">SMART PID</h1>
        <p className="text-sm text-text-soft">Fundação do rewrite — fase 2. Rotas chegam na fase 4.</p>
      </main>
    </ThemeProvider>
  );
}
```

In `index.html`, add inside `<head>` immediately BEFORE `</head>` (after the preload links):

```html
    <script>
      // Pre-paint theme (§6.8): apply the persisted theme before first paint so a
      // returning Phosphor user never flashes Recorder. Mirrors LEGACY_THEME_MAP in
      // src/theme/ThemeProvider.tsx — ThemeProvider.test.tsx enforces the sync.
      (function () {
        try {
          var stored = localStorage.getItem('spid.theme');
          var legacy = { 'dark-room': 'phosphor', 'md3-dark': 'recorder', 'md3-light': 'recorder', 'ocean': 'recorder' };
          var valid = ['recorder', 'phosphor', 'isa101'];
          var theme = valid.indexOf(stored) >= 0 ? stored : legacy[stored] || 'recorder';
          document.documentElement.setAttribute('data-theme', theme);
        } catch (e) {
          /* no storage: keep the static recorder default */
        }
      })();
    </script>
```

- [ ] **Step 4: Run to see them pass**

Run: `npm run test -- src/theme/ThemeProvider.test.tsx src/App.test.tsx`
Expected: PASS (13 tests total).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(web): ThemeProvider — spid.theme persistence, §6.8 legacy migration, pre-paint script"
```

---

### Task 5: Re-establish the no-raw-color source guard + lint fixtures

Deleting the old `src/` deleted the enforcement (spec §6.4: "the guard ships *with* the tokens"). Successor of `isa101-guard.test.ts`, color-only (see plan decision 3), enforced over the WHOLE new tree from day one — no incremental dir list.

**Files:**
- Test: `packages/smart_pid_web/src/__tests__/token-guard.test.ts`
- Create: `packages/smart_pid_web/src/__lintfixtures__/raw-color-violation.tsx`
- Create: `packages/smart_pid_web/src/__lintfixtures__/token-color-clean.tsx`
- Create: `packages/smart_pid_web/src/__lintfixtures__/gradient-token-allowed.tsx`

**Interfaces:**
- Consumes: nothing (reads the file tree).
- Produces: `FORBIDDEN_PATTERNS` + `findViolations(text: string, file?: string): Violation[]` exported from the test module (phase 11 reuses them when isa101 is retokenised). Guard exemptions (fixed here, relied on by later tasks): `*.test.ts(x)` files, `__lintfixtures__/`, `api/generated/`, `assets/`, and the value mirror `theme/themeContrast.ts`.

- [ ] **Step 1: Write the fixtures**

`src/__lintfixtures__/raw-color-violation.tsx`:

```tsx
// Fixture: must trip the no-raw-color guard.
//   - `bg-[#fff]` is an arbitrary hex color utility
//   - `text-red-500` is a named Tailwind palette color utility
//   - the inline `color` is a raw hex literal
// Each of these is a §6.4 violation (color must come from a token utility).
export function RawColorViolation() {
  return (
    <div className="bg-[#fff] text-red-500" style={{ color: '#00ff00' }}>
      raw color offender
    </div>
  );
}
```

`src/__lintfixtures__/token-color-clean.tsx`:

```tsx
// Fixture: must produce NO guard hit — every color is a §6.4 token utility.
export function TokenColorClean() {
  return (
    <div className="border border-rule bg-surface text-text">
      <span className="text-text-soft">token-only</span>
      <button
        type="button"
        className="bg-accent text-on-accent outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
      >
        ok
      </button>
    </div>
  );
}
```

`src/__lintfixtures__/gradient-token-allowed.tsx`:

```tsx
// Fixture: gradients built from token var()s carry no raw color. The §6.9
// card-row edge fade (phase 4) depends on this staying legal — the guard bans
// raw COLORS, not gradients (unlike the retired ISA-101 flat-surface guard).
export function GradientTokenAllowed() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-y-0 right-0 w-8"
      style={{ backgroundImage: 'linear-gradient(to right, transparent, var(--bg))' }}
    />
  );
}
```

- [ ] **Step 2: Write the failing guard test**

`src/__tests__/token-guard.test.ts`:

```ts
import { readdirSync, readFileSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

/**
 * Token-only color source guard (§6.4 / §12 "Source guard" row). Successor of
 * the ISA-101 guard ("Task 0.4 Vitest pivot" — this is a Vitest gate, not an
 * ESLint rule). Color-only: the ISA-era box-shadow/gradient/bevel bans are NOT
 * carried over (the §6.9 edge fade is a token-var gradient).
 *
 * Scope: ALL of src/**.{ts,tsx} except:
 *  - *.test.ts(x)            tests may hold hex (contrast mirrors, style injection)
 *  - __lintfixtures__/        the violation fixtures themselves
 *  - api/generated/           machine output
 *  - assets/                  fonts (no TS anyway)
 *  - theme/themeContrast.ts   the palette VALUE MIRROR for the contrast gate
 */

const here = dirname(fileURLToPath(import.meta.url));
const srcRoot = resolve(here, '..'); // .../src

const EXCLUDE_DIRS: ReadonlySet<string> = new Set(['__lintfixtures__', 'generated', 'assets']);
const EXCLUDE_FILES: ReadonlySet<string> = new Set(['theme/themeContrast.ts']);
const TEST_FILE = /\.test\.(?:ts|tsx)$/;
const SOURCE_EXT = /\.(?:ts|tsx)$/;

type Pattern = { readonly id: string; readonly re: RegExp; readonly label: string };

export const FORBIDDEN_PATTERNS: readonly Pattern[] = [
  { id: 'hex-literal', label: 'raw hex color literal (#rgb/#rrggbb)', re: /#[0-9a-fA-F]{3}(?:[0-9a-fA-F])?(?:[0-9a-fA-F]{2})?\b/ },
  { id: 'rgb', label: 'rgb()/rgba() color function', re: /\brgba?\s*\(/ },
  { id: 'hsl', label: 'hsl()/hsla() color function', re: /\bhsla?\s*\(/ },
  { id: 'oklch', label: 'oklch() color function', re: /\boklch\s*\(/ },
  { id: 'arbitrary-color', label: 'Tailwind arbitrary color utility ([#...])', re: /\[#[0-9a-fA-F]{3,8}\]/ },
  {
    id: 'named-palette',
    label: 'named-palette Tailwind color utility (e.g. text-red-500)',
    re: /\b(?:bg|text|border|ring|fill|stroke|from|to|via)-(?:red|orange|amber|yellow|green|teal|cyan|blue|indigo|violet|purple|pink|rose|slate|gray|zinc|neutral|stone)-\d/,
  },
];

/** Strip JS/TS comments so prose does not trip the matcher (keeps `http://`). */
function stripComments(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');
}

type Violation = { readonly file: string; readonly line: number; readonly pattern: string; readonly snippet: string };

export function findViolations(text: string, file = '<input>'): Violation[] {
  const lines = stripComments(text).split('\n');
  const out: Violation[] = [];
  lines.forEach((line, i) => {
    for (const p of FORBIDDEN_PATTERNS) {
      if (p.re.test(line)) {
        out.push({ file, line: i + 1, pattern: p.label, snippet: line.trim().slice(0, 100) });
      }
    }
  });
  return out;
}

function walkSourceFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const abs = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (EXCLUDE_DIRS.has(entry.name)) continue;
      out.push(...walkSourceFiles(abs));
    } else if (entry.isFile() && SOURCE_EXT.test(entry.name) && !TEST_FILE.test(entry.name)) {
      if (EXCLUDE_FILES.has(relative(srcRoot, abs))) continue;
      out.push(abs);
    }
  }
  return out;
}

const FIXTURES_DIR = resolve(srcRoot, '__lintfixtures__');
const readFixture = (name: string): string => readFileSync(resolve(FIXTURES_DIR, name), 'utf8');

describe('token-only color source guard', () => {
  it('the whole runtime source tree is free of raw colors', () => {
    const files = walkSourceFiles(srcRoot);
    expect(files.length).toBeGreaterThan(5); // guard against a broken walk silently passing

    const violations = files.flatMap((f) => findViolations(readFileSync(f, 'utf8'), relative(srcRoot, f)));
    if (violations.length > 0) {
      const report = violations
        .map((v) => `  ${v.file}:${v.line} — ${v.pattern}\n    ${v.snippet}`)
        .join('\n');
      throw new Error(`raw-color violations in src/:\n${report}`);
    }
    expect(violations).toEqual([]);
  });

  it('flags the raw-color violation fixture', () => {
    const v = findViolations(readFixture('raw-color-violation.tsx'));
    expect(v.map((x) => x.pattern)).toEqual(
      expect.arrayContaining([
        'raw hex color literal (#rgb/#rrggbb)',
        'Tailwind arbitrary color utility ([#...])',
        'named-palette Tailwind color utility (e.g. text-red-500)',
      ]),
    );
  });

  it('passes the token-only clean fixture', () => {
    expect(findViolations(readFixture('token-color-clean.tsx'))).toEqual([]);
  });

  it('passes the token-var gradient fixture (edge-fade stays legal)', () => {
    expect(findViolations(readFixture('gradient-token-allowed.tsx'))).toEqual([]);
  });
});
```

- [ ] **Step 3: Run — the self-test rows pass, the tree sweep must pass too**

Run: `npm run test -- src/__tests__/token-guard.test.ts`
Expected: PASS (4 tests). If the sweep flags anything in Tasks 1–4 output, fix the offender (it is a real §6.4 violation), never the guard.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "test(web): re-establish no-raw-color source guard with lint fixtures"
```

---

### Task 6: Contrast gate — Recorder + Phosphor, floors from §12

**Files:**
- Create: `packages/smart_pid_web/src/theme/contrast-libs.d.ts`
- Create: `packages/smart_pid_web/src/theme/themeContrast.ts`
- Test: `packages/smart_pid_web/src/theme/themeContrast.test.ts`

**Interfaces:**
- Consumes: hex values from Task 2's `themes.css` (mirrored, sync-tested).
- Produces: `type GateThemeId = 'recorder' | 'phosphor'`, `interface ThemePalette` (29 hex fields), `PALETTES: Record<GateThemeId, ThemePalette>` from `@/theme/themeContrast` — phase 11 extends with `isa101`. Exempt-by-decision: `--text-disabled`, `--state-oos`, `--rule` (decorative), `--accent-sunk` (transient pressed flash).

- [ ] **Step 1: Write the value mirror**

`src/theme/contrast-libs.d.ts` (wcag-contrast ships untyped):

```ts
// Ambient declarations for the contrast library used by the cross-theme gate.
declare module 'wcag-contrast' {
  /** WCAG 2.x contrast ratio between two hex colors (e.g. '#16202B', '#FFFFFF'). */
  export function hex(a: string, b: string): number;
}
```

`src/theme/themeContrast.ts`:

```ts
/**
 * Per-theme token VALUE MIRROR for the build-time contrast gate. Mirrors
 * themes.css exactly (sync-tested there); guard-exempt (token-guard EXCLUDE_FILES).
 * Field → token: camelCase of the §6.4 name (surfaceSunk → --surface-sunk, …).
 */
export type GateThemeId = 'recorder' | 'phosphor';

export interface ThemePalette {
  bg: string;
  surface: string;
  surfaceSunk: string;
  ruleStrong: string;
  text: string;
  textSoft: string;
  focusRing: string;
  selection: string;
  accent: string;
  accentHover: string;
  onAccent: string;
  alarmCrit: string;
  alarmCritBg: string;
  alarmWarn: string;
  alarmWarnBg: string;
  alarmAdv: string;
  alarmAdvBg: string;
  alarmLog: string;
  onAlarm: string;
  stateRunning: string;
  stateStopped: string;
  stateError: string;
  tracePv: string;
  traceSp: string;
  traceCo: string;
  trendBg: string;
  barTrack: string;
  barFill: string;
  barMarker: string;
}

export const PALETTES: Record<GateThemeId, ThemePalette> = {
  recorder: {
    bg: '#F7F8FA',
    surface: '#FFFFFF',
    surfaceSunk: '#EEF1F5',
    ruleStrong: '#7C8894',
    text: '#16202B',
    textSoft: '#5A6875',
    focusRing: '#16202B',
    selection: '#DCEBEB',
    accent: '#0E6B6B',
    accentHover: '#0B5757',
    onAccent: '#FFFFFF',
    alarmCrit: '#C02026',
    alarmCritBg: '#F7DCDC',
    alarmWarn: '#9E5E00',
    alarmWarnBg: '#F5E3CC',
    alarmAdv: '#6B4FA8',
    alarmAdvBg: '#E8E1F4',
    alarmLog: '#5A6875',
    onAlarm: '#FFFFFF',
    stateRunning: '#7C8894',
    stateStopped: '#5A6875',
    stateError: '#C02026',
    tracePv: '#1B4F87',
    traceSp: '#7C8894',
    traceCo: '#BC7211',
    trendBg: '#EEF1F5',
    barTrack: '#EEF1F5',
    barFill: '#5A6875',
    barMarker: '#16202B',
  },
  phosphor: {
    bg: '#0A0E14',
    surface: '#131A24',
    surfaceSunk: '#0E141C',
    ruleStrong: '#54697F',
    text: '#D6DEE8',
    textSoft: '#8894A3',
    focusRing: '#D6DEE8',
    selection: '#16304A',
    accent: '#23A6A6',
    accentHover: '#2FBDBD',
    onAccent: '#0A0E14',
    alarmCrit: '#FF4D4D',
    alarmCritBg: '#3A0E0E',
    alarmWarn: '#FFA51F',
    alarmWarnBg: '#3A2A00',
    alarmAdv: '#A98BFF',
    alarmAdvBg: '#241A3E',
    alarmLog: '#8894A3',
    onAlarm: '#0A0E14',
    stateRunning: '#5E7080',
    stateStopped: '#8894A3',
    stateError: '#FF4D4D',
    tracePv: '#9FC8F0',
    traceSp: '#6E7B8A',
    traceCo: '#E39B3D',
    trendBg: '#0A0E14',
    barTrack: '#0E141C',
    barFill: '#5E7080',
    barMarker: '#8FB6D6',
  },
};
```

- [ ] **Step 2: Write the failing gate test**

`src/theme/themeContrast.test.ts`:

```ts
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { hex as wcagHex } from 'wcag-contrast';
import { PALETTES, type GateThemeId, type ThemePalette } from './themeContrast';

const THEMES: GateThemeId[] = ['recorder', 'phosphor'];
const TEXT_FLOOR = 4.5; // WCAG 1.4.3 normal text (§12)
const NONTEXT_FLOOR = 3.0; // WCAG 1.4.11 non-text (§12)

const ratio = (a: string, b: string): number => wcagHex(a, b);

describe('§6.5/§6.6 text contrast ≥ 4.5:1', () => {
  it.each(THEMES)('%s: --text and --text-soft on every surface', (id) => {
    const p = PALETTES[id];
    for (const [name, surface] of [['bg', p.bg], ['surface', p.surface], ['surface-sunk', p.surfaceSunk]] as const) {
      expect(ratio(p.text, surface), `--text on --${name}`).toBeGreaterThanOrEqual(TEXT_FLOOR);
      expect(ratio(p.textSoft, surface), `--text-soft on --${name}`).toBeGreaterThanOrEqual(TEXT_FLOOR);
    }
  });

  it.each(THEMES)('%s: --text on --selection', (id) => {
    const p = PALETTES[id];
    expect(ratio(p.text, p.selection)).toBeGreaterThanOrEqual(TEXT_FLOOR);
  });

  it.each(THEMES)('%s: --on-accent on accent + hover (spec claims 6.30 / 6.52 on accent)', (id) => {
    const p = PALETTES[id];
    expect(ratio(p.onAccent, p.accent)).toBeGreaterThanOrEqual(TEXT_FLOOR);
    expect(ratio(p.onAccent, p.accentHover)).toBeGreaterThanOrEqual(TEXT_FLOOR);
  });

  it.each(THEMES)('%s: --on-alarm on ALL four severity fills (spec: ≥5.18 / ≥5.91)', (id) => {
    const p = PALETTES[id];
    for (const fill of [p.alarmCrit, p.alarmWarn, p.alarmAdv, p.alarmLog]) {
      expect(ratio(p.onAlarm, fill), fill).toBeGreaterThanOrEqual(TEXT_FLOOR);
    }
  });

  it.each(THEMES)('%s: severity colors used AS TEXT on page surfaces (Badge contract)', (id) => {
    const p = PALETTES[id];
    for (const sev of [p.alarmCrit, p.alarmWarn, p.alarmAdv, p.alarmLog]) {
      expect(ratio(sev, p.bg), `${sev} on bg`).toBeGreaterThanOrEqual(TEXT_FLOOR);
      expect(ratio(sev, p.surface), `${sev} on surface`).toBeGreaterThanOrEqual(TEXT_FLOOR);
    }
  });
});

describe('§12 non-text contrast ≥ 3:1', () => {
  it.each(THEMES)('%s: --rule-strong (control boundaries) on surface + sunk (spec: 3.62 / 3.08)', (id) => {
    const p = PALETTES[id];
    expect(ratio(p.ruleStrong, p.surface)).toBeGreaterThanOrEqual(NONTEXT_FLOOR);
    expect(ratio(p.ruleStrong, p.surfaceSunk)).toBeGreaterThanOrEqual(NONTEXT_FLOOR);
  });

  it.each(THEMES)('%s: --focus-ring on bg and surface (§12: ring ≥3:1; the ≥2px half is a class contract)', (id) => {
    const p = PALETTES[id];
    expect(ratio(p.focusRing, p.bg)).toBeGreaterThanOrEqual(NONTEXT_FLOOR);
    expect(ratio(p.focusRing, p.surface)).toBeGreaterThanOrEqual(NONTEXT_FLOOR);
  });

  it.each(THEMES)('%s: severity vs its own tint row bg (icon/stripe channel)', (id) => {
    const p = PALETTES[id];
    expect(ratio(p.alarmCrit, p.alarmCritBg)).toBeGreaterThanOrEqual(NONTEXT_FLOOR);
    expect(ratio(p.alarmWarn, p.alarmWarnBg)).toBeGreaterThanOrEqual(NONTEXT_FLOOR);
    expect(ratio(p.alarmAdv, p.alarmAdvBg)).toBeGreaterThanOrEqual(NONTEXT_FLOOR);
  });

  it.each(THEMES)('%s: state dots (running/stopped/error) on bg + surface; --state-oos exempt (faded IS the signal)', (id) => {
    const p = PALETTES[id];
    for (const state of [p.stateRunning, p.stateStopped, p.stateError]) {
      expect(ratio(state, p.bg), `${state} on bg`).toBeGreaterThanOrEqual(NONTEXT_FLOOR);
      expect(ratio(state, p.surface), `${state} on surface`).toBeGreaterThanOrEqual(NONTEXT_FLOOR);
    }
  });

  it.each(THEMES)('%s: traces on --trend-bg and --surface-sunk (spec: --trace-co 3.34 on sunk; Phosphor sunk new in v2)', (id) => {
    const p = PALETTES[id];
    for (const trace of [p.tracePv, p.traceSp, p.traceCo]) {
      expect(ratio(trace, p.trendBg), `${trace} on trend-bg`).toBeGreaterThanOrEqual(NONTEXT_FLOOR);
      expect(ratio(trace, p.surfaceSunk), `${trace} on sunk`).toBeGreaterThanOrEqual(NONTEXT_FLOOR);
    }
  });

  it.each(THEMES)('%s: bar fill + marker on bar track', (id) => {
    const p = PALETTES[id];
    expect(ratio(p.barFill, p.barTrack)).toBeGreaterThanOrEqual(NONTEXT_FLOOR);
    expect(ratio(p.barMarker, p.barTrack)).toBeGreaterThanOrEqual(NONTEXT_FLOOR);
  });

  it.each(THEMES)('%s: accent (interactive affordance) on surface', (id) => {
    const p = PALETTES[id];
    expect(ratio(p.accent, p.surface)).toBeGreaterThanOrEqual(NONTEXT_FLOOR);
  });
});

describe('mirror stays in sync with themes.css', () => {
  const TOKEN_OF: Record<keyof ThemePalette, string> = {
    bg: '--bg', surface: '--surface', surfaceSunk: '--surface-sunk',
    ruleStrong: '--rule-strong', text: '--text', textSoft: '--text-soft',
    focusRing: '--focus-ring', selection: '--selection', accent: '--accent',
    accentHover: '--accent-hover', onAccent: '--on-accent',
    alarmCrit: '--alarm-crit', alarmCritBg: '--alarm-crit-bg',
    alarmWarn: '--alarm-warn', alarmWarnBg: '--alarm-warn-bg',
    alarmAdv: '--alarm-adv', alarmAdvBg: '--alarm-adv-bg',
    alarmLog: '--alarm-log', onAlarm: '--on-alarm',
    stateRunning: '--state-running', stateStopped: '--state-stopped',
    stateError: '--state-error', tracePv: '--trace-pv', traceSp: '--trace-sp',
    traceCo: '--trace-co', trendBg: '--trend-bg', barTrack: '--bar-track',
    barFill: '--bar-fill', barMarker: '--bar-marker',
  };

  const css = readFileSync(resolve(process.cwd(), 'src/theme/themes.css'), 'utf8');

  function themeBlock(id: GateThemeId): string {
    const start = css.indexOf(`[data-theme="${id}"]`);
    expect(start, `block for ${id}`).toBeGreaterThanOrEqual(0);
    return css.slice(start, css.indexOf('}', start));
  }

  it.each(THEMES)('%s: every mirrored hex appears on its token in the CSS block', (id) => {
    const block = themeBlock(id);
    for (const [field, token] of Object.entries(TOKEN_OF) as [keyof ThemePalette, string][]) {
      const value = PALETTES[id][field];
      expect(block, `${token}: ${value}`).toContain(`${token}: ${value}`);
    }
  });
});
```

- [ ] **Step 3: Run to see it fail, then pass**

Run: `npm run test -- src/theme/themeContrast.test.ts`
Expected first: FAIL (`Cannot find module './themeContrast'` until Step 1 files exist, then green). After both files land: PASS (all pairs clear their floors — the spec values were pre-verified 2026-07-26; if any assertion fails, the MIRROR is wrong, never the spec value).

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "test(web): Recorder/Phosphor contrast gate — AA text, 3:1 non-text, sync-checked mirror"
```

---

### Task 7: `Button` primitive

**Files:**
- Create: `packages/smart_pid_web/src/components/Button.tsx`
- Test: `packages/smart_pid_web/src/components/Button.test.tsx`

**Interfaces:**
- Consumes: `cn` (`@/lib/utils`), token utilities (Task 2).
- Produces: `Button`, `buttonVariants`, `interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants>` — `variant?: 'primary' | 'secondary' | 'ghost' | 'destructive'` (default `secondary`), `size?: 'md' | 'sm'` (default `md`). Every interactive primitive and feature phase uses it; `MissingState` (Task 22) imports it.

- [ ] **Step 1: Write the failing test**

`src/components/Button.test.tsx` (note: `@testing-library/user-event` is not a devDependency — the repo convention is `fireEvent`):

```tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Button } from './Button';

describe('Button', () => {
  it('renders type=button by default with its accessible name', () => {
    render(<Button>Salvar</Button>);
    const btn = screen.getByRole('button', { name: 'Salvar' });
    expect(btn).toHaveAttribute('type', 'button');
  });

  it('meets the 44px touch floor and the ≥2px focus ring class contract (§12)', () => {
    render(<Button>Entrar</Button>);
    const btn = screen.getByRole('button', { name: 'Entrar' });
    expect(btn.className).toContain('min-h-11');
    expect(btn.className).toContain('min-w-11');
    expect(btn.className).toContain('focus-visible:ring-2');
    expect(btn.className).toContain('focus-visible:ring-focus-ring');
  });

  it('variant classes are token-only', () => {
    const { rerender } = render(<Button variant="primary">a</Button>);
    expect(screen.getByRole('button').className).toContain('bg-accent');
    rerender(<Button variant="destructive">a</Button>);
    expect(screen.getByRole('button').className).toContain('bg-alarm-crit');
    rerender(<Button variant="ghost">a</Button>);
    expect(screen.getByRole('button').className).toContain('text-text-soft');
  });

  it('disabled blocks activation', () => {
    const onClick = vi.fn();
    render(
      <Button disabled onClick={onClick}>
        x
      </Button>,
    );
    fireEvent.click(screen.getByRole('button'));
    expect(onClick).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run to see it fail**

Run: `npm run test -- src/components/Button.test.tsx`
Expected: FAIL — `Cannot find module './Button'`.

- [ ] **Step 3: Implement**

`src/components/Button.tsx`:

```tsx
import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

/**
 * Quiet instrument chrome (§6.1): secondary (outline) is the default; primary
 * (accent) is opt-in; destructive uses --alarm-crit — the ONE sanctioned
 * process-color exception for confirm affordances (§6.3).
 */
export const buttonVariants = cva(
  cn(
    'inline-flex min-h-11 min-w-11 select-none items-center justify-center gap-2 whitespace-nowrap',
    'rounded-control font-ui font-medium outline-none transition-colors',
    'focus-visible:ring-2 focus-visible:ring-focus-ring',
    'disabled:pointer-events-none disabled:opacity-50',
  ),
  {
    variants: {
      variant: {
        primary: 'bg-accent text-on-accent hover:bg-accent-hover active:bg-accent-sunk',
        secondary: 'border border-rule-strong bg-surface text-text hover:bg-surface-sunk',
        ghost: 'text-text-soft hover:bg-surface-sunk hover:text-text',
        destructive: 'bg-alarm-crit text-on-alarm hover:opacity-90',
      },
      size: {
        md: 'px-4 py-2 text-sm',
        sm: 'px-3 py-1 text-xs',
      },
    },
    defaultVariants: { variant: 'secondary', size: 'md' },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, type = 'button', ...props }, ref) => (
    <button ref={ref} type={type} className={cn(buttonVariants({ variant, size }), className)} {...props} />
  ),
);
Button.displayName = 'Button';
```

- [ ] **Step 4: Run to see it pass**

Run: `npm run test -- src/components/Button.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/components/Button.tsx src/components/Button.test.tsx
git commit -m "feat(web): Button primitive (token-only, 44px floor, quiet-default variants)"
```

---

### Task 8: `Badge` primitive

**Files:**
- Create: `packages/smart_pid_web/src/components/Badge.tsx`
- Test: `packages/smart_pid_web/src/components/Badge.test.tsx`

**Interfaces:**
- Consumes: `cn`, token utilities.
- Produces: `Badge`, `badgeVariants`, `interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants>` — `tone?: 'neutral' | 'accent' | 'crit' | 'warn' | 'adv' | 'log'` (default `neutral`). Severity tones render colored TEXT+BORDER on the ambient surface (≥4.5:1, gated in Task 6); the `--alarm-*-bg` tints are for alarm ROW backgrounds (phase 6), not badges. Severity is never color-only: the badge always carries children (text); phase 6 adds the glyph channel.

- [ ] **Step 1: Write the failing test**

`src/components/Badge.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Badge } from './Badge';

describe('Badge', () => {
  it('renders its text content (severity never color-only)', () => {
    render(<Badge tone="crit">2 CRITICAL</Badge>);
    expect(screen.getByText('2 CRITICAL')).toBeInTheDocument();
  });

  it('severity tones color text+border with the severity token, not a tint bg', () => {
    render(<Badge tone="warn">1 WARNING</Badge>);
    const el = screen.getByText('1 WARNING');
    expect(el.className).toContain('text-alarm-warn');
    expect(el.className).toContain('border-alarm-warn');
    expect(el.className).not.toContain('bg-alarm-warn');
  });

  it('neutral (quiet) is the default — counts in --text-soft (§6.9 quiet alarm bar)', () => {
    render(<Badge>0 alarmes</Badge>);
    expect(screen.getByText('0 alarmes').className).toContain('text-text-soft');
  });
});
```

- [ ] **Step 2: Run to see it fail**

Run: `npm run test -- src/components/Badge.test.tsx`
Expected: FAIL — `Cannot find module './Badge'`.

- [ ] **Step 3: Implement**

`src/components/Badge.tsx`:

```tsx
import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

export const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-pill border px-2 py-0.5 font-ui text-xs font-medium',
  {
    variants: {
      tone: {
        neutral: 'border-rule text-text-soft',
        accent: 'border-accent bg-accent-soft text-accent',
        crit: 'border-alarm-crit text-alarm-crit',
        warn: 'border-alarm-warn text-alarm-warn',
        adv: 'border-alarm-adv text-alarm-adv',
        log: 'border-rule text-alarm-log',
      },
    },
    defaultVariants: { tone: 'neutral' },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}
```

- [ ] **Step 4: Run to see it pass**

Run: `npm run test -- src/components/Badge.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/components/Badge.tsx src/components/Badge.test.tsx
git commit -m "feat(web): Badge primitive (severity tones as text+border, quiet default)"
```

---

### Task 9: `Readout` primitive (creates `lib/format`)

**Files:**
- Create: `packages/smart_pid_web/src/lib/format.ts`
- Create: `packages/smart_pid_web/src/components/Readout.tsx`
- Test: `packages/smart_pid_web/src/lib/format.test.ts`
- Test: `packages/smart_pid_web/src/components/Readout.test.tsx`

**Interfaces:**
- Consumes: `cn`; `.numeric` class (Task 2).
- Produces: `formatNumber(value: number | null | undefined, decimals: number): string` from `@/lib/format` (em dash `'—'` for null/undefined/NaN; NO unit handling — phase 3's `formatWithUnit` builds on it, agreed with PlanPhase03). `Readout`, `interface ReadoutProps { label: string; value: number | null | undefined; unit?: string; decimals?: number; size?: 'sm' | 'md' | 'lg'; className?: string }` — defaults `decimals=1`, `size='md'`. Every numeral renders through `.numeric` (Geist Mono, §6.2).

- [ ] **Step 1: Write the failing tests**

`src/lib/format.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { formatNumber } from './format';

describe('formatNumber (tabular fixed-decimal, §6.2)', () => {
  it('formats with fixed decimals', () => {
    expect(formatNumber(1.234, 2)).toBe('1.23');
    expect(formatNumber(150.25, 1)).toBe('150.3');
    expect(formatNumber(5, 0)).toBe('5');
    expect(formatNumber(-42.1, 1)).toBe('-42.1');
  });

  it('renders the em dash for null/undefined/NaN', () => {
    expect(formatNumber(null, 1)).toBe('—');
    expect(formatNumber(undefined, 1)).toBe('—');
    expect(formatNumber(Number.NaN, 1)).toBe('—');
  });
});
```

`src/components/Readout.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Readout } from './Readout';

describe('Readout', () => {
  it('shows label, formatted value and unit', () => {
    render(<Readout label="PV" value={150.25} unit="°C" decimals={1} />);
    expect(screen.getByText('PV')).toBeInTheDocument();
    expect(screen.getByText('150.3')).toBeInTheDocument();
    expect(screen.getByText('°C')).toBeInTheDocument();
  });

  it('every numeral is Geist Mono — value carries the .numeric class (§6.2)', () => {
    render(<Readout label="SP" value={148} />);
    expect(screen.getByText('148.0').className).toContain('numeric');
  });

  it('renders the em dash when the value is missing', () => {
    render(<Readout label="CO" value={null} />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to see them fail**

Run: `npm run test -- src/lib/format.test.ts src/components/Readout.test.tsx`
Expected: FAIL — `Cannot find module './format'` / `'./Readout'`.

- [ ] **Step 3: Implement**

`src/lib/format.ts`:

```ts
/**
 * Fixed-decimal tabular formatting for process values (§6.2). The SINGLE
 * format module — phase 3 extends it (units, timestamps) without changing
 * this signature. Alignment comes from .numeric (tabular-nums, Geist Mono).
 */
export function formatNumber(value: number | null | undefined, decimals: number): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '—';
  }
  return value.toFixed(decimals);
}
```

`src/components/Readout.tsx`:

```tsx
import { formatNumber } from '@/lib/format';
import { cn } from '@/lib/utils';

export interface ReadoutProps {
  label: string;
  value: number | null | undefined;
  unit?: string;
  decimals?: number;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const VALUE_SIZE: Record<NonNullable<ReadoutProps['size']>, string> = {
  sm: 'text-sm',
  md: 'text-xl',
  lg: 'text-2xl',
};

/** Labeled numeric display. The label is Archivo (UI face); the value is ALWAYS
 *  Geist Mono via .numeric — a KPI figure is a metric (§6.2). */
export function Readout({ label, value, unit, decimals = 1, size = 'md', className }: ReadoutProps) {
  return (
    <div className={cn('flex flex-col gap-0.5', className)}>
      <span className="text-2xs font-medium uppercase tracking-wider text-text-soft">{label}</span>
      <span className="flex items-baseline gap-1">
        <span className={cn('numeric font-medium text-text', VALUE_SIZE[size])}>
          {formatNumber(value, decimals)}
        </span>
        {unit ? <span className="text-xs text-text-soft">{unit}</span> : null}
      </span>
    </div>
  );
}
```

- [ ] **Step 4: Run to see them pass**

Run: `npm run test -- src/lib/format.test.ts src/components/Readout.test.tsx`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/lib/format.ts src/lib/format.test.ts src/components/Readout.tsx src/components/Readout.test.tsx
git commit -m "feat(web): Readout primitive + single format module (Geist Mono numerals)"
```

---

### Task 10: `AnalogBar` primitive (creates `lib/scale`)

**Files:**
- Create: `packages/smart_pid_web/src/lib/scale.ts`
- Create: `packages/smart_pid_web/src/components/AnalogBar.tsx`
- Test: `packages/smart_pid_web/src/lib/scale.test.ts`
- Test: `packages/smart_pid_web/src/components/AnalogBar.test.tsx`

**Interfaces:**
- Consumes: `formatNumber` (Task 9), `cn`.
- Produces: from `@/lib/scale`: `interface Scale { euMin: number; euMax: number; unit: string }`, `valueToFraction(value: number, scale: Scale): number` (clamped 0..1; 0 when span ≤ 0), `ticks(scale: Scale, count?: number): number[]` (evenly spaced values euMin→euMax inclusive, default count 5, min 2 — pinned with PlanPhase03). `AnalogBar`, `type AnalogBarAlarm = 'normal' | 'warn' | 'crit'`, `interface AnalogBarProps { label: string; value: number | null | undefined; scale: Scale; spValue?: number; alarm?: AnalogBarAlarm; decimals?: number; size?: 'card' | 'faceplate'; className?: string }`. Fill/SP-marker use the two sanctioned dynamic inline styles (width %, left %); fill color is a runtime-selected token `var()` (never a literal).

- [ ] **Step 1: Write the failing tests**

`src/lib/scale.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { ticks, valueToFraction, type Scale } from './scale';

const s: Scale = { euMin: 0, euMax: 200, unit: '°C' };

describe('valueToFraction', () => {
  it('maps and clamps into 0..1', () => {
    expect(valueToFraction(100, s)).toBe(0.5);
    expect(valueToFraction(-50, s)).toBe(0);
    expect(valueToFraction(400, s)).toBe(1);
  });

  it('degenerate span yields 0', () => {
    expect(valueToFraction(10, { euMin: 5, euMax: 5, unit: '' })).toBe(0);
  });
});

describe('ticks', () => {
  it('generates evenly spaced inclusive ticks (default 5)', () => {
    expect(ticks({ euMin: 0, euMax: 100, unit: '%' })).toEqual([0, 25, 50, 75, 100]);
  });

  it('respects count and the minimum of 2', () => {
    expect(ticks(s, 3)).toEqual([0, 100, 200]);
    expect(ticks(s, 1)).toEqual([0, 200]);
  });

  it('degenerate span collapses to [euMin, euMin]', () => {
    expect(ticks({ euMin: 7, euMax: 7, unit: '' })).toEqual([7, 7]);
  });
});
```

`src/components/AnalogBar.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { AnalogBar } from './AnalogBar';

const scale = { euMin: 0, euMax: 200, unit: '°C' };

describe('AnalogBar', () => {
  it('exposes a meter role with EU range and value text', () => {
    render(<AnalogBar label="PV" value={150.2} scale={scale} />);
    const meter = screen.getByRole('meter', { name: 'PV' });
    expect(meter).toHaveAttribute('aria-valuemin', '0');
    expect(meter).toHaveAttribute('aria-valuemax', '200');
    expect(meter).toHaveAttribute('aria-valuenow', '150.2');
    expect(meter).toHaveAttribute('aria-valuetext', '150.2 °C');
  });

  it('fill width tracks the clamped fraction (sanctioned dynamic inline style)', () => {
    render(<AnalogBar label="PV" value={100} scale={scale} />);
    expect(screen.getByTestId('analog-bar-fill').style.width).toBe('50.00%');
  });

  it('alarm level swaps the fill token var, never a raw color', () => {
    render(<AnalogBar label="PV" value={100} scale={scale} alarm="crit" />);
    expect(screen.getByTestId('analog-bar-fill').style.background).toBe('var(--alarm-crit)');
  });

  it('renders the SP marker when spValue is given', () => {
    render(<AnalogBar label="PV" value={100} scale={scale} spValue={150} />);
    expect(screen.getByTestId('analog-bar-sp').style.left).toBe('75.00%');
  });

  it('missing value: 0% fill, em dash, aria-valuetext "sem dados"', () => {
    render(<AnalogBar label="CO" value={null} scale={scale} />);
    expect(screen.getByTestId('analog-bar-fill').style.width).toBe('0.00%');
    expect(screen.getByText('—')).toBeInTheDocument();
    expect(screen.getByRole('meter', { name: 'CO' })).toHaveAttribute('aria-valuetext', 'sem dados');
  });
});
```

- [ ] **Step 2: Run to see them fail**

Run: `npm run test -- src/lib/scale.test.ts src/components/AnalogBar.test.tsx`
Expected: FAIL — `Cannot find module './scale'` / `'./AnalogBar'`.

- [ ] **Step 3: Implement**

`src/lib/scale.ts`:

```ts
/**
 * Value→fraction, clamping and tick generation for AnalogBar (§7 pure module).
 * Phase 3 may extend (valueToPercent, clampToScale) but NEVER changes these
 * signatures — pinned with the phase-3 plan.
 */
export interface Scale {
  euMin: number;
  euMax: number;
  unit: string;
}

/** Clamped 0..1 fraction of value within the scale span; 0 when span <= 0. */
export function valueToFraction(value: number, scale: Scale): number {
  const span = scale.euMax - scale.euMin;
  if (span <= 0) return 0;
  const f = (value - scale.euMin) / span;
  return f < 0 ? 0 : f > 1 ? 1 : f;
}

/** Evenly spaced tick VALUES from euMin to euMax inclusive (count >= 2, default 5). */
export function ticks(scale: Scale, count = 5): number[] {
  const n = Math.max(2, Math.floor(count));
  const span = scale.euMax - scale.euMin;
  if (span <= 0) return [scale.euMin, scale.euMin];
  return Array.from({ length: n }, (_, i) => scale.euMin + (span * i) / (n - 1));
}
```

`src/components/AnalogBar.tsx`:

```tsx
import { formatNumber } from '@/lib/format';
import { valueToFraction, type Scale } from '@/lib/scale';
import { cn } from '@/lib/utils';

export type AnalogBarAlarm = 'normal' | 'warn' | 'crit';

export interface AnalogBarProps {
  label: string;
  value: number | null | undefined;
  scale: Scale;
  spValue?: number;
  alarm?: AnalogBarAlarm;
  decimals?: number;
  size?: 'card' | 'faceplate';
  className?: string;
}

/**
 * Fill color per alarm level — token var() references selected at runtime
 * (one of the two sanctioned dynamic inline styles; the other is the width %).
 * Normal fill is gray (--bar-fill): green never means "ok" (§6.4).
 */
const ALARM_FILL: Record<AnalogBarAlarm, string> = {
  normal: 'var(--bar-fill)',
  warn: 'var(--alarm-warn)',
  crit: 'var(--alarm-crit)',
};

const TRACK_HEIGHT: Record<NonNullable<AnalogBarProps['size']>, string> = {
  card: 'h-2',
  faceplate: 'h-3.5',
};

export function AnalogBar({
  label,
  value,
  scale,
  spValue,
  alarm = 'normal',
  decimals = 1,
  size = 'card',
  className,
}: AnalogBarProps) {
  const finite = typeof value === 'number' && Number.isFinite(value);
  const pct = (finite ? valueToFraction(value, scale) * 100 : 0).toFixed(2);
  const spPct = spValue !== undefined ? (valueToFraction(spValue, scale) * 100).toFixed(2) : null;

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <span className="w-8 shrink-0 text-2xs font-medium uppercase tracking-wider text-text-soft">
        {label}
      </span>
      <div
        role="meter"
        aria-label={label}
        aria-valuemin={scale.euMin}
        aria-valuemax={scale.euMax}
        aria-valuenow={finite ? value : undefined}
        aria-valuetext={finite ? `${formatNumber(value, decimals)} ${scale.unit}` : 'sem dados'}
        className={cn('relative min-w-16 grow overflow-hidden bg-bar-track', TRACK_HEIGHT[size])}
      >
        <div
          data-testid="analog-bar-fill"
          className="absolute inset-y-0 left-0"
          style={{ width: `${pct}%`, background: ALARM_FILL[alarm] }}
        />
        {spPct !== null ? (
          <div
            data-testid="analog-bar-sp"
            aria-hidden="true"
            className="absolute inset-y-0 w-0.5 -translate-x-1/2 bg-bar-marker"
            style={{ left: `${spPct}%` }}
          />
        ) : null}
      </div>
      <span className="numeric w-16 shrink-0 text-right text-sm text-text">
        {formatNumber(value, decimals)}
      </span>
    </div>
  );
}
```

- [ ] **Step 4: Run to see them pass**

Run: `npm run test -- src/lib/scale.test.ts src/components/AnalogBar.test.tsx`
Expected: PASS (11 tests).

- [ ] **Step 5: Commit**

```bash
git add src/lib/scale.ts src/lib/scale.test.ts src/components/AnalogBar.tsx src/components/AnalogBar.test.tsx
git commit -m "feat(web): AnalogBar primitive + scale module (meter semantics, token fills)"
```

---

### Task 11: `Field` primitive (label/description/error wrapper + `Input`)

**Files:**
- Create: `packages/smart_pid_web/src/components/Field.tsx`
- Test: `packages/smart_pid_web/src/components/Field.test.tsx`

**Interfaces:**
- Consumes: `cn`, token utilities.
- Produces: `Field`, `interface FieldProps { label: string; htmlFor: string; description?: string; error?: string; required?: boolean; children: React.ReactNode; className?: string }`; `Input`, `interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> { invalid?: boolean }` (forwardRef). ID convention (relied on by every form phase): description id = `` `${htmlFor}-desc` ``, error id = `` `${htmlFor}-err` `` — callers wire `aria-describedby` to those ids. Error renders with `role="alert"` in `--alarm-crit`. Inputs sit on `--surface-sunk` (§6.5 "chart wells, inputs").

- [ ] **Step 1: Write the failing test**

`src/components/Field.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Field, Input } from './Field';

describe('Field + Input', () => {
  it('associates the label with the control', () => {
    render(
      <Field label="Usuário" htmlFor="user">
        <Input id="user" />
      </Field>,
    );
    expect(screen.getByLabelText('Usuário')).toBeInTheDocument();
  });

  it('renders description and error with the id convention', () => {
    render(
      <Field label="Senha" htmlFor="pw" description="Mínimo 8 caracteres" error="Obrigatório">
        <Input id="pw" type="password" aria-describedby="pw-desc pw-err" invalid />
      </Field>,
    );
    expect(screen.getByText('Mínimo 8 caracteres')).toHaveAttribute('id', 'pw-desc');
    const err = screen.getByRole('alert');
    expect(err).toHaveAttribute('id', 'pw-err');
    expect(err).toHaveTextContent('Obrigatório');
    expect(screen.getByLabelText('Senha')).toHaveAttribute('aria-invalid', 'true');
  });

  it('Input meets the touch floor and sits on surface-sunk', () => {
    render(<Input aria-label="Valor" />);
    const input = screen.getByRole('textbox', { name: 'Valor' });
    expect(input.className).toContain('min-h-11');
    expect(input.className).toContain('bg-surface-sunk');
  });

  it('required marks the label visually without polluting the accessible name', () => {
    render(
      <Field label="Endpoint" htmlFor="ep" required>
        <Input id="ep" />
      </Field>,
    );
    expect(screen.getByLabelText('Endpoint')).toBeInTheDocument(); // name stays exact
  });
});
```

- [ ] **Step 2: Run to see it fail**

Run: `npm run test -- src/components/Field.test.tsx`
Expected: FAIL — `Cannot find module './Field'`.

- [ ] **Step 3: Implement**

`src/components/Field.tsx`:

```tsx
import * as React from 'react';
import { cn } from '@/lib/utils';

export interface FieldProps {
  label: string;
  htmlFor: string;
  description?: string;
  error?: string;
  required?: boolean;
  children: React.ReactNode;
  className?: string;
}

/**
 * Labeled form-control wrapper. ID convention: description `${htmlFor}-desc`,
 * error `${htmlFor}-err` — callers wire aria-describedby to those ids.
 * The `*` is aria-hidden so accessible names stay verbatim (E2E binds to them).
 */
export function Field({ label, htmlFor, description, error, required = false, children, className }: FieldProps) {
  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <label htmlFor={htmlFor} className="text-sm font-medium text-text">
        {label}
        {required ? (
          <span aria-hidden="true" className="text-alarm-crit">
            {' '}
            *
          </span>
        ) : null}
      </label>
      {children}
      {description ? (
        <p id={`${htmlFor}-desc`} className="text-xs text-text-soft">
          {description}
        </p>
      ) : null}
      {error ? (
        <p id={`${htmlFor}-err`} role="alert" className="text-xs font-medium text-alarm-crit">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, invalid = false, ...props }, ref) => (
    <input
      ref={ref}
      aria-invalid={invalid || undefined}
      className={cn(
        'min-h-11 w-full rounded-control border border-rule-strong bg-surface-sunk px-3 py-2 text-sm text-text',
        'placeholder:text-text-disabled outline-none focus-visible:ring-2 focus-visible:ring-focus-ring',
        'disabled:cursor-not-allowed disabled:text-text-disabled',
        invalid && 'border-alarm-crit',
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = 'Input';
```

- [ ] **Step 4: Run to see it pass**

Run: `npm run test -- src/components/Field.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/components/Field.tsx src/components/Field.test.tsx
git commit -m "feat(web): Field/Input primitive (a11y id convention, sunk inputs)"
```

---

### Task 12: `Dialog` primitive

**Files:**
- Create: `packages/smart_pid_web/src/components/Dialog.tsx`
- Test: `packages/smart_pid_web/src/components/Dialog.test.tsx`

**Interfaces:**
- Consumes: `radix-ui` Dialog, `cn`, `lucide-react` `X`.
- Produces: shadcn-style composition — `Dialog`, `DialogTrigger`, `DialogPortal`, `DialogOverlay`, `DialogClose`, `DialogContent` (props: Radix `Dialog.Content` props + `children`), `DialogHeader`, `DialogFooter`, `DialogTitle`, `DialogDescription`. Contracts: overlay is `bg-scrim` (the token IS the translucency — no `/60` opacity utility); the built-in close button has `aria-label="Fechar"` (verbatim, E2E-bound) and a 44px target; titles use `.type-display`. Every destructive confirm dialog in later phases builds on this.

- [ ] **Step 1: Write the failing test**

`src/components/Dialog.test.tsx`:

```tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from './Dialog';

function Harness() {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <button type="button">Abrir</button>
      </DialogTrigger>
      <DialogContent>
        <DialogTitle>Excluir projeto</DialogTitle>
        <DialogDescription>Esta ação não pode ser desfeita.</DialogDescription>
      </DialogContent>
    </Dialog>
  );
}

describe('Dialog', () => {
  it('opens from the trigger with role=dialog and its accessible name', () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole('button', { name: 'Abrir' }));
    expect(screen.getByRole('dialog', { name: 'Excluir projeto' })).toBeInTheDocument();
  });

  it('ships the verbatim pt-BR close affordance "Fechar" at the 44px floor', () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole('button', { name: 'Abrir' }));
    const close = screen.getByRole('button', { name: 'Fechar' });
    expect(close.className).toContain('min-h-11');
    expect(close.className).toContain('min-w-11');
  });

  it('closes via Fechar', () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole('button', { name: 'Abrir' }));
    fireEvent.click(screen.getByRole('button', { name: 'Fechar' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('title carries the display face; overlay carries the scrim token', () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole('button', { name: 'Abrir' }));
    expect(screen.getByText('Excluir projeto').className).toContain('type-display');
    // Overlay lives in a Radix portal — query the document, not DOM siblings.
    const overlay = document.querySelector('[data-slot="dialog-overlay"]');
    expect(overlay?.className).toContain('bg-scrim');
  });
});
```

- [ ] **Step 2: Run to see it fail**

Run: `npm run test -- src/components/Dialog.test.tsx`
Expected: FAIL — `Cannot find module './Dialog'`.

- [ ] **Step 3: Implement**

`src/components/Dialog.tsx`:

```tsx
import * as React from 'react';
import { Dialog as DialogPrimitive } from 'radix-ui';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';

const Dialog = DialogPrimitive.Root;
const DialogTrigger = DialogPrimitive.Trigger;
const DialogPortal = DialogPrimitive.Portal;
const DialogClose = DialogPrimitive.Close;

const DialogOverlay = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    data-slot="dialog-overlay"
    className={cn('fixed inset-0 z-50 bg-scrim', className)}
    {...props}
  />
));
DialogOverlay.displayName = DialogPrimitive.Overlay.displayName;

const DialogContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <DialogPortal>
    <DialogOverlay />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        'fixed left-1/2 top-1/2 z-50 flex w-full max-w-lg -translate-x-1/2 -translate-y-1/2 flex-col gap-3',
        'rounded-card border border-rule-strong bg-surface p-6 text-text outline-none',
        className,
      )}
      {...props}
    >
      {children}
      <DialogPrimitive.Close
        aria-label="Fechar"
        className={cn(
          'absolute right-1 top-1 inline-flex min-h-11 min-w-11 items-center justify-center',
          'text-text-soft outline-none transition-colors hover:text-text',
          'focus-visible:ring-2 focus-visible:ring-focus-ring',
        )}
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPortal>
));
DialogContent.displayName = DialogPrimitive.Content.displayName;

function DialogHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('flex flex-col gap-1', className)} {...props} />;
}
DialogHeader.displayName = 'DialogHeader';

function DialogFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('flex justify-end gap-2 pt-2', className)} {...props} />;
}
DialogFooter.displayName = 'DialogFooter';

const DialogTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn('type-display text-lg text-text', className)}
    {...props}
  />
));
DialogTitle.displayName = DialogPrimitive.Title.displayName;

const DialogDescription = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Description>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description
    ref={ref}
    className={cn('text-sm text-text-soft', className)}
    {...props}
  />
));
DialogDescription.displayName = DialogPrimitive.Description.displayName;

export {
  Dialog,
  DialogPortal,
  DialogOverlay,
  DialogTrigger,
  DialogClose,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
};
```

- [ ] **Step 4: Run to see it pass**

Run: `npm run test -- src/components/Dialog.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/components/Dialog.tsx src/components/Dialog.test.tsx
git commit -m "feat(web): Dialog primitive (scrim token, Fechar verbatim, display-face title)"
```

---

### Task 13: `Tooltip` primitive

**Files:**
- Create: `packages/smart_pid_web/src/components/Tooltip.tsx`
- Test: `packages/smart_pid_web/src/components/Tooltip.test.tsx`

**Interfaces:**
- Consumes: `radix-ui` Tooltip, `cn`.
- Produces: `TooltipProvider` (app-level, phase 4 mounts ONE), `Tooltip`, `TooltipTrigger`, `TooltipContent` (Radix props + `sideOffset?: number` default 4). Quiet chrome: surface + hairline border, no arrow.

- [ ] **Step 1: Write the failing test**

`src/components/Tooltip.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './Tooltip';

describe('Tooltip', () => {
  it('exposes role=tooltip with token-only styling', () => {
    render(
      <TooltipProvider delayDuration={0}>
        <Tooltip defaultOpen>
          <TooltipTrigger asChild>
            <button type="button">IAE</button>
          </TooltipTrigger>
          <TooltipContent>Integral do erro absoluto</TooltipContent>
        </Tooltip>
      </TooltipProvider>,
    );
    const tip = screen.getByRole('tooltip');
    expect(tip).toHaveTextContent('Integral do erro absoluto');
    expect(tip.className).toContain('bg-surface');
    expect(tip.className).toContain('border-rule-strong');
  });
});
```

- [ ] **Step 2: Run to see it fail**

Run: `npm run test -- src/components/Tooltip.test.tsx`
Expected: FAIL — `Cannot find module './Tooltip'`.

- [ ] **Step 3: Implement**

`src/components/Tooltip.tsx`:

```tsx
import * as React from 'react';
import { Tooltip as TooltipPrimitive } from 'radix-ui';
import { cn } from '@/lib/utils';

const TooltipProvider = TooltipPrimitive.Provider;
const Tooltip = TooltipPrimitive.Root;
const TooltipTrigger = TooltipPrimitive.Trigger;

const TooltipContent = React.forwardRef<
  React.ElementRef<typeof TooltipPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 4, ...props }, ref) => (
  <TooltipPrimitive.Content
    ref={ref}
    sideOffset={sideOffset}
    className={cn(
      'z-50 rounded-control border border-rule-strong bg-surface px-2 py-1 text-xs text-text',
      className,
    )}
    {...props}
  />
));
TooltipContent.displayName = TooltipPrimitive.Content.displayName;

export { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger };
```

- [ ] **Step 4: Run to see it pass**

Run: `npm run test -- src/components/Tooltip.test.tsx`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add src/components/Tooltip.tsx src/components/Tooltip.test.tsx
git commit -m "feat(web): Tooltip primitive (quiet surface, hairline border)"
```

---

### Task 14: `Switch` primitive

**Files:**
- Create: `packages/smart_pid_web/src/components/Switch.tsx`
- Test: `packages/smart_pid_web/src/components/Switch.test.tsx`

**Interfaces:**
- Consumes: `radix-ui` Switch, `cn`.
- Produces: `Switch` (forwardRef, props = Radix `Switch.Root` props). 24px-tall visual track; an `after:` pseudo-element extends the hit area to the 44px floor (compact-control rule from Global Constraints — the phase-4 e2e enforcement list matches today's, which never measured switches; Button-class controls stay literal 44px).

- [ ] **Step 1: Write the failing test**

`src/components/Switch.test.tsx`:

```tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Switch } from './Switch';

describe('Switch', () => {
  it('toggles aria-checked on click', () => {
    render(<Switch aria-label="Otimização contínua" />);
    const sw = screen.getByRole('switch', { name: 'Otimização contínua' });
    expect(sw).toHaveAttribute('aria-checked', 'false');
    fireEvent.click(sw);
    expect(sw).toHaveAttribute('aria-checked', 'true');
  });

  it('carries the pseudo hit-area extension and accent checked state', () => {
    render(<Switch aria-label="x" />);
    const sw = screen.getByRole('switch');
    expect(sw.className).toContain('after:absolute');
    expect(sw.className).toContain('data-[state=checked]:bg-accent');
  });

  it('disabled blocks toggling', () => {
    render(<Switch aria-label="x" disabled />);
    const sw = screen.getByRole('switch');
    fireEvent.click(sw);
    expect(sw).toHaveAttribute('aria-checked', 'false');
  });
});
```

- [ ] **Step 2: Run to see it fail**

Run: `npm run test -- src/components/Switch.test.tsx`
Expected: FAIL — `Cannot find module './Switch'`.

- [ ] **Step 3: Implement**

`src/components/Switch.tsx`:

```tsx
import * as React from 'react';
import { Switch as SwitchPrimitive } from 'radix-ui';
import { cn } from '@/lib/utils';

/**
 * 24px visual track; the ::after inset extends the pointer target to ≥44px
 * (compact-control rule). Checked state uses the accent — interactive chrome,
 * never a process/alarm color (§6.3/§6.6).
 */
export const Switch = React.forwardRef<
  React.ElementRef<typeof SwitchPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SwitchPrimitive.Root>
>(({ className, ...props }, ref) => (
  <SwitchPrimitive.Root
    ref={ref}
    className={cn(
      'peer relative inline-flex h-6 w-10 shrink-0 cursor-pointer items-center rounded-pill',
      'border border-rule-strong bg-bar-track outline-none transition-colors',
      "after:absolute after:-inset-x-1 after:-inset-y-2.5 after:content-['']",
      'focus-visible:ring-2 focus-visible:ring-focus-ring',
      'data-[state=checked]:border-accent data-[state=checked]:bg-accent',
      'disabled:cursor-not-allowed disabled:opacity-50',
      className,
    )}
    {...props}
  >
    <SwitchPrimitive.Thumb
      className={cn(
        'pointer-events-none block h-4 w-4 translate-x-1 rounded-pill bg-surface transition-transform',
        'data-[state=checked]:translate-x-[1.125rem]',
      )}
    />
  </SwitchPrimitive.Root>
));
Switch.displayName = SwitchPrimitive.Root.displayName;
```

- [ ] **Step 4: Run to see it pass**

Run: `npm run test -- src/components/Switch.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/components/Switch.tsx src/components/Switch.test.tsx
git commit -m "feat(web): Switch primitive (accent checked state, 44px hit extension)"
```

---

### Task 15: `Slider` primitive

**Files:**
- Create: `packages/smart_pid_web/src/components/Slider.tsx`
- Test: `packages/smart_pid_web/src/components/Slider.test.tsx`

**Interfaces:**
- Consumes: `radix-ui` Slider, `cn`.
- Produces: `Slider` (forwardRef), `interface SliderProps extends React.ComponentPropsWithoutRef<typeof SliderPrimitive.Root> { thumbLabel?: string }` — `thumbLabel` becomes each thumb's `aria-label` (phase 5's CO slider passes `thumbLabel="CO manual"`). Root is `min-h-11`; the thumb is 16px at ≥1024 and grows to `h-11 w-11` below 1024 (`max-lg:`), matching the responsive rule the retained `e2e/target-size.spec.ts` enforces (`assertMinTarget` on the CO thumb <1024). Range fill is accent (setpoint control = interactive chrome, not a process bar).

- [ ] **Step 1: Write the failing test**

`src/components/Slider.test.tsx`:

```tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Slider } from './Slider';

describe('Slider', () => {
  it('exposes a labeled slider thumb with value semantics', () => {
    render(<Slider defaultValue={[40]} min={0} max={100} step={5} thumbLabel="CO manual" />);
    const thumb = screen.getByRole('slider', { name: 'CO manual' });
    expect(thumb).toHaveAttribute('aria-valuenow', '40');
    expect(thumb).toHaveAttribute('aria-valuemin', '0');
    expect(thumb).toHaveAttribute('aria-valuemax', '100');
  });

  it('keyboard steps the value (Radix keyboard support)', () => {
    render(<Slider defaultValue={[40]} min={0} max={100} step={5} thumbLabel="CO manual" />);
    const thumb = screen.getByRole('slider', { name: 'CO manual' });
    thumb.focus();
    fireEvent.keyDown(thumb, { key: 'ArrowRight' });
    expect(thumb).toHaveAttribute('aria-valuenow', '45');
  });

  it('thumb carries the responsive 44px floor below lg (retained e2e contract)', () => {
    render(<Slider defaultValue={[40]} thumbLabel="x" />);
    const thumb = screen.getByRole('slider');
    expect(thumb.className).toContain('max-lg:h-11');
    expect(thumb.className).toContain('max-lg:w-11');
  });
});
```

- [ ] **Step 2: Run to see it fail**

Run: `npm run test -- src/components/Slider.test.tsx`
Expected: FAIL — `Cannot find module './Slider'`.

- [ ] **Step 3: Implement**

`src/components/Slider.tsx`:

```tsx
import * as React from 'react';
import { Slider as SliderPrimitive } from 'radix-ui';
import { cn } from '@/lib/utils';

export interface SliderProps extends React.ComponentPropsWithoutRef<typeof SliderPrimitive.Root> {
  /** aria-label applied to every thumb (Radix does not inherit it from the root). */
  thumbLabel?: string;
}

/**
 * The thumb is a compact 16px control at ≥1024; below the 1024 breakpoint it
 * grows to the literal 44px touch floor — the pattern the retained
 * e2e/target-size.spec.ts asserts on the CO slider (assertMinTarget <1024).
 */
export const Slider = React.forwardRef<
  React.ElementRef<typeof SliderPrimitive.Root>,
  SliderProps
>(({ className, disabled, thumbLabel, ...props }, ref) => {
  const value = props.value ?? props.defaultValue ?? [0];
  const thumbCount = Array.isArray(value) ? value.length : 1;

  return (
    <SliderPrimitive.Root
      ref={ref}
      disabled={disabled}
      className={cn(
        'relative flex min-h-11 w-full touch-none select-none items-center data-[disabled]:opacity-50',
        className,
      )}
      {...props}
    >
      <SliderPrimitive.Track className="relative h-1.5 w-full grow overflow-hidden rounded-pill bg-bar-track">
        <SliderPrimitive.Range className="absolute h-full bg-accent" />
      </SliderPrimitive.Track>
      {Array.from({ length: thumbCount }, (_, index) => (
        <SliderPrimitive.Thumb
          key={index}
          aria-label={thumbLabel}
          aria-disabled={disabled || undefined}
          className={cn(
            'block h-4 w-4 rounded-pill border border-rule-strong bg-surface outline-none transition-colors',
            'focus-visible:ring-2 focus-visible:ring-focus-ring disabled:pointer-events-none',
            'max-lg:h-11 max-lg:w-11',
          )}
        />
      ))}
    </SliderPrimitive.Root>
  );
});
Slider.displayName = SliderPrimitive.Root.displayName;
```

- [ ] **Step 4: Run to see it pass**

Run: `npm run test -- src/components/Slider.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/components/Slider.tsx src/components/Slider.test.tsx
git commit -m "feat(web): Slider primitive (thumbLabel a11y, responsive 44px thumb)"
```

---

### Task 16: `Select` primitive

**Files:**
- Create: `packages/smart_pid_web/src/components/Select.tsx`
- Test: `packages/smart_pid_web/src/components/Select.test.tsx`

**Interfaces:**
- Consumes: `radix-ui` Select, `cn`, `lucide-react` `Check`/`ChevronDown`.
- Produces: `Select` (Root), `SelectValue`, `SelectTrigger`, `SelectContent`, `SelectItem`, `SelectGroup`, `SelectLabel` — Radix prop pass-through. Trigger sits on `--surface-sunk`, `min-h-11`; highlighted items use `bg-selection` (the token exists for exactly this). jsdom cannot drive Radix pointer opening — tests use `defaultOpen` (the `scrollIntoView`/pointer-capture stubs from Task 1's setup make it render).

- [ ] **Step 1: Write the failing test**

`src/components/Select.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './Select';

describe('Select', () => {
  it('renders trigger with accessible name and sunk styling', () => {
    render(
      <Select defaultValue="pid">
        <SelectTrigger aria-label="Tipo de controlador">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="pid">PID</SelectItem>
        </SelectContent>
      </Select>,
    );
    const trigger = screen.getByRole('combobox', { name: 'Tipo de controlador' });
    expect(trigger.className).toContain('bg-surface-sunk');
    expect(trigger.className).toContain('min-h-11');
  });

  it('defaultOpen renders the listbox with options and selection highlight class', () => {
    render(
      <Select defaultOpen defaultValue="pid">
        <SelectTrigger aria-label="Tipo">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="pid">PID</SelectItem>
          <SelectItem value="fuzzy">Fuzzy</SelectItem>
        </SelectContent>
      </Select>,
    );
    expect(screen.getByRole('listbox')).toBeInTheDocument();
    const options = screen.getAllByRole('option');
    expect(options).toHaveLength(2);
    expect(options[0].className).toContain('data-[highlighted]:bg-selection');
  });
});
```

- [ ] **Step 2: Run to see it fail**

Run: `npm run test -- src/components/Select.test.tsx`
Expected: FAIL — `Cannot find module './Select'`.

- [ ] **Step 3: Implement**

`src/components/Select.tsx`:

```tsx
import * as React from 'react';
import { Select as SelectPrimitive } from 'radix-ui';
import { Check, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';

const Select = SelectPrimitive.Root;
const SelectGroup = SelectPrimitive.Group;
const SelectValue = SelectPrimitive.Value;

const SelectTrigger = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Trigger>
>(({ className, children, ...props }, ref) => (
  <SelectPrimitive.Trigger
    ref={ref}
    className={cn(
      'flex min-h-11 w-full items-center justify-between gap-2 rounded-control border border-rule-strong',
      'bg-surface-sunk px-3 py-2 text-sm text-text outline-none',
      'focus-visible:ring-2 focus-visible:ring-focus-ring',
      'disabled:cursor-not-allowed disabled:text-text-disabled',
      className,
    )}
    {...props}
  >
    {children}
    <SelectPrimitive.Icon asChild>
      <ChevronDown className="h-4 w-4 shrink-0 text-text-soft" aria-hidden="true" />
    </SelectPrimitive.Icon>
  </SelectPrimitive.Trigger>
));
SelectTrigger.displayName = SelectPrimitive.Trigger.displayName;

const SelectContent = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <SelectPrimitive.Portal>
    <SelectPrimitive.Content
      ref={ref}
      className={cn(
        'z-50 min-w-32 overflow-hidden rounded-card border border-rule-strong bg-surface text-text',
        className,
      )}
      {...props}
    >
      <SelectPrimitive.Viewport className="p-1">{children}</SelectPrimitive.Viewport>
    </SelectPrimitive.Content>
  </SelectPrimitive.Portal>
));
SelectContent.displayName = SelectPrimitive.Content.displayName;

const SelectLabel = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Label>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Label>
>(({ className, ...props }, ref) => (
  <SelectPrimitive.Label
    ref={ref}
    className={cn('px-3 py-1.5 text-2xs font-medium uppercase tracking-wider text-text-soft', className)}
    {...props}
  />
));
SelectLabel.displayName = SelectPrimitive.Label.displayName;

const SelectItem = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Item>
>(({ className, children, ...props }, ref) => (
  <SelectPrimitive.Item
    ref={ref}
    className={cn(
      'relative flex min-h-11 cursor-default select-none items-center gap-2 px-3 py-2 text-sm outline-none',
      'data-[highlighted]:bg-selection data-[disabled]:pointer-events-none data-[disabled]:text-text-disabled',
      className,
    )}
    {...props}
  >
    <SelectPrimitive.ItemIndicator className="absolute right-2">
      <Check className="h-4 w-4" aria-hidden="true" />
    </SelectPrimitive.ItemIndicator>
    <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
  </SelectPrimitive.Item>
));
SelectItem.displayName = SelectPrimitive.Item.displayName;

export { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue };
```

- [ ] **Step 4: Run to see it pass**

Run: `npm run test -- src/components/Select.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/components/Select.tsx src/components/Select.test.tsx
git commit -m "feat(web): Select primitive (sunk trigger, selection-token highlight)"
```

---

### Task 17: `Tabs` primitive

**Files:**
- Create: `packages/smart_pid_web/src/components/Tabs.tsx`
- Test: `packages/smart_pid_web/src/components/Tabs.test.tsx`

**Interfaces:**
- Consumes: `radix-ui` Tabs, `cn`.
- Produces: `Tabs`, `TabsList`, `TabsTrigger`, `TabsContent` — Radix pass-through. Active tab = accent underline (2px bottom border) + full text color; inactive = `--text-soft`. Triggers are `min-h-11`.

- [ ] **Step 1: Write the failing test**

`src/components/Tabs.test.tsx`:

```tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './Tabs';

function Harness() {
  return (
    <Tabs defaultValue="pid">
      <TabsList aria-label="Configuração">
        <TabsTrigger value="pid">PID</TabsTrigger>
        <TabsTrigger value="fuzzy">Fuzzy</TabsTrigger>
      </TabsList>
      <TabsContent value="pid">Ganhos PID</TabsContent>
      <TabsContent value="fuzzy">Regras fuzzy</TabsContent>
    </Tabs>
  );
}

describe('Tabs', () => {
  it('shows the default panel and switches on click', () => {
    render(<Harness />);
    expect(screen.getByText('Ganhos PID')).toBeInTheDocument();
    expect(screen.queryByText('Regras fuzzy')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('tab', { name: 'Fuzzy' }));
    expect(screen.getByText('Regras fuzzy')).toBeInTheDocument();
  });

  it('active state styles via accent underline; triggers meet the touch floor', () => {
    render(<Harness />);
    const tab = screen.getByRole('tab', { name: 'PID' });
    expect(tab).toHaveAttribute('data-state', 'active');
    expect(tab.className).toContain('data-[state=active]:border-accent');
    expect(tab.className).toContain('min-h-11');
  });
});
```

- [ ] **Step 2: Run to see it fail**

Run: `npm run test -- src/components/Tabs.test.tsx`
Expected: FAIL — `Cannot find module './Tabs'`.

- [ ] **Step 3: Implement**

`src/components/Tabs.tsx`:

```tsx
import * as React from 'react';
import { Tabs as TabsPrimitive } from 'radix-ui';
import { cn } from '@/lib/utils';

const Tabs = TabsPrimitive.Root;

const TabsList = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.List
    ref={ref}
    className={cn('inline-flex items-center gap-1 border-b border-rule', className)}
    {...props}
  />
));
TabsList.displayName = TabsPrimitive.List.displayName;

const TabsTrigger = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={cn(
      '-mb-px inline-flex min-h-11 items-center justify-center border-b-2 border-transparent px-4',
      'text-sm font-medium text-text-soft outline-none transition-colors',
      'hover:text-text focus-visible:ring-2 focus-visible:ring-focus-ring',
      'data-[state=active]:border-accent data-[state=active]:text-text',
      'disabled:pointer-events-none disabled:text-text-disabled',
      className,
    )}
    {...props}
  />
));
TabsTrigger.displayName = TabsPrimitive.Trigger.displayName;

const TabsContent = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Content
    ref={ref}
    className={cn('pt-3 outline-none focus-visible:ring-2 focus-visible:ring-focus-ring', className)}
    {...props}
  />
));
TabsContent.displayName = TabsPrimitive.Content.displayName;

export { Tabs, TabsContent, TabsList, TabsTrigger };
```

- [ ] **Step 4: Run to see it pass**

Run: `npm run test -- src/components/Tabs.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/components/Tabs.tsx src/components/Tabs.test.tsx
git commit -m "feat(web): Tabs primitive (accent underline, 44px triggers)"
```

---

### Task 18: `DropdownMenu` primitive

**Files:**
- Create: `packages/smart_pid_web/src/components/DropdownMenu.tsx`
- Test: `packages/smart_pid_web/src/components/DropdownMenu.test.tsx`

**Interfaces:**
- Consumes: `radix-ui` DropdownMenu, `cn`.
- Produces: `DropdownMenu`, `DropdownMenuTrigger`, `DropdownMenuContent`, `DropdownMenuItem` (extra prop `destructive?: boolean` — `--alarm-crit` text, the sanctioned destructive affordance), `DropdownMenuSeparator`, `DropdownMenuLabel`. Phase 4's `[cfg]` menu (Projects/Settings/Connection/Users) builds on this.

- [ ] **Step 1: Write the failing test**

`src/components/DropdownMenu.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from './DropdownMenu';

describe('DropdownMenu', () => {
  it('defaultOpen renders the menu with items, label and separator', () => {
    render(
      <DropdownMenu defaultOpen>
        <DropdownMenuTrigger asChild>
          <button type="button">Configurações</button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuLabel>Projeto</DropdownMenuLabel>
          <DropdownMenuItem>Abrir projeto</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem destructive>Excluir projeto</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>,
    );
    expect(screen.getByRole('menu')).toBeInTheDocument();
    expect(screen.getAllByRole('menuitem')).toHaveLength(2);
    expect(screen.getByText('Projeto')).toBeInTheDocument();
  });

  it('destructive items carry the sanctioned crit token, min-h-11, selection highlight', () => {
    render(
      <DropdownMenu defaultOpen>
        <DropdownMenuTrigger asChild>
          <button type="button">m</button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem destructive>Excluir</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>,
    );
    const item = screen.getByRole('menuitem', { name: 'Excluir' });
    expect(item.className).toContain('text-alarm-crit');
    expect(item.className).toContain('min-h-11');
    expect(item.className).toContain('data-[highlighted]:bg-selection');
  });
});
```

- [ ] **Step 2: Run to see it fail**

Run: `npm run test -- src/components/DropdownMenu.test.tsx`
Expected: FAIL — `Cannot find module './DropdownMenu'`.

- [ ] **Step 3: Implement**

`src/components/DropdownMenu.tsx`:

```tsx
import * as React from 'react';
import { DropdownMenu as DropdownMenuPrimitive } from 'radix-ui';
import { cn } from '@/lib/utils';

const DropdownMenu = DropdownMenuPrimitive.Root;
const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger;

const DropdownMenuContent = React.forwardRef<
  React.ElementRef<typeof DropdownMenuPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Content>
>(({ className, sideOffset = 4, ...props }, ref) => (
  <DropdownMenuPrimitive.Portal>
    <DropdownMenuPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      className={cn(
        'z-50 min-w-40 rounded-card border border-rule-strong bg-surface p-1 text-text',
        className,
      )}
      {...props}
    />
  </DropdownMenuPrimitive.Portal>
));
DropdownMenuContent.displayName = DropdownMenuPrimitive.Content.displayName;

interface DropdownMenuItemProps
  extends React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Item> {
  /** §6.3: destructive actions use --alarm-crit on their confirm affordance. */
  destructive?: boolean;
}

const DropdownMenuItem = React.forwardRef<
  React.ElementRef<typeof DropdownMenuPrimitive.Item>,
  DropdownMenuItemProps
>(({ className, destructive = false, ...props }, ref) => (
  <DropdownMenuPrimitive.Item
    ref={ref}
    className={cn(
      'flex min-h-11 cursor-default select-none items-center gap-2 rounded-control px-3 text-sm outline-none',
      'data-[highlighted]:bg-selection data-[disabled]:pointer-events-none data-[disabled]:text-text-disabled',
      destructive && 'text-alarm-crit',
      className,
    )}
    {...props}
  />
));
DropdownMenuItem.displayName = DropdownMenuPrimitive.Item.displayName;

const DropdownMenuSeparator = React.forwardRef<
  React.ElementRef<typeof DropdownMenuPrimitive.Separator>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Separator>
>(({ className, ...props }, ref) => (
  <DropdownMenuPrimitive.Separator
    ref={ref}
    className={cn('my-1 h-px bg-rule', className)}
    {...props}
  />
));
DropdownMenuSeparator.displayName = DropdownMenuPrimitive.Separator.displayName;

const DropdownMenuLabel = React.forwardRef<
  React.ElementRef<typeof DropdownMenuPrimitive.Label>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Label>
>(({ className, ...props }, ref) => (
  <DropdownMenuPrimitive.Label
    ref={ref}
    className={cn('px-3 py-1.5 text-2xs font-medium uppercase tracking-wider text-text-soft', className)}
    {...props}
  />
));
DropdownMenuLabel.displayName = DropdownMenuPrimitive.Label.displayName;

export {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
};
```

- [ ] **Step 4: Run to see it pass**

Run: `npm run test -- src/components/DropdownMenu.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/components/DropdownMenu.tsx src/components/DropdownMenu.test.tsx
git commit -m "feat(web): DropdownMenu primitive (cfg-menu base, destructive item token)"
```

---

### Task 19: `Toast` / `Toaster` primitive

**Files:**
- Create: `packages/smart_pid_web/src/components/Toast.tsx`
- Test: `packages/smart_pid_web/src/components/Toast.test.tsx`

**Interfaces:**
- Consumes: `radix-ui` Toast, `cn`, `lucide-react` `X`.
- Produces (all from `@/components/Toast`):
  - `type ToastTone = 'default' | 'crit' | 'warn'`
  - `interface ToastOptions { title: string; description?: string; tone?: ToastTone; durationMs?: number }`
  - `toast(opts: ToastOptions): string` (returns id; module-level store, callable outside React — phase 3's 403 handler calls `toast({ title: 'sem permissão', tone: 'warn' })`)
  - `dismissToast(id: string): void`, `clearToasts(): void` (used by tests and logout)
  - `useToasts(): readonly ActiveToast[]` where `interface ActiveToast extends ToastOptions { id: string }`
  - `Toaster(): JSX.Element` — mount ONCE at app root (phase 4). Radix gives `role="status"`; close button `aria-label="Fechar"`; max 3 toasts retained.

- [ ] **Step 1: Write the failing test**

`src/components/Toast.test.tsx`:

```tsx
import { act, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { Toaster, clearToasts, dismissToast, toast } from './Toast';

afterEach(() => {
  act(() => {
    clearToasts();
  });
});

describe('Toast/Toaster', () => {
  it('toast() renders a status with title, description and Fechar', () => {
    render(<Toaster />);
    act(() => {
      toast({ title: 'Salvo', description: 'Parâmetros aplicados' });
    });
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByText('Salvo')).toBeInTheDocument();
    expect(screen.getByText('Parâmetros aplicados')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Fechar' })).toBeInTheDocument();
  });

  it('tones map to severity tokens (crit/warn) with default surface otherwise', () => {
    render(<Toaster />);
    act(() => {
      toast({ title: 'sem permissão', tone: 'warn' });
    });
    const root = screen.getByText('sem permissão').closest('li');
    expect(root?.className).toContain('border-alarm-warn');
  });

  it('dismissToast removes by id; keeps at most 3', () => {
    render(<Toaster />);
    let id = '';
    act(() => {
      id = toast({ title: 'a' });
      toast({ title: 'b' });
      toast({ title: 'c' });
      toast({ title: 'd' });
    });
    expect(screen.queryByText('a')).not.toBeInTheDocument(); // evicted (max 3)
    act(() => {
      dismissToast(id);
    });
    expect(screen.getByText('d')).toBeInTheDocument();
  });
});
```

(Radix `Toast.Root` renders an `<li>` with `role="status"` inside the viewport `<ol>`.)

- [ ] **Step 2: Run to see it fail**

Run: `npm run test -- src/components/Toast.test.tsx`
Expected: FAIL — `Cannot find module './Toast'`.

- [ ] **Step 3: Implement**

`src/components/Toast.tsx`:

```tsx
import * as React from 'react';
import { Toast as ToastPrimitive } from 'radix-ui';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';

export type ToastTone = 'default' | 'crit' | 'warn';

export interface ToastOptions {
  title: string;
  description?: string;
  tone?: ToastTone;
  durationMs?: number;
}

export interface ActiveToast extends ToastOptions {
  id: string;
}

const MAX_TOASTS = 3;
const DEFAULT_DURATION_MS = 5000;

// Module-level store so `toast()` is callable outside React (e.g. the phase-3
// apiClient 403 handler). Toaster subscribes; tests reset via clearToasts().
let counter = 0;
let toasts: readonly ActiveToast[] = [];
const listeners = new Set<(next: readonly ActiveToast[]) => void>();

function emit(): void {
  for (const listener of listeners) listener(toasts);
}

export function toast(opts: ToastOptions): string {
  const id = String(++counter);
  toasts = [...toasts.slice(-(MAX_TOASTS - 1)), { tone: 'default', durationMs: DEFAULT_DURATION_MS, ...opts, id }];
  emit();
  return id;
}

export function dismissToast(id: string): void {
  toasts = toasts.filter((t) => t.id !== id);
  emit();
}

export function clearToasts(): void {
  toasts = [];
  emit();
}

export function useToasts(): readonly ActiveToast[] {
  const [state, setState] = React.useState(toasts);
  React.useEffect(() => {
    listeners.add(setState);
    setState(toasts);
    return () => {
      listeners.delete(setState);
    };
  }, []);
  return state;
}

const TONE_CLASS: Record<ToastTone, string> = {
  default: 'border-rule-strong bg-surface',
  crit: 'border-alarm-crit bg-alarm-crit-bg',
  warn: 'border-alarm-warn bg-alarm-warn-bg',
};

/** Mount ONCE at the app root (phase 4). */
export function Toaster() {
  const items = useToasts();
  return (
    <ToastPrimitive.Provider swipeDirection="right">
      {items.map((t) => (
        <ToastPrimitive.Root
          key={t.id}
          duration={t.durationMs}
          onOpenChange={(open) => {
            if (!open) dismissToast(t.id);
          }}
          className={cn(
            'relative flex flex-col gap-1 rounded-card border p-3 pr-12 text-text',
            TONE_CLASS[t.tone ?? 'default'],
          )}
        >
          <ToastPrimitive.Title className="text-sm font-medium">{t.title}</ToastPrimitive.Title>
          {t.description ? (
            <ToastPrimitive.Description className="text-xs text-text-soft">
              {t.description}
            </ToastPrimitive.Description>
          ) : null}
          <ToastPrimitive.Close
            aria-label="Fechar"
            className={cn(
              'absolute right-0 top-0 inline-flex min-h-11 min-w-11 items-center justify-center',
              'text-text-soft outline-none hover:text-text focus-visible:ring-2 focus-visible:ring-focus-ring',
            )}
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </ToastPrimitive.Close>
        </ToastPrimitive.Root>
      ))}
      <ToastPrimitive.Viewport
        className="fixed bottom-4 right-4 z-50 flex w-96 max-w-[calc(100vw-2rem)] flex-col gap-2 outline-none"
      />
    </ToastPrimitive.Provider>
  );
}
```

- [ ] **Step 4: Run to see it pass**

Run: `npm run test -- src/components/Toast.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/components/Toast.tsx src/components/Toast.test.tsx
git commit -m "feat(web): Toast/Toaster primitive (module store, severity tones, Fechar)"
```

---

### Task 20: `Command` palette primitive (cmdk)

**Files:**
- Create: `packages/smart_pid_web/src/components/Command.tsx`
- Test: `packages/smart_pid_web/src/components/Command.test.tsx`

**Interfaces:**
- Consumes: `cmdk`, Dialog (Task 12), `cn`, `lucide-react` `Search`.
- Produces: `Command`, `CommandInput` (default `placeholder="Buscar comando…"`), `CommandList`, `CommandEmpty` (default children `Nenhum resultado.`), `CommandGroup`, `CommandItem`, and `CommandDialog` — `interface CommandDialogProps { open: boolean; onOpenChange: (open: boolean) => void; label?: string; children: React.ReactNode }` (default `label="Paleta de comandos"`). Phase 4 binds the `[k]` shortcut and provides items.

- [ ] **Step 1: Write the failing test**

`src/components/Command.test.tsx`:

```tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Command, CommandEmpty, CommandInput, CommandItem, CommandList } from './Command';

function Harness() {
  return (
    <Command label="Paleta de comandos">
      <CommandInput />
      <CommandList>
        <CommandEmpty />
        <CommandItem onSelect={() => {}}>Ir para alarmes</CommandItem>
        <CommandItem onSelect={() => {}}>Trocar tema</CommandItem>
      </CommandList>
    </Command>
  );
}

describe('Command palette', () => {
  it('renders the pt-BR input placeholder and all items', () => {
    render(<Harness />);
    expect(screen.getByPlaceholderText('Buscar comando…')).toBeInTheDocument();
    expect(screen.getAllByRole('option')).toHaveLength(2);
  });

  it('filters items as the user types', () => {
    render(<Harness />);
    fireEvent.change(screen.getByPlaceholderText('Buscar comando…'), { target: { value: 'tema' } });
    expect(screen.getByText('Trocar tema')).toBeInTheDocument();
    expect(screen.queryByText('Ir para alarmes')).not.toBeInTheDocument();
  });

  it('shows the pt-BR empty state when nothing matches', () => {
    render(<Harness />);
    fireEvent.change(screen.getByPlaceholderText('Buscar comando…'), { target: { value: 'zzz' } });
    expect(screen.getByText('Nenhum resultado.')).toBeInTheDocument();
  });

  it('Enter selects the highlighted item', () => {
    const onSelect = vi.fn();
    render(
      <Command label="p">
        <CommandInput />
        <CommandList>
          <CommandItem onSelect={onSelect}>Única ação</CommandItem>
        </CommandList>
      </Command>,
    );
    const input = screen.getByRole('combobox');
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onSelect).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Run to see it fail**

Run: `npm run test -- src/components/Command.test.tsx`
Expected: FAIL — `Cannot find module './Command'`.

- [ ] **Step 3: Implement**

`src/components/Command.tsx`:

```tsx
import * as React from 'react';
import { Command as CommandPrimitive } from 'cmdk';
import { Search } from 'lucide-react';
import { Dialog, DialogContent } from '@/components/Dialog';
import { cn } from '@/lib/utils';

const Command = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive>
>(({ className, ...props }, ref) => (
  <CommandPrimitive
    ref={ref}
    className={cn('flex w-full flex-col overflow-hidden bg-surface text-text', className)}
    {...props}
  />
));
Command.displayName = CommandPrimitive.displayName;

const CommandInput = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Input>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Input>
>(({ className, placeholder = 'Buscar comando…', ...props }, ref) => (
  <div className="flex items-center gap-2 border-b border-rule px-3">
    <Search className="h-4 w-4 shrink-0 text-text-soft" aria-hidden="true" />
    <CommandPrimitive.Input
      ref={ref}
      placeholder={placeholder}
      className={cn(
        'min-h-11 w-full bg-transparent text-sm text-text outline-none placeholder:text-text-disabled',
        className,
      )}
      {...props}
    />
  </div>
));
CommandInput.displayName = CommandPrimitive.Input.displayName;

const CommandList = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.List>
>(({ className, ...props }, ref) => (
  <CommandPrimitive.List
    ref={ref}
    className={cn('max-h-72 overflow-y-auto p-1', className)}
    {...props}
  />
));
CommandList.displayName = CommandPrimitive.List.displayName;

const CommandEmpty = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Empty>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Empty>
>(({ children = 'Nenhum resultado.', className, ...props }, ref) => (
  <CommandPrimitive.Empty
    ref={ref}
    className={cn('py-6 text-center text-sm text-text-soft', className)}
    {...props}
  >
    {children}
  </CommandPrimitive.Empty>
));
CommandEmpty.displayName = CommandPrimitive.Empty.displayName;

const CommandGroup = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Group>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Group>
>(({ className, ...props }, ref) => (
  <CommandPrimitive.Group
    ref={ref}
    className={cn(
      '[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5',
      '[&_[cmdk-group-heading]]:text-2xs [&_[cmdk-group-heading]]:font-medium',
      '[&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider',
      '[&_[cmdk-group-heading]]:text-text-soft',
      className,
    )}
    {...props}
  />
));
CommandGroup.displayName = CommandPrimitive.Group.displayName;

const CommandItem = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Item>
>(({ className, ...props }, ref) => (
  <CommandPrimitive.Item
    ref={ref}
    className={cn(
      'flex min-h-11 cursor-default select-none items-center gap-2 rounded-control px-2 text-sm outline-none',
      'data-[selected=true]:bg-selection data-[disabled=true]:pointer-events-none data-[disabled=true]:text-text-disabled',
      className,
    )}
    {...props}
  />
));
CommandItem.displayName = CommandPrimitive.Item.displayName;

export interface CommandDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  label?: string;
  children: React.ReactNode;
}

/** The `[k]` palette shell (§6.9). Phase 4 binds the shortcut and the actions. */
export function CommandDialog({ open, onOpenChange, label = 'Paleta de comandos', children }: CommandDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-label={label} className="top-[20%] translate-y-0 p-0">
        <Command label={label}>{children}</Command>
      </DialogContent>
    </Dialog>
  );
}

export { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList };
```

- [ ] **Step 4: Run to see it pass**

Run: `npm run test -- src/components/Command.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/components/Command.tsx src/components/Command.test.tsx
git commit -m "feat(web): Command palette primitive (cmdk, pt-BR copy, dialog shell)"
```

---

### Task 21: `VirtualList` primitive

**Files:**
- Create: `packages/smart_pid_web/src/components/VirtualList.tsx`
- Test: `packages/smart_pid_web/src/components/VirtualList.test.tsx`

**Interfaces:**
- Consumes: `@tanstack/react-virtual` `useVirtualizer`, `cn`.
- Produces: `VirtualList<T>`, `interface VirtualListProps<T> { items: readonly T[]; renderItem: (item: T, index: number) => React.ReactNode; height: number | string; estimateSize?: number; overscan?: number; getKey?: (item: T, index: number) => React.Key; role?: string; 'aria-label'?: string; className?: string }` — defaults `estimateSize=40`, `overscan=8`, `role='list'` (rows get `listitem` when role is `list`). Phase 6's alarm flood renders through this. Row positioning uses the sanctioned dynamic inline transform.

- [ ] **Step 1: Write the failing test**

`src/components/VirtualList.test.tsx` (jsdom has no layout: stub the prototype `offset*` like the retired AlarmPanel test did — the virtualizer measures a real viewport and windows the rows):

```tsx
import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { VirtualList } from './VirtualList';

const offsetWidthDesc = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetWidth');
const offsetHeightDesc = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetHeight');

beforeEach(() => {
  Object.defineProperty(HTMLElement.prototype, 'offsetWidth', { configurable: true, value: 600 });
  Object.defineProperty(HTMLElement.prototype, 'offsetHeight', { configurable: true, value: 400 });
});

afterEach(() => {
  if (offsetWidthDesc) Object.defineProperty(HTMLElement.prototype, 'offsetWidth', offsetWidthDesc);
  if (offsetHeightDesc) Object.defineProperty(HTMLElement.prototype, 'offsetHeight', offsetHeightDesc);
});

const items = Array.from({ length: 1000 }, (_, i) => `Alarme ${i}`);

describe('VirtualList', () => {
  it('windows a 1000-row flood: renders a small subset, sizes the scroll body to the total', () => {
    render(
      <VirtualList
        items={items}
        height={400}
        estimateSize={40}
        aria-label="Alarmes ativos"
        renderItem={(item) => <span>{item}</span>}
      />,
    );
    const rendered = screen.getAllByRole('listitem');
    expect(rendered.length).toBeGreaterThan(0);
    expect(rendered.length).toBeLessThan(60); // windowed, not 1000
    const list = screen.getByRole('list', { name: 'Alarmes ativos' });
    const body = list.firstElementChild as HTMLElement;
    expect(body.style.height).toBe('40000px'); // 1000 × 40
  });

  it('renders the first row content', () => {
    render(
      <VirtualList items={items} height={400} renderItem={(item) => <span>{item}</span>} />,
    );
    expect(screen.getByText('Alarme 0')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to see it fail**

Run: `npm run test -- src/components/VirtualList.test.tsx`
Expected: FAIL — `Cannot find module './VirtualList'`.

- [ ] **Step 3: Implement**

`src/components/VirtualList.tsx`:

```tsx
import { useRef, type Key, type ReactNode } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { cn } from '@/lib/utils';

export interface VirtualListProps<T> {
  items: readonly T[];
  renderItem: (item: T, index: number) => ReactNode;
  /** Scroll viewport height (px number or any CSS size). */
  height: number | string;
  /** Estimated row height in px (fixed-size windowing). */
  estimateSize?: number;
  overscan?: number;
  getKey?: (item: T, index: number) => Key;
  role?: string;
  'aria-label'?: string;
  className?: string;
}

/** Windowed list for floods (§7: alarm flood). Fixed-size rows, no measurement. */
export function VirtualList<T>({
  items,
  renderItem,
  height,
  estimateSize = 40,
  overscan = 8,
  getKey,
  role = 'list',
  'aria-label': ariaLabel,
  className,
}: VirtualListProps<T>) {
  const parentRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => estimateSize,
    overscan,
  });

  return (
    <div
      ref={parentRef}
      role={role}
      aria-label={ariaLabel}
      className={cn('overflow-y-auto', className)}
      style={{ height }}
    >
      <div className="relative w-full" style={{ height: `${virtualizer.getTotalSize()}px` }}>
        {virtualizer.getVirtualItems().map((v) => (
          <div
            key={getKey ? getKey(items[v.index], v.index) : v.key}
            role={role === 'list' ? 'listitem' : undefined}
            data-index={v.index}
            className="absolute left-0 top-0 w-full"
            style={{ height: `${v.size}px`, transform: `translateY(${v.start}px)` }}
          >
            {renderItem(items[v.index], v.index)}
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run to see it pass**

Run: `npm run test -- src/components/VirtualList.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/components/VirtualList.tsx src/components/VirtualList.test.tsx
git commit -m "feat(web): VirtualList primitive (react-virtual windowing for floods)"
```

---

### Task 22: `MissingState` primitive (loading / empty / error-disconnect)

**Files:**
- Create: `packages/smart_pid_web/src/components/MissingState.tsx`
- Test: `packages/smart_pid_web/src/components/MissingState.test.tsx`

**Interfaces:**
- Consumes: `Button` (Task 7), `cn`.
- Produces (all from `@/components/MissingState`):
  - `LoadingState`, `interface LoadingStateProps { label: string; bars?: number; lastKnown?: React.ReactNode; className?: string }` — static placeholder bars (NO shimmer), `aria-busy="true"`.
  - `EmptyState`, `interface EmptyStateProps { message: string; hint?: string; action?: React.ReactNode; className?: string }`.
  - `ErrorState`, `interface ErrorStateProps { message: string; onRetry?: () => void; retryLabel?: string; stale?: React.ReactNode; className?: string }` — `role="alert"`, default `retryLabel='Tentar novamente'`; covers the error-disconnect state (§11: loading and empty are designed states, never spinners over blank space; 5xx never blank).

- [ ] **Step 1: Write the failing test**

`src/components/MissingState.test.tsx`:

```tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { EmptyState, ErrorState, LoadingState } from './MissingState';

describe('MissingState', () => {
  it('LoadingState: aria-busy, static bars, greyed last-known value', () => {
    render(<LoadingState label="Carregando controladores…" lastKnown={<span>150.2</span>} />);
    const region = screen.getByLabelText('Carregando controladores…');
    expect(region).toHaveAttribute('aria-busy', 'true');
    expect(region.querySelectorAll('[data-slot="loading-bar"]')).toHaveLength(4);
    expect(screen.getByText('150.2')).toBeInTheDocument();
  });

  it('LoadingState carries no animation utilities (motion must not draw the eye)', () => {
    render(<LoadingState label="x" />);
    expect(screen.getByLabelText('x').innerHTML).not.toContain('animate-');
  });

  it('EmptyState: message + hint + action slot', () => {
    render(<EmptyState message="Nenhum alarme ativo" hint="Tudo operando normalmente" />);
    expect(screen.getByText('Nenhum alarme ativo')).toBeInTheDocument();
    expect(screen.getByText('Tudo operando normalmente')).toBeInTheDocument();
  });

  it('ErrorState: role=alert with pt-BR retry affordance', () => {
    const onRetry = vi.fn();
    render(<ErrorState message="Sem conexão com o servidor" onRetry={onRetry} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Sem conexão com o servidor');
    fireEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Run to see it fail**

Run: `npm run test -- src/components/MissingState.test.tsx`
Expected: FAIL — `Cannot find module './MissingState'`.

- [ ] **Step 3: Implement**

`src/components/MissingState.tsx`:

```tsx
import type { ReactNode } from 'react';
import { Button } from '@/components/Button';
import { cn } from '@/lib/utils';

/**
 * Designed missing states (§11): loading and empty are states, not spinners
 * over blank space; 5xx/disconnect never renders blank. LoadingState is STATIC
 * (no shimmer/skeleton animation) — motion must not draw the operator's eye.
 */

const BAR_WIDTHS = ['w-2/3', 'w-1/2', 'w-3/4', 'w-2/5'] as const;

export interface LoadingStateProps {
  label: string;
  bars?: number;
  /** Greyed last-known value carried over while refreshing. */
  lastKnown?: ReactNode;
  className?: string;
}

export function LoadingState({ label, bars = 4, lastKnown, className }: LoadingStateProps) {
  return (
    <div aria-busy="true" aria-label={label} className={cn('flex flex-col gap-2 p-4', className)}>
      <span className="text-sm text-text-soft">{label}</span>
      {Array.from({ length: bars }, (_, i) => (
        <div
          key={i}
          data-slot="loading-bar"
          className={cn('h-2 bg-bar-track', BAR_WIDTHS[i % BAR_WIDTHS.length])}
        />
      ))}
      {lastKnown ? <div className="text-text-disabled">{lastKnown}</div> : null}
    </div>
  );
}

export interface EmptyStateProps {
  message: string;
  hint?: string;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ message, hint, action, className }: EmptyStateProps) {
  return (
    <div className={cn('flex flex-col items-center gap-2 p-8 text-center', className)}>
      <p className="text-sm font-medium text-text">{message}</p>
      {hint ? <p className="text-xs text-text-soft">{hint}</p> : null}
      {action}
    </div>
  );
}

export interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
  /** Stale last-known content shown greyed under the error. */
  stale?: ReactNode;
  className?: string;
}

export function ErrorState({
  message,
  onRetry,
  retryLabel = 'Tentar novamente',
  stale,
  className,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn('flex flex-col items-start gap-2 border border-rule-strong bg-surface-sunk p-4', className)}
    >
      <p className="text-sm font-medium text-text">{message}</p>
      {stale ? <div className="text-xs text-text-disabled">{stale}</div> : null}
      {onRetry ? (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          {retryLabel}
        </Button>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 4: Run to see it pass**

Run: `npm run test -- src/components/MissingState.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/components/MissingState.tsx src/components/MissingState.test.tsx
git commit -m "feat(web): MissingState primitive (static loading, empty, error-disconnect)"
```

---

### Task 23: `Trend` primitive (creates `lib/uplotTheme`) — the signature element

**Files:**
- Create: `packages/smart_pid_web/src/lib/uplotTheme.ts`
- Create: `packages/smart_pid_web/src/components/Trend.tsx`
- Test: `packages/smart_pid_web/src/lib/uplotTheme.test.ts`
- Test: `packages/smart_pid_web/src/components/Trend.test.tsx`

**Interfaces:**
- Consumes: `uplot` 1.6.31, tokens (`--trace-*`, `--trend-*`, `--accent`, `--font-data`), `cn`.
- Produces — from `@/lib/uplotTheme` (retained pattern, re-pointed at the NEW token names):
  ```ts
  interface TrendTokens {
    pv: string; sp: string; co: string;          // --trace-pv/--trace-sp/--trace-co
    grid: string; axis: string; bg: string;      // --trend-grid/--trend-axis/--trend-bg
    accent: string;                              // --accent (AI ticks)
    pvWidth: number; spWidth: number; coWidth: number; // parseFloat('2px') → 2
    font: string;                                // `12px ${--font-data}`
  }
  function readTrendTokens(style: CSSStyleDeclaration): TrendTokens;
  interface UplotTheme {
    axesStroke: string; gridStroke: string; bg: string; accent: string; axisFont: string;
    series: {
      pv: { stroke: string; width: number };
      sp: { stroke: string; width: number; dash: [number, number] };   // [6, 4]
      co: { stroke: string; width: number; scale: 'co' };
    };
  }
  function buildUplotTheme(tokens: TrendTokens): UplotTheme;
  ```
- Produces — from `@/components/Trend` (props designed for phases 4/7):
  ```ts
  interface TrendSeriesData { t: number[]; pv: (number | null)[]; sp: (number | null)[]; co: (number | null)[] }
  interface TrendAxisConfig { min?: number; max?: number; unit?: string }
  interface TrendPenTip { t: number; pv: number }
  interface TrendProps {
    data: TrendSeriesData;
    ariaLabel: string;                      // pt-BR at call sites
    pvAxis?: TrendAxisConfig;               // left axis (PV/SP); auto-range when omitted
    coAxis?: TrendAxisConfig;               // right axis; defaults 0–100
    penTip?: TrendPenTip | null;            // §6.7 TRUE latest UNDECIMATED sample (windowBuffer head, phase 3) — null hides the pen
    aiTicks?: readonly number[];            // unix-seconds of ACTION.AI.{id} events (phase 3 buffers them)
    glow?: boolean;                         // Phosphor halo pass; caller decides via theme (phase 4)
    height?: number;                        // px, default 280
    className?: string;
  }
  function Trend(props: TrendProps): JSX.Element;
  ```
- Behavior contracts: uPlot bakes stroke colors at construction → **`themeKey` re-instantiation** (MutationObserver on `data-theme`, exposed as `data-theme-key` for tests); pen tip drawn in a `hooks.draw` pass at `valToPos(penTip.t/pv)` — a static marker (frozen by construction under reduced motion, §6.7); halo = 2 wider low-alpha re-strokes + crisp re-stroke of the PV path — **`ctx.shadowBlur` never appears** (§6.7 ban; the automated gate is phase-4 acceptance); AI ticks are 6px accent ticks rising from the time axis; SP dashed `[6,4]`; CO on the right `co` scale.

- [ ] **Step 1: Write the failing lib test**

`src/lib/uplotTheme.test.ts`:

```ts
import { afterEach, describe, expect, it } from 'vitest';
import { buildUplotTheme, readTrendTokens } from './uplotTheme';

const root = document.documentElement;
const SET = {
  '--trace-pv': '#1B4F87',
  '--trace-sp': '#7C8894',
  '--trace-co': '#BC7211',
  '--trend-grid': '#E4E9EF',
  '--trend-axis': '#9DA9B5',
  '--trend-bg': '#EEF1F5',
  '--accent': '#0E6B6B',
  '--trend-pv-width': '2px',
  '--trend-sp-width': '1.5px',
  '--trend-co-width': '1.5px',
  '--font-data': "'Geist Mono', monospace",
} as const;

afterEach(() => {
  for (const name of Object.keys(SET)) root.style.removeProperty(name);
});

function apply(): CSSStyleDeclaration {
  for (const [name, value] of Object.entries(SET)) root.style.setProperty(name, value);
  return getComputedStyle(root);
}

describe('readTrendTokens (NEW §6.4 names)', () => {
  it('reads traces, grid, axis, bg, accent and px widths', () => {
    const t = readTrendTokens(apply());
    expect(t.pv).toBe('#1B4F87');
    expect(t.sp).toBe('#7C8894');
    expect(t.co).toBe('#BC7211');
    expect(t.grid).toBe('#E4E9EF');
    expect(t.axis).toBe('#9DA9B5');
    expect(t.bg).toBe('#EEF1F5');
    expect(t.accent).toBe('#0E6B6B');
    expect(t.pvWidth).toBe(2); // parseFloat('2px')
    expect(t.spWidth).toBe(1.5);
    expect(t.font).toBe("12px 'Geist Mono', monospace");
  });

  it('falls back to 1.5 width when a width token is missing (defensive)', () => {
    const style = apply();
    root.style.removeProperty('--trend-co-width');
    expect(readTrendTokens(getComputedStyle(root)).coWidth).toBe(1.5);
    void style;
  });
});

describe('buildUplotTheme', () => {
  it('maps series treatments: SP dashed [6,4], CO on the co scale', () => {
    const theme = buildUplotTheme(readTrendTokens(apply()));
    expect(theme.series.sp.dash).toEqual([6, 4]);
    expect(theme.series.co.scale).toBe('co');
    expect(theme.series.pv.width).toBe(2);
    expect(theme.axisFont).toContain('Geist Mono');
  });
});
```

- [ ] **Step 2: Run to see it fail**

Run: `npm run test -- src/lib/uplotTheme.test.ts`
Expected: FAIL — `Cannot find module './uplotTheme'`.

- [ ] **Step 3: Implement the token bridge**

`src/lib/uplotTheme.ts`:

```ts
/**
 * uPlot token bridge (§7, retained pattern re-pointed at the §6.4 names:
 * --trace-* for series, --trend-* for chart chrome). uPlot bakes stroke colors
 * at construction — Trend pairs this with themeKey re-instantiation.
 */
export interface TrendTokens {
  pv: string;
  sp: string;
  co: string;
  grid: string;
  axis: string;
  bg: string;
  /** --accent: AI intervention ticks (§6.7) — interactive chrome, never a trace/alarm color. */
  accent: string;
  /** Per-series line weights (CSS px) from --trend-*-width ('2px' → 2). */
  pvWidth: number;
  spWidth: number;
  coWidth: number;
  /** Axis label font shorthand, derived from --font-data. */
  font: string;
}

const DEFAULT_LINE_WIDTH = 1.5;
const AXIS_FONT_PX = 12;

function readWidth(style: CSSStyleDeclaration, name: string): number {
  const raw = Number.parseFloat(style.getPropertyValue(name));
  return Number.isFinite(raw) && raw > 0 ? raw : DEFAULT_LINE_WIDTH;
}

export function readTrendTokens(style: CSSStyleDeclaration): TrendTokens {
  const get = (n: string) => style.getPropertyValue(n).trim();
  const fontFamily = get('--font-data') || 'ui-monospace, monospace';
  return {
    pv: get('--trace-pv'),
    sp: get('--trace-sp'),
    co: get('--trace-co'),
    grid: get('--trend-grid'),
    axis: get('--trend-axis'),
    bg: get('--trend-bg'),
    accent: get('--accent'),
    pvWidth: readWidth(style, '--trend-pv-width'),
    spWidth: readWidth(style, '--trend-sp-width'),
    coWidth: readWidth(style, '--trend-co-width'),
    font: `${AXIS_FONT_PX}px ${fontFamily}`,
  };
}

export interface UplotTheme {
  axesStroke: string;
  gridStroke: string;
  bg: string;
  accent: string;
  axisFont: string;
  series: {
    pv: { stroke: string; width: number };
    sp: { stroke: string; width: number; dash: [number, number] };
    co: { stroke: string; width: number; scale: 'co' };
  };
}

export function buildUplotTheme(tokens: TrendTokens): UplotTheme {
  return {
    axesStroke: tokens.axis,
    gridStroke: tokens.grid,
    bg: tokens.bg,
    accent: tokens.accent,
    axisFont: tokens.font,
    series: {
      pv: { stroke: tokens.pv, width: tokens.pvWidth },
      sp: { stroke: tokens.sp, width: tokens.spWidth, dash: [6, 4] },
      co: { stroke: tokens.co, width: tokens.coWidth, scale: 'co' },
    },
  };
}
```

Run: `npm run test -- src/lib/uplotTheme.test.ts` — Expected: PASS (3 tests).

- [ ] **Step 4: Write the failing component test**

`src/components/Trend.test.tsx`:

```tsx
import { act, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { Trend, type TrendSeriesData } from './Trend';

const data: TrendSeriesData = {
  t: [1000, 1001, 1002],
  pv: [150.1, 150.2, 150.4],
  sp: [148, 148, 148],
  co: [42.0, 42.1, 42.3],
};

afterEach(() => {
  document.documentElement.removeAttribute('data-theme');
});

describe('Trend', () => {
  it('renders an accessible chart region (role=img + pt-BR name)', () => {
    render(<Trend data={data} ariaLabel="Tendência FIC-101" height={200} />);
    expect(screen.getByRole('img', { name: 'Tendência FIC-101' })).toBeInTheDocument();
  });

  it('mounts with penTip, aiTicks and glow without crashing (jsdom canvas stubbed)', () => {
    render(
      <Trend
        data={data}
        ariaLabel="t"
        penTip={{ t: 1002, pv: 150.4 }}
        aiTicks={[1001]}
        glow
        height={200}
      />,
    );
    expect(screen.getByRole('img', { name: 't' })).toBeInTheDocument();
  });

  it('re-instantiates the plot when [data-theme] flips (themeKey pattern)', async () => {
    render(<Trend data={data} ariaLabel="t" height={200} />);
    const region = screen.getByRole('img', { name: 't' });
    expect(region).toHaveAttribute('data-theme-key', '0');
    act(() => {
      document.documentElement.setAttribute('data-theme', 'phosphor');
    });
    await waitFor(() => expect(region).toHaveAttribute('data-theme-key', '1'));
  });
});
```

Run: `npm run test -- src/components/Trend.test.tsx`
Expected: FAIL — `Cannot find module './Trend'`.

- [ ] **Step 5: Implement the Trend component**

`src/components/Trend.tsx`:

```tsx
import { useEffect, useMemo, useRef, useState } from 'react';
import uPlot from 'uplot';
import 'uplot/dist/uPlot.min.css';
import { buildUplotTheme, readTrendTokens, type UplotTheme } from '@/lib/uplotTheme';
import { cn } from '@/lib/utils';

export interface TrendSeriesData {
  /** Aligned columns: unix-second timestamps + one value column per series. */
  t: number[];
  pv: (number | null)[];
  sp: (number | null)[];
  co: (number | null)[];
}

export interface TrendAxisConfig {
  min?: number;
  max?: number;
  unit?: string;
}

export interface TrendPenTip {
  t: number;
  pv: number;
}

export interface TrendProps {
  data: TrendSeriesData;
  /** Accessible name — pt-BR at call sites (e.g. "Tendência FIC-101"). */
  ariaLabel: string;
  /** Left axis (PV/SP). Auto-range when min/max omitted. */
  pvAxis?: TrendAxisConfig;
  /** Right axis (CO). Defaults 0–100 (valve %). */
  coAxis?: TrendAxisConfig;
  /**
   * §6.7 pen tip: the TRUE latest sample — NOT the tail of the decimated series.
   * Phase 3's windowBuffer exposes the undecimated head; null/undefined hides the pen.
   * A static marker by construction — under prefers-reduced-motion nothing animates.
   */
  penTip?: TrendPenTip | null;
  /** AI intervention timestamps (unix seconds) ticked on the time axis (§6.7). */
  aiTicks?: readonly number[];
  /** Phosphor halo pass on PV (§6.7). Caller decides (phase 4: theme === 'phosphor'). */
  glow?: boolean;
  height?: number;
  className?: string;
}

const PEN_RADIUS_PX = 3.5;
const AI_TICK_PX = 6;

function drawPenTip(u: uPlot, tip: TrendPenTip, color: string): void {
  const x = u.valToPos(tip.t, 'x', true);
  const y = u.valToPos(tip.pv, 'y', true);
  const ctx = u.ctx;
  ctx.save();
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(x, y, PEN_RADIUS_PX * uPlot.pxRatio, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function drawAiTicks(u: uPlot, ticks: readonly number[], color: string): void {
  const ctx = u.ctx;
  const min = u.scales.x.min ?? Number.NEGATIVE_INFINITY;
  const max = u.scales.x.max ?? Number.POSITIVE_INFINITY;
  const y0 = u.bbox.top + u.bbox.height;
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5 * uPlot.pxRatio;
  for (const t of ticks) {
    if (t < min || t > max) continue;
    const x = u.valToPos(t, 'x', true);
    ctx.beginPath();
    ctx.moveTo(x, y0);
    ctx.lineTo(x, y0 - AI_TICK_PX * uPlot.pxRatio);
    ctx.stroke();
  }
  ctx.restore();
}

/**
 * §6.7 Phosphor halo: re-stroke the PV path 2× wider at low alpha, then crisp
 * on top. ctx.shadowBlur is BANNED from the per-frame path (cost scales with
 * path length × radius at 60 fps) — never introduce it here.
 */
function drawHalo(u: uPlot, seriesIdx: number, theme: UplotTheme): void {
  const paths = (u.series[seriesIdx] as { _paths?: { stroke?: Path2D | null } })._paths;
  const stroke = paths?.stroke;
  if (!stroke) return;
  const ctx = u.ctx;
  const w = theme.series.pv.width * uPlot.pxRatio;
  ctx.save();
  ctx.strokeStyle = theme.series.pv.stroke;
  ctx.globalAlpha = 0.16;
  ctx.lineWidth = w * 3.5;
  ctx.stroke(stroke);
  ctx.globalAlpha = 0.3;
  ctx.lineWidth = w * 2;
  ctx.stroke(stroke);
  ctx.globalAlpha = 1;
  ctx.lineWidth = w;
  ctx.stroke(stroke);
  ctx.restore();
}

export function Trend({
  data,
  ariaLabel,
  pvAxis,
  coAxis,
  penTip,
  aiTicks,
  glow = false,
  height = 280,
  className,
}: TrendProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const plotRef = useRef<uPlot | null>(null);
  const [themeKey, setThemeKey] = useState(0);

  // Latest values readable from draw hooks without rebuilding the plot.
  const themeRef = useRef<UplotTheme | null>(null);
  const penTipRef = useRef<TrendPenTip | null>(penTip ?? null);
  const aiTicksRef = useRef<readonly number[]>(aiTicks ?? []);
  const glowRef = useRef(glow);
  penTipRef.current = penTip ?? null;
  aiTicksRef.current = aiTicks ?? [];
  glowRef.current = glow;

  const aligned = useMemo(
    () => [data.t, data.pv, data.sp, data.co] as uPlot.AlignedData,
    [data],
  );

  // uPlot bakes stroke colors at construction: rebuild on data-theme flips.
  useEffect(() => {
    const obs = new MutationObserver(() => setThemeKey((k) => k + 1));
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => obs.disconnect();
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const theme = buildUplotTheme(readTrendTokens(getComputedStyle(document.documentElement)));
    themeRef.current = theme;

    const opts: uPlot.Options = {
      width: el.clientWidth || 640,
      height,
      legend: { show: false },
      cursor: { x: true, y: true },
      scales: {
        x: { time: true },
        y:
          pvAxis?.min !== undefined && pvAxis?.max !== undefined
            ? { range: [pvAxis.min, pvAxis.max] }
            : {},
        co: { range: [coAxis?.min ?? 0, coAxis?.max ?? 100] },
      },
      axes: [
        {
          stroke: theme.axesStroke,
          font: theme.axisFont,
          grid: { stroke: theme.gridStroke, width: 1 },
          ticks: { stroke: theme.gridStroke, width: 1 },
        },
        {
          label: pvAxis?.unit,
          stroke: theme.axesStroke,
          font: theme.axisFont,
          grid: { stroke: theme.gridStroke, width: 1 },
          ticks: { stroke: theme.gridStroke, width: 1 },
        },
        {
          side: 1,
          scale: 'co',
          label: coAxis?.unit ?? '%',
          stroke: theme.axesStroke,
          font: theme.axisFont,
          grid: { show: false },
          ticks: { stroke: theme.gridStroke, width: 1 },
        },
      ],
      series: [
        {},
        { label: 'PV', stroke: theme.series.pv.stroke, width: theme.series.pv.width },
        { label: 'SP', stroke: theme.series.sp.stroke, width: theme.series.sp.width, dash: theme.series.sp.dash },
        { label: 'CO', stroke: theme.series.co.stroke, width: theme.series.co.width, scale: 'co' },
      ],
      hooks: {
        drawSeries: [
          (u, si) => {
            if (si === 1 && glowRef.current && themeRef.current) drawHalo(u, si, themeRef.current);
          },
        ],
        draw: [
          (u) => {
            const t = themeRef.current;
            if (!t) return;
            if (aiTicksRef.current.length > 0) drawAiTicks(u, aiTicksRef.current, t.accent);
            const tip = penTipRef.current;
            if (tip) drawPenTip(u, tip, t.series.pv.stroke);
          },
        ],
      },
    };

    try {
      plotRef.current = new uPlot(opts, aligned, el);
    } catch {
      /* jsdom has no canvas measure; ignore in tests */
    }

    const ro = new ResizeObserver(() => {
      const w = el.clientWidth;
      if (w > 0) plotRef.current?.setSize({ width: w, height });
    });
    ro.observe(el);

    return () => {
      ro.disconnect();
      plotRef.current?.destroy();
      plotRef.current = null;
    };
    // Rebuild on theme flips / geometry / axis config; data updates go through setData below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [themeKey, height, pvAxis?.min, pvAxis?.max, coAxis?.min, coAxis?.max]);

  useEffect(() => {
    plotRef.current?.setData(aligned);
  }, [aligned]);

  // Pen tip / AI ticks / glow changes need only a redraw, not a rebuild.
  useEffect(() => {
    plotRef.current?.redraw();
  }, [penTip, aiTicks, glow]);

  return (
    <div
      ref={containerRef}
      role="img"
      aria-label={ariaLabel}
      data-theme-key={themeKey}
      className={cn('w-full bg-trend-bg', className)}
      style={{ height }}
    />
  );
}
```

- [ ] **Step 6: Run to see it pass**

Run: `npm run test -- src/components/Trend.test.tsx src/lib/uplotTheme.test.ts`
Expected: PASS (6 tests across both files).

- [ ] **Step 7: Full-suite sanity + typecheck + lint (all 17 primitives now in)**

Run: `npm run test && npm run typecheck && npm run lint`
Expected: every suite green (incl. token-guard sweeping the new primitives), tsc exit 0, eslint exit 0.

- [ ] **Step 8: Commit**

```bash
git add src/lib/uplotTheme.ts src/lib/uplotTheme.test.ts src/components/Trend.tsx src/components/Trend.test.tsx
git commit -m "feat(web): Trend primitive — uPlot token bridge, themeKey rebuild, pen tip, AI ticks, halo (no shadowBlur)"
```

---

### Task 24: Bundle gate with font budget + baseline reset + CI-gates doc (E2E dark)

Spec §6.2: *"`scripts/check-bundle.mjs` is extended in phase 2 to sum `dist/assets/*.woff2` — today it measures only the entry JS chunk and its CSS, so fonts are invisible to the existing gate."*

**Files:**
- Replace: `packages/smart_pid_web/scripts/check-bundle.mjs`
- Regenerate: `packages/smart_pid_web/bundle-baseline.json` (via `--update-baseline`)
- Replace: `packages/smart_pid_web/docs/ci-gates.md`

**Interfaces:**
- Consumes: `dist/` from `npm run build` (fonts from Task 3 hashed into `dist/assets/*.woff2`).
- Produces: `npm run build:budget` (existing script chain `build` + `check:bundle`) now enforcing JS ≤ 300 KB gzip, CSS ≤ 50 KB gzip, **fonts ≤ 160 KB raw**, and regression tolerance ±10 KB vs the committed baseline `{ appPageJsGzipKb, cssGzipKb, fontsRawKb }`. The documented gate order later phases append to.

- [ ] **Step 1: Replace `scripts/check-bundle.mjs` with the font-aware version**

Full replacement content (extends the proven script — manifest resolution and gzip logic unchanged, `statSync` + woff2 sum + `fontsRawKb` baseline field added):

```js
#!/usr/bin/env node
/* eslint-disable no-undef -- Node build script: process/console are Node globals,
   and the flat ESLint config only declares browser globals for src/** + e2e/**. */
// Perf budget gate (§12): gzip size of the app-page entry JS + CSS produced by
// `vite build`, plus the RAW sum of dist/assets/*.woff2 (§6.2 font budget —
// woff2 is pre-compressed, raw ≈ transfer). Fails on budget breach or
// regression vs the committed baseline.
//
// Budgets: app-page JS <= 300 KB gzip, CSS <= 50 KB gzip, fonts <= 160 KB raw.
// Run AFTER `vite build`:  node scripts/check-bundle.mjs
//   --update-baseline   rewrite bundle-baseline.json to current sizes
//
// Zero runtime deps: gzip via Node's built-in zlib.

import { gzipSync } from 'node:zlib';
import { existsSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(__dirname, '..');
const distDir = join(webRoot, 'dist');
const assetsDir = join(distDir, 'assets');
const manifestPath = join(distDir, '.vite', 'manifest.json');
const baselinePath = join(webRoot, 'bundle-baseline.json');

const KB = 1024;
const BUDGET = { jsKb: 300, cssKb: 50, fontsKb: 160 };
// Allowed growth over the committed baseline before a regression fails CI.
const REGRESSION_TOLERANCE_KB = 10;

const updateBaseline = process.argv.includes('--update-baseline');

function fail(msg) {
  console.error(`✗ ${msg}`);
  process.exit(1);
}

function gzipKb(absPath) {
  return gzipSync(readFileSync(absPath), { level: 9 }).length / KB;
}

if (!existsSync(distDir)) {
  fail('dist/ not found. Run `npm run build` before the bundle budget check.');
}

// Resolve the app-page entry chunk + its CSS from the Vite manifest when present
// (reliable), else fall back to the largest hashed asset of each type.
let entryJs;
let entryCss;

if (existsSync(manifestPath)) {
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
  const entry = Object.values(manifest).find((e) => e.isEntry);
  if (!entry) fail('No entry chunk found in Vite manifest.');
  entryJs = join(distDir, entry.file);
  if (Array.isArray(entry.css) && entry.css.length > 0) {
    entryCss = join(distDir, entry.css[0]);
  }
}

if (!entryJs) {
  // Fallback: pick the largest JS/CSS in dist/assets.
  if (!existsSync(assetsDir)) fail('dist/assets/ not found.');
  const files = readdirSync(assetsDir);
  const pickLargest = (ext) =>
    files
      .filter((f) => f.endsWith(ext))
      .map((f) => ({ f, size: readFileSync(join(assetsDir, f)).length }))
      .sort((a, b) => b.size - a.size)[0]?.f;
  const js = pickLargest('.js');
  const css = pickLargest('.css');
  if (!js) fail('No JS asset found in dist/assets/.');
  entryJs = join(assetsDir, js);
  if (css) entryCss = join(assetsDir, css);
}

const jsKb = gzipKb(entryJs);
const cssKb = entryCss ? gzipKb(entryCss) : 0;

// §6.2 font budget: sum RAW dist/assets/*.woff2 (woff2 does not gzip further).
const fontFiles = existsSync(assetsDir)
  ? readdirSync(assetsDir).filter((f) => f.endsWith('.woff2'))
  : [];
const fontsKb = fontFiles.reduce((sum, f) => sum + statSync(join(assetsDir, f)).size, 0) / KB;

const current = {
  appPageJsGzipKb: Number(jsKb.toFixed(1)),
  cssGzipKb: Number(cssKb.toFixed(1)),
  fontsRawKb: Number(fontsKb.toFixed(1)),
};

console.log('Bundle budget check:');
console.log(`  app-page JS: ${current.appPageJsGzipKb} KB gzip  (budget ${BUDGET.jsKb} KB)`);
console.log(`  CSS:         ${current.cssGzipKb} KB gzip  (budget ${BUDGET.cssKb} KB)`);
console.log(`  fonts:       ${current.fontsRawKb} KB raw (${fontFiles.length} woff2)  (budget ${BUDGET.fontsKb} KB)`);

if (updateBaseline) {
  writeFileSync(baselinePath, `${JSON.stringify(current, null, 2)}\n`);
  console.log(`✓ Baseline written to ${baselinePath}`);
  process.exit(0);
}

let baseline;
if (existsSync(baselinePath)) {
  baseline = JSON.parse(readFileSync(baselinePath, 'utf8'));
} else {
  writeFileSync(baselinePath, `${JSON.stringify(current, null, 2)}\n`);
  baseline = current;
  console.log(`ℹ No baseline found; captured current sizes to ${baselinePath}`);
}

const errors = [];

if (current.appPageJsGzipKb > BUDGET.jsKb) {
  errors.push(`app-page JS ${current.appPageJsGzipKb} KB exceeds budget ${BUDGET.jsKb} KB`);
}
if (current.cssGzipKb > BUDGET.cssKb) {
  errors.push(`CSS ${current.cssGzipKb} KB exceeds budget ${BUDGET.cssKb} KB`);
}
if (current.fontsRawKb > BUDGET.fontsKb) {
  errors.push(`fonts ${current.fontsRawKb} KB exceed the §6.2 budget ${BUDGET.fontsKb} KB`);
}

const jsDelta = current.appPageJsGzipKb - baseline.appPageJsGzipKb;
const cssDelta = current.cssGzipKb - baseline.cssGzipKb;
const fontsDelta = current.fontsRawKb - (baseline.fontsRawKb ?? 0);
console.log(
  `  delta vs baseline: JS ${jsDelta >= 0 ? '+' : ''}${jsDelta.toFixed(1)} KB, ` +
    `CSS ${cssDelta >= 0 ? '+' : ''}${cssDelta.toFixed(1)} KB, ` +
    `fonts ${fontsDelta >= 0 ? '+' : ''}${fontsDelta.toFixed(1)} KB`,
);

if (jsDelta > REGRESSION_TOLERANCE_KB) {
  errors.push(
    `app-page JS grew ${jsDelta.toFixed(1)} KB over baseline ` +
      `(> ${REGRESSION_TOLERANCE_KB} KB tolerance). Run with --update-baseline if intentional.`,
  );
}
if (cssDelta > REGRESSION_TOLERANCE_KB) {
  errors.push(
    `CSS grew ${cssDelta.toFixed(1)} KB over baseline ` +
      `(> ${REGRESSION_TOLERANCE_KB} KB tolerance). Run with --update-baseline if intentional.`,
  );
}
if (fontsDelta > REGRESSION_TOLERANCE_KB) {
  errors.push(
    `fonts grew ${fontsDelta.toFixed(1)} KB over baseline ` +
      `(> ${REGRESSION_TOLERANCE_KB} KB tolerance). Run with --update-baseline if intentional.`,
  );
}

if (errors.length > 0) {
  for (const e of errors) console.error(`✗ ${e}`);
  process.exit(1);
}

console.log('✓ Bundle within budget and baseline tolerance.');
```

- [ ] **Step 2: Build, reset the baseline for the new tree, verify the gate**

Run (cwd `packages/smart_pid_web`):

```bash
npm run build && node scripts/check-bundle.mjs --update-baseline && npm run check:bundle
```

Expected: baseline rewritten with three fields (foundation-era JS will be far below the old 113.6 KB — that is the point of resetting), then:

```
Bundle budget check:
  app-page JS: <n> KB gzip  (budget 300 KB)
  CSS:         <n> KB gzip  (budget 50 KB)
  fonts:       <n> KB raw (3 woff2)  (budget 160 KB)
  delta vs baseline: JS +0.0 KB, CSS +0.0 KB, fonts +0.0 KB
✓ Bundle within budget and baseline tolerance.
```

`fonts` MUST report 3 woff2 files. If it reports 0, the preload/import wiring of Task 3 broke — stop and fix there.

- [ ] **Step 3: Rewrite `docs/ci-gates.md` (gate order + E2E-dark documentation)**

Full replacement content:

```markdown
# CI Gate Order (§12 — quality gates, rewrite era)

This package has **no in-repo CI workflow** (`.github/workflows/` is absent). This
document is the authority for the gate order; when a CI workflow is added it MUST
run these steps in this order, failing fast on the first non-zero exit.

## Gate order (run from `packages/smart_pid_web/`)

| # | Gate | Command | Fails when |
|---|------|---------|-----------|
| 1 | **Lint** | `npm run lint` | ESLint error |
| 2 | **Typecheck** | `npm run typecheck` | `tsc -b` reports any type error |
| 3 | **Vitest** | `npm run test` | Any unit/component/gate test fails — includes the §6.4 token-resolution gate, the Recorder/Phosphor contrast gate, the no-raw-color source guard (`src/__tests__/token-guard.test.ts`), the fonts gate, and every primitive component test |
| 4 | **Build + bundle budget** | `npm run build:budget` | `vite build` fails, OR app-page JS > 300 KB gzip, OR CSS > 50 KB gzip, OR fonts > 160 KB raw (§6.2), OR a regression > 10 KB vs `bundle-baseline.json` |
| 5 | **OpenAPI drift** | `npm run gen:api:check` | The committed `openapi.json` / `src/api/generated/openapi.ts` differ from a fresh hermetic regeneration (requires `uv sync` at the repo root) |
| 6 | **Playwright E2E** | `npm run test:e2e` | **SUSPENDED — E2E IS DARK in phases 2–3** (spec §13/§14: the foundation has no routes). Do NOT run as a gate. Re-greening is per phase from 4 on: `login-dashboard`, `faceplate`, `responsive`, `target-size`, `fatia7-auth-negative`, `themes` (rewritten) in phase 4; see the §13 table for the rest. The specs and old visual baselines stay on disk untouched until their phase (baselines are deleted in phase 11). |

`build:budget` runs `npm run build` then `npm run check:bundle` (`scripts/check-bundle.mjs`).

## Bundle budgets

- **app-page JS entry chunk: ≤ 300 KB gzip**
- **CSS: ≤ 50 KB gzip**
- **Fonts: ≤ 160 KB raw woff2 sum (§6.2)** — 1 Archivo Variable + 2 Geist Mono files
- Regression guard: > 10 KB growth over the committed `bundle-baseline.json`
  (fields `appPageJsGzipKb`, `cssGzipKb`, `fontsRawKb`) fails the gate.
  Run `npm run check:bundle -- --update-baseline` to record an intentional change.

The check resolves the entry chunk + its CSS from `dist/.vite/manifest.json`
(`build.manifest: true` in `vite.config.ts`); it falls back to the largest hashed
JS/CSS asset if the manifest is absent. Fonts are summed from `dist/assets/*.woff2`.

## Example workflow (reference — not committed)

```yaml
# .github/workflows/web-ci.yml — add when CI infra lands. Order is load-bearing.
defaults:
  run:
    working-directory: packages/smart_pid_web
steps:
  - run: npm ci
  - run: npm run lint
  - run: npm run typecheck
  - run: npm run test
  - run: npm run build:budget
  - run: uv sync            # repo root — gen:api:check shells into the backend
  - run: npm run gen:api:check
  # npm run test:e2e — DARK until phase 4 (§13); re-enable per phase
```
```

- [ ] **Step 4: Commit**

```bash
git add scripts/check-bundle.mjs bundle-baseline.json docs/ci-gates.md
git commit -m "feat(web): bundle gate sums woff2 fonts (≤160KB), baseline reset, E2E-dark documented"
```

---

### Task 25: Hermetic OpenAPI codegen — committed dump, committed types, drift gate

Spec §7: today the output is gitignored, produced against a live server, and imported by nothing. Rebuild: **committed** generated file, **hermetic** generation (dump `app.openapi()` to static JSON, no listening daemon), CI-listed **drift gate**. Sequenced after phase 0 (the role work changed the schema: users router, role field).

**Files:**
- Create: `scripts/dump_openapi.py` (repo root — new `scripts/` directory)
- Test: `tests/core/unit/test_openapi_dump.py`
- Create: `packages/smart_pid_web/openapi.json` (generated, committed)
- Create: `packages/smart_pid_web/src/api/generated/openapi.ts` (generated, committed)
- Create: `packages/smart_pid_web/scripts/check-codegen.mjs`
- Modify: `packages/smart_pid_web/package.json` (replace `gen:api`, add `gen:api:check`)
- Modify: `packages/smart_pid_web/.gitignore` (drop the `src/api/generated/` line)

**Interfaces:**
- Consumes: `smart_pid_core.adapters.inbound.api.app.create_app` (kwargs `repo`, `historian`, `user_repo`, `loop_manager`, `settings`; only `settings` is touched before serving — stubs are safe for schema introspection), `smart_pid_core.config.CoreSettings` (requires `jwt_secret`; `_env_file=None` keeps the dump hermetic vs a stray `.env`). Phase-0 surface: `/users`, `/users/{user_id}`, `UserRole` enum `["admin","user"]`, `/auth/me` (pinned with PlanPhase00).
- Produces: `packages/smart_pid_web/openapi.json` + `src/api/generated/openapi.ts` with standard openapi-typescript v7 exports `paths` / `components` / `operations`. Phase 3's `apiClient` types itself with `import type { paths, components } from '@/api/generated/openapi'`. Regeneration: `npm run gen:api`; drift gate: `npm run gen:api:check`.

- [ ] **Step 1: Write the failing backend test**

`tests/core/unit/test_openapi_dump.py`:

```python
"""Hermetic OpenAPI dump powering the web codegen chain (spec §7).

Runs the dump script as a subprocess (the CLI surface npm calls) and asserts
the phase-0 schema surface is present and the output is deterministic.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "dump_openapi.py"


def _dump(out: Path) -> dict:
    subprocess.run(
        [sys.executable, str(SCRIPT), "--out", str(out)],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
    )
    return json.loads(out.read_text(encoding="utf-8"))


def test_dump_contains_the_phase0_surface(tmp_path: Path) -> None:
    schema = _dump(tmp_path / "openapi.json")
    assert schema["info"]["title"] == "Smart PID API"
    paths = schema["paths"]
    assert "/auth/login" in paths
    assert "/auth/me" in paths
    # Phase-0 users router (spec §9): /users + /users/{user_id}.
    assert any(p == "/users" or p.startswith("/users/") for p in paths)
    # Lowercase two-role enum (spec §9). Do NOT assert per-route 403 objects:
    # plain HTTPException 403s are not auto-documented by FastAPI.
    role_enum = schema["components"]["schemas"]["UserRole"]["enum"]
    assert sorted(role_enum) == ["admin", "user"]


def test_dump_is_deterministic(tmp_path: Path) -> None:
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    _dump(a)
    _dump(b)
    assert a.read_bytes() == b.read_bytes()
```

- [ ] **Step 2: Run to see it fail**

Run (cwd repo root): `uv run pytest tests/core/unit/test_openapi_dump.py -q`
Expected: FAIL — `FileNotFoundError`/`CalledProcessError` (script does not exist).

- [ ] **Step 3: Write the dump script**

`scripts/dump_openapi.py`:

```python
#!/usr/bin/env python3
"""Dump the FastAPI OpenAPI schema to static JSON — no listening daemon.

Hermetic codegen (spec §7): build the app with stub adapter dependencies
(create_app only stores them on app.state; route/schema introspection never
touches them), call app.openapi(), write deterministic JSON. The web package
consumes the dump with openapi-typescript (npm run gen:api).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from smart_pid_core.adapters.inbound.api.app import create_app
from smart_pid_core.config import CoreSettings

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "packages" / "smart_pid_web" / "openapi.json"


def build_schema() -> dict[str, Any]:
    # _env_file=None: never read a developer's .env — the dump must be hermetic.
    settings = CoreSettings(jwt_secret="openapi-dump", _env_file=None)
    stub: Any = None
    app = create_app(
        repo=stub,
        historian=stub,
        user_repo=stub,
        loop_manager=stub,
        settings=settings,
    )
    return app.openapi()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output JSON path")
    args = parser.parse_args()

    schema = build_schema()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    # sort_keys + fixed indent + trailing newline => byte-stable committed artifact.
    args.out.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the backend test to see it pass**

Run (cwd repo root): `uv run pytest tests/core/unit/test_openapi_dump.py -q`
Expected: `2 passed`. (If `/users` is missing, phase 0 has not been merged — STOP; this plan's Global Constraints require phases 0–1 first.)

- [ ] **Step 5: Wire the npm scripts and un-ignore the generated file**

In `packages/smart_pid_web/package.json`, replace the `gen:api` line and add the check:

```json
    "gen:api": "uv run --directory ../.. python scripts/dump_openapi.py --out packages/smart_pid_web/openapi.json && openapi-typescript openapi.json -o src/api/generated/openapi.ts",
    "gen:api:check": "node scripts/check-codegen.mjs",
```

In `packages/smart_pid_web/.gitignore`, DELETE the line:

```
src/api/generated/
```

(The `eslint.config.js` ignore for `src/api/generated` stays — machine output is not linted. The token-guard already excludes `generated/`.)

- [ ] **Step 6: Generate and commit the artifacts**

Run (cwd `packages/smart_pid_web`):

```bash
npm run gen:api
```

Expected output: `wrote …/packages/smart_pid_web/openapi.json` then openapi-typescript reporting the generated file. Verify the committed shape:

```bash
grep -c 'export interface paths' src/api/generated/openapi.ts   # expected: 1
grep -c '"/users"' openapi.json                                  # expected: >= 1
npm run typecheck                                                # generated file compiles under tsc -b
```

- [ ] **Step 7: Write the drift gate**

`packages/smart_pid_web/scripts/check-codegen.mjs`:

```js
#!/usr/bin/env node
/* eslint-disable no-undef -- Node build script (same rationale as check-bundle.mjs). */
// OpenAPI drift gate (spec §7/§12): regenerate the dump + types into a temp dir
// and fail if either differs from the committed artifacts.
// CI runs `npm run gen:api:check` (requires `uv sync` at the repo root).

import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const repoRoot = resolve(webRoot, '../..');
const tmp = mkdtempSync(join(tmpdir(), 'spid-codegen-'));

function run(cmd, args, cwd) {
  const r = spawnSync(cmd, args, { cwd, stdio: ['ignore', 'inherit', 'inherit'] });
  if (r.status !== 0) {
    rmSync(tmp, { recursive: true, force: true });
    console.error(`✗ ${cmd} ${args.join(' ')} failed`);
    process.exit(1);
  }
}

const same = (a, b) => readFileSync(a, 'utf8') === readFileSync(b, 'utf8');

// Same basename as the committed dump so any tool-embedded name matches.
const freshJson = join(tmp, 'openapi.json');
const freshTs = join(tmp, 'openapi.ts');

run('uv', ['run', 'python', 'scripts/dump_openapi.py', '--out', freshJson], repoRoot);
run('npx', ['openapi-typescript', freshJson, '-o', freshTs], webRoot);

let dirty = false;
if (!same(freshJson, join(webRoot, 'openapi.json'))) {
  console.error('✗ openapi.json is stale vs the backend schema.');
  dirty = true;
}
if (!same(freshTs, join(webRoot, 'src/api/generated/openapi.ts'))) {
  console.error('✗ src/api/generated/openapi.ts is stale vs the backend schema.');
  dirty = true;
}
rmSync(tmp, { recursive: true, force: true });

if (dirty) {
  console.error('  Run `npm run gen:api` and commit the result.');
  process.exit(1);
}
console.log('✓ OpenAPI dump and generated types match the backend schema.');
```

- [ ] **Step 8: Run the drift gate to see it pass (and prove it can fail)**

Run (cwd `packages/smart_pid_web`):

```bash
npm run gen:api:check
```

Expected: `✓ OpenAPI dump and generated types match the backend schema.`

Prove the gate bites: append a space to `openapi.json`, run `npm run gen:api:check` — expected `✗ openapi.json is stale … exit 1` — then restore with `git checkout -- openapi.json`.

- [ ] **Step 9: Full phase verification + commit**

Run:

```bash
npm run lint && npm run typecheck && npm run test && npm run build:budget && npm run gen:api:check
cd ../.. && uv run pytest tests/core/unit/test_openapi_dump.py -q
```

Expected: every gate green; backend `2 passed`.

```bash
git add -A
git commit -m "feat(web): hermetic OpenAPI codegen — committed dump + types, drift gate (gen:api:check)"
```

---

## Spec coverage map (phase-2 scope → tasks)

| Spec requirement | Task(s) |
|---|---|
| §13-2 scaffold; old `src/` deleted at phase 2; freeze-inventory retired (§12) | 1 |
| §6.4 token contract, all names resolve under every theme (token-resolution gate) | 2 |
| §6.5/§6.6 exact values; §6.8 three themes; isa101 names resolve from phase 2 | 2 |
| Tailwind v4 `@theme inline` bridge over `[data-theme]` (§7 stack pins) | 2 |
| §6.2 fonts: Archivo Variable + Geist Mono 400/500, swap, preload, ≤160 KB, tabular-nums + 'zero' 1 | 2 (classes), 3 (files/wiring), 24 (dist gate) |
| §6.8 `DEFAULT_THEME=recorder`, `spid.theme`, stored-value migration (all rows tested) | 4 |
| §12 source guard re-established with lint fixtures | 5 |
| §12 contrast gates: AA text, 3:1 non-text, focus ring ≥3:1 (+≥2px as class contract) | 6 (+2px in 7–23 class assertions) |
| §7 primitives — all 17 | 7 Button · 8 Badge · 9 Readout · 10 AnalogBar · 11 Field · 12 Dialog · 13 Tooltip · 14 Switch · 15 Slider · 16 Select · 17 Tabs · 18 DropdownMenu · 19 Toast/Toaster · 20 Command · 21 VirtualList · 22 MissingState · 23 Trend |
| §6.7 pen tip (undecimated head), AI ticks, halo without `ctx.shadowBlur`, reduced-motion static pen | 23 |
| §7 uPlot token bridge + `themeKey` re-instantiation retained | 23 |
| §11 global reduced-motion policy | 2 (base CSS), 22 (static loading), 23 (static pen) |
| §12 target size ≥44×44 (class contracts now; e2e re-measures in phase 4) | 7, 11–20 |
| §6.2 bundle gate extended to woff2 (§14 risk "fonts blow the budget invisibly") | 24 |
| §13 E2E dark in phases 2–3, documented | Global Constraints, 24 |
| §7 committed hermetic codegen + CI drift gate, sequenced after phase 0 | 25 |
| pt-BR copy; `Fechar` verbatim | 12, 19 (+ all visible copy in 20, 22) |

Deliberately NOT here (later phases): routes/pages/shell/login (4), realtime + `envelope`/`windowBuffer`/`alarmMachine` + `apiClient`/TanStack wiring (3), features (4–10), isa101 retokenisation + visual baselines (11), no-shadowBlur automated gate (4).

---

## Interfaces exported (for later phases)

Everything below is the phase-2 contract. Phases 3–11 import these names verbatim; changing any of them is a breaking change to the plan chain.

### Theme system (`@/theme/…`)

```ts
// @/theme/contract
export const THEME_IDS: readonly ['recorder', 'phosphor', 'isa101'];
export type ContractThemeId = 'recorder' | 'phosphor' | 'isa101';
export const CONTRACT_TOKENS: readonly string[]; // the 43 names below

// @/theme/ThemeProvider
export type ThemeId = ContractThemeId;
export const THEMES: ReadonlyArray<{ id: ThemeId; label: string }>; // Recorder | Phosphor | ISA-101
export const STORAGE_KEY: 'spid.theme';
export const DEFAULT_THEME: ThemeId; // 'recorder'
export const LEGACY_THEME_MAP: Readonly<Record<string, ThemeId>>;
//   { 'dark-room': 'phosphor', 'md3-dark': 'recorder', 'md3-light': 'recorder', ocean: 'recorder' }
export function resolveStoredTheme(raw: string | null): ThemeId; // valid → legacy map → 'recorder'
export function ThemeProvider(props: { children: ReactNode }): JSX.Element;
export function useTheme(): { theme: ThemeId; setTheme: (t: ThemeId) => void; themes: typeof THEMES };

// @/theme/themeContrast (gate mirror — phase 11 adds isa101)
export type GateThemeId = 'recorder' | 'phosphor';
export interface ThemePalette { /* 29 hex fields, see Task 6 */ }
export const PALETTES: Record<GateThemeId, ThemePalette>;
```

### The 43 contract token names (§6.4 — closed set)

```
--bg --surface --surface-sunk
--rule --rule-strong
--text --text-soft --text-disabled
--focus-ring --selection --scrim
--accent --accent-hover --accent-sunk --accent-soft --on-accent
--alarm-crit --alarm-crit-bg --alarm-warn --alarm-warn-bg
--alarm-adv --alarm-adv-bg --alarm-log --on-alarm
--state-running --state-stopped --state-error --state-oos
--trace-pv --trace-sp --trace-co
--trend-grid --trend-axis --trend-bg
--trend-pv-width --trend-sp-width --trend-co-width
--bar-track --bar-fill --bar-marker
--font-display --font-ui --font-data
```

Tailwind utilities exist for every color token (`bg-…`/`text-…`/`border-…`/`ring-…` of the name without `--`), fonts (`font-display`, `font-ui`, `font-data`), sizes (`text-2xs|xs|sm|base|lg|xl|2xl`), radii (`rounded-card|control|pill`). CSS classes: `.numeric` (ALL numerals — Geist Mono, tabular-nums, slashed zero), `.type-display` (Archivo wdth 125 — never numerals). Non-contract layout tokens also in `:root`: `--fw-regular|medium|semibold|bold`, `--dur-fast|normal|slow`, `--ease-out|standard`, `--radius-card|control|pill`.

### Pure lib modules (`@/lib/…`) — phase 3 extends, NEVER changes these signatures

```ts
// @/lib/utils
export function cn(...inputs: ClassValue[]): string;

// @/lib/scale
export interface Scale { euMin: number; euMax: number; unit: string }
export function valueToFraction(value: number, scale: Scale): number; // clamped 0..1; 0 when span<=0
export function ticks(scale: Scale, count?: number): number[];       // inclusive, default 5, min 2

// @/lib/format
export function formatNumber(value: number | null | undefined, decimals: number): string; // '—' for null/undefined/NaN; NO units

// @/lib/uplotTheme
export interface TrendTokens {
  pv: string; sp: string; co: string; grid: string; axis: string; bg: string; accent: string;
  pvWidth: number; spWidth: number; coWidth: number; font: string;
}
export function readTrendTokens(style: CSSStyleDeclaration): TrendTokens; // reads --trace-*/--trend-*/--accent/--font-data
export interface UplotTheme {
  axesStroke: string; gridStroke: string; bg: string; accent: string; axisFont: string;
  series: {
    pv: { stroke: string; width: number };
    sp: { stroke: string; width: number; dash: [number, number] };
    co: { stroke: string; width: number; scale: 'co' };
  };
}
export function buildUplotTheme(tokens: TrendTokens): UplotTheme;
```

### The 17 primitives (`@/components/<Name>` — no barrel)

```ts
// @/components/Button
export const buttonVariants: /* cva */;
export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'destructive'; // default 'secondary'
  size?: 'md' | 'sm';                                          // default 'md'
}
export const Button: React.ForwardRefExoticComponent<ButtonProps & React.RefAttributes<HTMLButtonElement>>;

// @/components/Badge
export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: 'neutral' | 'accent' | 'crit' | 'warn' | 'adv' | 'log'; // default 'neutral'
}
export function Badge(props: BadgeProps): JSX.Element;

// @/components/Readout
export interface ReadoutProps {
  label: string; value: number | null | undefined; unit?: string;
  decimals?: number /* 1 */; size?: 'sm' | 'md' | 'lg' /* 'md' */; className?: string;
}
export function Readout(props: ReadoutProps): JSX.Element;

// @/components/AnalogBar
export type AnalogBarAlarm = 'normal' | 'warn' | 'crit';
export interface AnalogBarProps {
  label: string; value: number | null | undefined; scale: Scale; spValue?: number;
  alarm?: AnalogBarAlarm /* 'normal' */; decimals?: number /* 1 */;
  size?: 'card' | 'faceplate' /* 'card' */; className?: string;
}
export function AnalogBar(props: AnalogBarProps): JSX.Element; // role="meter"; testids: analog-bar-fill, analog-bar-sp

// @/components/Field
export interface FieldProps {
  label: string; htmlFor: string; description?: string; error?: string;
  required?: boolean; children: React.ReactNode; className?: string;
}
export function Field(props: FieldProps): JSX.Element; // ids: `${htmlFor}-desc`, `${htmlFor}-err` (role=alert)
export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> { invalid?: boolean }
export const Input: React.ForwardRefExoticComponent<InputProps & React.RefAttributes<HTMLInputElement>>;

// @/components/Dialog — Radix pass-through composition
export { Dialog, DialogPortal, DialogOverlay, DialogTrigger, DialogClose, DialogContent,
         DialogHeader, DialogFooter, DialogTitle, DialogDescription };
// DialogContent embeds the close button aria-label="Fechar" (44px). Overlay = bg-scrim.

// @/components/Tooltip
export { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger }; // mount ONE TooltipProvider at root (phase 4)

// @/components/Switch
export const Switch: React.ForwardRefExoticComponent<
  React.ComponentPropsWithoutRef<typeof SwitchPrimitive.Root> & React.RefAttributes<HTMLButtonElement>
>;

// @/components/Slider
export interface SliderProps extends React.ComponentPropsWithoutRef<typeof SliderPrimitive.Root> {
  thumbLabel?: string; // per-thumb aria-label (CO slider: 'CO manual')
}
export const Slider: React.ForwardRefExoticComponent<SliderProps & React.RefAttributes<HTMLSpanElement>>;
// thumb: 16px ≥1024, literal 44px <1024 (max-lg:h-11 max-lg:w-11) — retained e2e contract

// @/components/Select
export { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue };

// @/components/Tabs
export { Tabs, TabsContent, TabsList, TabsTrigger };

// @/components/DropdownMenu
export { DropdownMenu, DropdownMenuContent, DropdownMenuItem /* extra prop destructive?: boolean */,
         DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger };

// @/components/Toast
export type ToastTone = 'default' | 'crit' | 'warn';
export interface ToastOptions { title: string; description?: string; tone?: ToastTone; durationMs?: number /* 5000 */ }
export interface ActiveToast extends ToastOptions { id: string }
export function toast(opts: ToastOptions): string;   // callable outside React (403 handler: toast({ title: 'sem permissão', tone: 'warn' }))
export function dismissToast(id: string): void;
export function clearToasts(): void;                  // tests + logout
export function useToasts(): readonly ActiveToast[];
export function Toaster(): JSX.Element;               // mount ONCE at root (phase 4); close = "Fechar"

// @/components/Command
export { Command, CommandEmpty /* default 'Nenhum resultado.' */, CommandGroup,
         CommandInput /* default placeholder 'Buscar comando…' */, CommandItem, CommandList };
export interface CommandDialogProps {
  open: boolean; onOpenChange: (open: boolean) => void;
  label?: string /* 'Paleta de comandos' */; children: React.ReactNode;
}
export function CommandDialog(props: CommandDialogProps): JSX.Element; // phase 4 binds [k]

// @/components/VirtualList
export interface VirtualListProps<T> {
  items: readonly T[]; renderItem: (item: T, index: number) => React.ReactNode;
  height: number | string; estimateSize?: number /* 40 */; overscan?: number /* 8 */;
  getKey?: (item: T, index: number) => React.Key; role?: string /* 'list' */;
  'aria-label'?: string; className?: string;
}
export function VirtualList<T>(props: VirtualListProps<T>): JSX.Element; // phase 6 alarm flood

// @/components/MissingState
export interface LoadingStateProps { label: string; bars?: number /* 4 */; lastKnown?: React.ReactNode; className?: string }
export function LoadingState(props: LoadingStateProps): JSX.Element; // aria-busy, STATIC bars
export interface EmptyStateProps { message: string; hint?: string; action?: React.ReactNode; className?: string }
export function EmptyState(props: EmptyStateProps): JSX.Element;
export interface ErrorStateProps { message: string; onRetry?: () => void; retryLabel?: string /* 'Tentar novamente' */; stale?: React.ReactNode; className?: string }
export function ErrorState(props: ErrorStateProps): JSX.Element; // role=alert; error-disconnect state

// @/components/Trend
export interface TrendSeriesData { t: number[]; pv: (number | null)[]; sp: (number | null)[]; co: (number | null)[] }
export interface TrendAxisConfig { min?: number; max?: number; unit?: string }
export interface TrendPenTip { t: number; pv: number }
export interface TrendProps {
  data: TrendSeriesData; ariaLabel: string;
  pvAxis?: TrendAxisConfig; coAxis?: TrendAxisConfig /* right axis, default 0–100 */;
  penTip?: TrendPenTip | null;      // phase 3: windowBuffer's UNDECIMATED head; phase 4 wires it
  aiTicks?: readonly number[];      // phase 3: buffered ACTION.AI.{id} timestamps; phase 7 multitrend reuses
  glow?: boolean;                   // phase 4: theme === 'phosphor'
  height?: number /* 280 */; className?: string;
}
export function Trend(props: TrendProps): JSX.Element; // role="img"; data-theme-key attr = rebuild counter
```

### Codegen chain (phase 3's apiClient consumes)

```bash
# regenerate (repo backend must be uv-synced; runs the hermetic dump, no daemon):
npm run gen:api          # cwd packages/smart_pid_web
# CI drift gate:
npm run gen:api:check
```

- Committed artifacts: `packages/smart_pid_web/openapi.json`, `packages/smart_pid_web/src/api/generated/openapi.ts`
- Import pattern (phase 3): `import type { paths, components, operations } from '@/api/generated/openapi';`
- Backend script: `scripts/dump_openapi.py` (repo root), test `tests/core/unit/test_openapi_dump.py`

### Fonts

- Families (exact `font-family` strings): `'Archivo Variable'` (wght 100–900, wdth 62.5%–125%), `'Geist Mono'` (400, 500)
- Files: `src/assets/fonts/{archivo-latin-var,geist-mono-latin-400,geist-mono-latin-500}.woff2` (provenance: `src/assets/fonts/README.md`)
- Budget: ≤160 KB combined, gated by `src/theme/fonts.test.ts` (source) and `npm run build:budget` (dist)

### Test infrastructure

- `src/test/setup.ts` (auto-loaded): canvas 2D stub (uPlot), `ResizeObserver` stub, `matchMedia` stub, `scrollIntoView` + pointer-capture stubs (Radix). VirtualList-style tests additionally stub `HTMLElement.prototype.offsetWidth/offsetHeight` per-file (see Task 21).
- Guard exemptions: test files, `__lintfixtures__/`, `api/generated/`, `assets/`, `theme/themeContrast.ts`.

### Phase gates (Definition of Done for every later frontend phase)

```bash
npm run lint && npm run typecheck && npm run test && npm run build:budget && npm run gen:api:check
```

E2E (`npm run test:e2e`) stays DARK through phase 3; phase 4 re-greens `login-dashboard`, `faceplate`, `responsive`, `target-size`, `fatia7-auth-negative`, `themes` (rewritten) per spec §13.
