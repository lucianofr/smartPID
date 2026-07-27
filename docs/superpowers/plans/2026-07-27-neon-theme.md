# Neon Theme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `neon` as the fourth and default theme of the Smart PID web frontend — a full 41-token palette, four new glow tokens that turn "bloom" into a semantic salience channel, a self-hosted Orbitron display face, and the deletion of the last hardcoded theme name in the source.

**Architecture:** Everything lands through the existing §6.4 token contract. `CONTRACT_TOKENS` grows from 44 to 48 (four glow tokens); `--font-display` migrates out of `tokens.css :root` into every `[data-theme]` block so one theme can change the display face without touching the numeral or body faces; a new `[data-theme="neon"]` block declares all 46 per-theme names. No component learns a theme id — `TrendPanel` and `TwinTrend` stop asking `theme === 'phosphor'` and start reading `--glow-trace`, and the CSS glows hang off four token references in `src/index.css`. The WCAG contrast gate gains `neon` with zero floor changes: the palette was verified against all 43 assertions before this plan was written.

**Tech Stack:** React 18, Vite, Tailwind CSS v4 (CSS-first `@theme inline`), radix-ui, TanStack Query, uPlot, Vitest + jsdom, Playwright.

> **This plan assumes the UI-corrections plan (`docs/superpowers/plans/2026-07-27-ui-corrections.md`) landed first.** Both plans target the same branch and both touch `packages/smart_pid_web/src/features/dashboard/Faceplate.tsx`: the corrections plan **owns** and restructures it (and `src/pages/DashboardPage.tsx`); this plan only ever consumes tokens from it and never edits it. If the corrections plan has not landed, stop and land it first — otherwise the visual baselines regenerated in Task 10 will be captured against the old layout and will have to be thrown away.

## Global Constraints

- **Source spec:** `docs/superpowers/specs/2026-07-27-ui-corrections-design.md` at commit `c594f09`, section 10 plus the parts of sections 11 and 12 that concern it. This plan implements **only** section 10. Sections 4–9 (faceplate rail, AI config move, command-palette removal, `[cfg]` icons, executive nav entry, trend persistence and titles) belong to the sibling UI-corrections plan and are explicit non-goals here.
- **UI copy is pt-BR. Code, identifiers, comments and commit messages are English. Conventional Commits.**
- **Frozen accessible names — never change these strings:** the `SeriesSelector` checkbox `aria-label` `Loop {id} · {SIGNAL}`, `Configurações`, `Configurar {tag}`, `Usuário`, `Senha`, `Entrar`, `Salvar`, `Fechar`. Existing tests bind to them.
- **Interactive targets stay ≥ 44×44 CSS px (E2E-050).** No change in this plan may shrink one.
- **WCAG floors: 4.5:1 text (1.4.3), 3:1 non-text (1.4.11).** `src/theme/themeContrast.test.ts` enforces them in CI. `TEXT_FLOOR = 4.5` and `NONTEXT_FLOOR = 3.0` are not to be edited, and no assertion in that file may be deleted or relaxed.
- **`TEST_E2E.md` assertions may be re-specified or strengthened, never weakened.**
- **Frontend-only.** No Python, no backend change. The backend suite is not re-run.
- **Never use the omp `browser` tool for input.** It does not deliver CDP mouse/keyboard events (documented harness defect) and has produced false "dead control" reports. Real browser verification is `cd packages/smart_pid_web && env -u CI npx playwright test`.
- **All commands in this plan run from the repo root** unless the step says otherwise. The frontend package is `packages/smart_pid_web`.
- **Font budget:** combined raw `woff2` ≤ 160 KB (163840 bytes), enforced by `src/theme/fonts.test.ts` and `scripts/check-bundle.mjs`. Current total is 112 244 bytes across three files, leaving 51 596 bytes of headroom.
- **No CDN font imports.** The product can be deployed on an isolated plant network. Every face is self-hosted under `src/assets/fonts/`.

---

## File Structure

**Created:**

| File | Responsibility |
|---|---|
| `packages/smart_pid_web/src/assets/fonts/orbitron-latin-var.woff2` | Orbitron variable (wght 400–900), latin subset — the `neon` display face |
| `packages/smart_pid_web/src/assets/fonts/OFL-Orbitron.txt` | SIL OFL 1.1 licence text, a legal requirement of redistributing the face |
| `packages/smart_pid_web/src/theme/useGlowTrace.ts` | One hook: "does `--glow-trace` resolve non-zero right now?" — replaces two `theme === 'phosphor'` literals |
| `packages/smart_pid_web/src/theme/useGlowTrace.test.tsx` | Behaviour test for that hook |
| `packages/smart_pid_web/src/theme/glow.test.ts` | CSS-text gate: the glow tokens reach exactly the four intended surfaces and no static chrome |
| `packages/smart_pid_web/e2e/themes.spec.ts-snapshots/dashboard-neon-{320,768,1024,1440}-linux.png` | The four new visual baselines |

**Modified:**

| File | Change |
|---|---|
| `src/theme/contract.ts` | `THEME_IDS` gains `'neon'`; `CONTRACT_TOKENS` gains the four glow tokens (44 → 48) |
| `src/theme/themes.css` | Glow tokens and `--font-display` added to the three existing blocks; new `[data-theme="neon"]` block |
| `src/theme/tokens.css` | `--font-display` removed from `:root` |
| `src/theme/ThemeProvider.tsx` | `THEMES` gains `{ id: 'neon', label: 'Neon' }`; `DEFAULT_THEME` becomes `'neon'` |
| `src/theme/themeContrast.ts` | `GateThemeId` gains `'neon'`; mirrored neon palette |
| `src/theme/themeContrast.test.ts` | Gate theme list gains `neon`. No floor change |
| `src/theme/isa101Mapping.test.ts` | Type-token exception list, `ISA101_EXPECTED`, `MAPPING`, and the four-block vocabulary assertion |
| `src/theme/tokenResolve.test.ts` | Contract size + `--glow-trace` px-unit assertions |
| `src/theme/fonts.test.ts` | Fourth `woff2`, fourth `font-display: swap`, fourth preload, OFL file |
| `src/theme/ThemeProvider.test.tsx` | Four-theme registry, `neon` default, pre-paint `valid` array |
| `src/assets/fonts/fonts.css` | Fourth `@font-face` |
| `src/assets/fonts/README.md` | Orbitron provenance row + regeneration commands |
| `index.html` | Static `data-theme`, pre-paint `valid` array and fallback, Orbitron preload |
| `src/index.css` | Four glow rules in `@layer components` |
| `src/components/Badge.tsx` / `Badge.test.tsx` | `badge-glow` on the three severity tones |
| `src/components/Button.tsx` / `Button.test.tsx` | `btn-primary` hook class on the primary variant |
| `src/features/dashboard/TrendPanel.tsx` / `TrendPanel.test.tsx` | Token-driven glow |
| `src/features/simulator/TwinTrend.tsx` | Token-driven glow |
| `src/components/Trend.tsx` | Stale prop docs naming the deleted `theme === 'phosphor'` rule |
| `src/App.test.tsx` | Default `data-theme` is `neon` |
| `src/app/AppShell.test.tsx` | Four `menuitemradio` entries |
| `e2e/themes.spec.ts` | Four-theme matrix, token-driven halo test, new baselines |
| `e2e/user-role.spec.ts` | Four `menuitemradio` entries |
| `TEST_E2E.md` (repo root) | E2E-045 and E2E-046 re-specified |

---

## Spec discrepancies

Recorded rather than silently deviated from. Each is a fact about the codebase that §10 did not account for; none changes the design.

1. **§10.5's `none` off-value for `--glow-alarm`, `--glow-focus` and `--glow-accent` is not implementable as written.** The CSS grammar for `box-shadow` is `none | <shadow>#` — `none` is legal only as the *sole* value, so `box-shadow: inset 3px 0 0 0 currentColor, none` is an invalid declaration, and `--tw-shadow: none` makes Tailwind's composed `box-shadow: …, var(--tw-shadow)` invalid at computed-value time, which would **delete the focus ring** in Recorder, Phosphor and ISA-101. Verified against the installed Tailwind (v4.3.3): `.ring-2` emits `box-shadow: var(--tw-inset-shadow), var(--tw-inset-ring-shadow), var(--tw-ring-offset-shadow), var(--tw-ring-shadow), var(--tw-shadow)` and registers `@property --tw-shadow { syntax: "*"; inherits: false; initial-value: 0 0 #0000 }`. This plan therefore uses **`0 0 #0000`** — Tailwind's own "no shadow" sentinel, a valid `<shadow>` that renders nothing — as the off-value in the three non-neon themes. `--glow-trace` is unaffected: it is a length, and `0px` is what §10.5 already specifies.
2. **§10.7 and §11.1 omit `src/app/AppShell.test.tsx:171-176` and `:202`.** Both assert the theme `menuitemradio` list/length; a fourth theme breaks them. Covered in Task 4. Coordinated with the sibling corrections plan, which deletes the command-palette tests in the same file but leaves these two assertions alone.
3. **§10.7 and §11.1 omit `e2e/user-role.spec.ts:165`.** §10.7 row 14 names only `:185` (the admin count), but `:165` asserts the *user* menu's exact labels `['Recorder', 'Phosphor', 'ISA-101']` and breaks identically. Covered in Task 10.
4. **§10.7 rows 7 and 8 understate the `isa101Mapping.test.ts` work.** The assertion at `:192-200` computes `CONTRACT_TOKENS.filter(t => !covered.has(t) && !typeTokens.includes(t))` and expects `[]`, so every new contract token must also enter `ISA101_EXPECTED`; and `:213-215` requires `Object.keys(MAPPING)` to equal `Object.keys(ISA101_EXPECTED)`, so each must also enter `MAPPING` as `DERIVED`. `:254-262` additionally needs a fourth `names[3]` equality assertion. Covered in Tasks 1, 2 and 4.
5. **§10.1 says the gate runs "over every palette in `GateThemeId`" and §10.3 says the palette was "checked against the 43 assertions `themeContrast.test.ts` actually makes".** Both are accurate, but note that `GateThemeId` is `'recorder' | 'phosphor'` today — **`isa101` is not gated**. `neon` joins a two-theme gate, making it three. Independently re-verified while writing this plan: all 43 assertions pass for the §10.3 palette, tightest margins `--alarm-crit` vs `--alarm-crit-bg` at 4.72:1 (floor 3.0), `--rule-strong` on `--surface` at 3.23:1 (floor 3.0), `--alarm-crit` as text on `--surface` at 5.15:1 (floor 4.5).
6. **§12 step 11 says "the four affected `TEST_E2E.md` procedures" while §11.3 enumerates six** (E2E-006, 036, 049, 045, 046, plus E2E-015/043 evidence recapture). This plan re-runs the two it owns, E2E-045 and E2E-046. The other four belong to the sibling corrections plan.

---

### Task 1: The four glow tokens

**Files:**
- Modify: `packages/smart_pid_web/src/theme/contract.ts:8-34`
- Modify: `packages/smart_pid_web/src/theme/themes.css:8-28` (recorder), `:30-51` (phosphor), `:61-82` (isa101)
- Modify: `packages/smart_pid_web/src/theme/isa101Mapping.test.ts:66-118` (`MAPPING`), `:121-163` (`ISA101_EXPECTED`)
- Test: `packages/smart_pid_web/src/theme/tokenResolve.test.ts`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `CONTRACT_TOKENS` is a `readonly string[]` of length **48** exported from `src/theme/contract.ts`, containing the four new names `'--glow-alarm'`, `'--glow-focus'`, `'--glow-accent'`, `'--glow-trace'`. All four resolve non-empty under `[data-theme="recorder"]`, `[data-theme="phosphor"]` and `[data-theme="isa101"]`. `--glow-trace` resolves to a CSS length string (`'4px'` under phosphor, `'0px'` under recorder and isa101) so that `Number.parseFloat` reads it, matching the `--trend-*-width` convention. `--glow-alarm`, `--glow-focus` and `--glow-accent` resolve to a valid `<shadow>` (`'0 0 #0000'` in all three existing themes) so they can be concatenated into a comma-separated `box-shadow` list without invalidating it.

- [ ] **Step 1: Write the failing contract-size test**

Append these two cases inside the existing `describe('§6.4 token contract resolves under every [data-theme]', …)` block in `packages/smart_pid_web/src/theme/tokenResolve.test.ts`, immediately after the `trend widths carry px units consumable by parseFloat (uplotTheme contract)` case:

```ts
  it('the contract holds 48 tokens — 41 palette + 3 type + the four §10.5 glow tokens', () => {
    expect(CONTRACT_TOKENS).toHaveLength(48);
    for (const token of ['--glow-alarm', '--glow-focus', '--glow-accent', '--glow-trace']) {
      expect(CONTRACT_TOKENS, token).toContain(token);
    }
  });

  it('--glow-trace carries px so parseFloat reads it (the halo is "token non-zero")', () => {
    document.documentElement.setAttribute('data-theme', 'phosphor');
    expect(resolved('--glow-trace')).toBe('4px');
    expect(Number.parseFloat(resolved('--glow-trace'))).toBe(4);
    document.documentElement.setAttribute('data-theme', 'recorder');
    expect(Number.parseFloat(resolved('--glow-trace'))).toBe(0);
    document.documentElement.setAttribute('data-theme', 'isa101');
    expect(Number.parseFloat(resolved('--glow-trace'))).toBe(0);
  });

  it('the bloom tokens are valid <shadow> values, never the uncomposable `none`', () => {
    for (const id of ['recorder', 'phosphor', 'isa101']) {
      document.documentElement.setAttribute('data-theme', id);
      for (const token of ['--glow-alarm', '--glow-focus', '--glow-accent']) {
        expect(resolved(token), `${id} ${token}`).toBe('0 0 #0000');
      }
    }
  });
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd packages/smart_pid_web && npx vitest run src/theme/tokenResolve.test.ts`
Expected: FAIL — `expected [ '--bg', '--surface', … ] to have a length of 48 but got 44`, plus `expected '' to be '4px'` and `expected '' to be '0 0 #0000'`.

- [ ] **Step 3: Add the four tokens to the contract**

In `packages/smart_pid_web/src/theme/contract.ts`, replace the `// Bar` and `// Type` trailer of `CONTRACT_TOKENS` (lines 32-34, ending `] as const;`) with:

```ts
  // Bar
  '--bar-track', '--bar-fill', '--bar-marker',
  // Glow (§10.5) — the salience channel. Bloom is reserved for alarms, focus,
  // the PV trace and primary-button hover; steady state never blooms. The three
  // shadow tokens are `0 0 #0000` (a valid no-op <shadow>) outside neon, NOT
  // `none`: `none` cannot appear inside a comma-separated box-shadow list and
  // would invalidate Tailwind's composed ring.
  '--glow-alarm', '--glow-focus', '--glow-accent', '--glow-trace',
  // Type
  '--font-display', '--font-ui', '--font-data',
] as const;
```

- [ ] **Step 4: Declare the tokens in the three existing themes**

In `packages/smart_pid_web/src/theme/themes.css`, add one line before the closing `}` of `[data-theme="recorder"]` (after `--bar-track: #EEF1F5;  --bar-fill: #5A6875;  --bar-marker: #16202B;`):

```css
  --glow-alarm: 0 0 #0000;  --glow-focus: 0 0 #0000;  --glow-accent: 0 0 #0000;
  --glow-trace: 0px;        /* §10.5 no halo on paper */
```

Add before the closing `}` of `[data-theme="phosphor"]` (after `--bar-track: #0E141C;  --bar-fill: #5E7080;  --bar-marker: #8FB6D6;`):

```css
  --glow-alarm: 0 0 #0000;  --glow-focus: 0 0 #0000;  --glow-accent: 0 0 #0000;
  --glow-trace: 4px;        /* §10.5 the CRT halo, formerly `theme === 'phosphor'` */
```

Add before the closing `}` of `[data-theme="isa101"]` (after `--bar-track: #252526;  --bar-fill: #9A9A9A;  --bar-marker: #CCCCCC;`):

```css
  --glow-alarm: 0 0 #0000;  --glow-focus: 0 0 #0000;  --glow-accent: 0 0 #0000;
  --glow-trace: 0px;        /* §10.5 ISA-101 chrome does not bloom */
```

- [ ] **Step 5: Teach the ISA-101 mapping gate about the four new names**

`isa101Mapping.test.ts:192-200` asserts that every `CONTRACT_TOKENS` entry except the type tokens appears in `ISA101_EXPECTED`, and `:213-215` asserts `Object.keys(MAPPING)` equals `Object.keys(ISA101_EXPECTED)`. Both must gain the four names.

In `packages/smart_pid_web/src/theme/isa101Mapping.test.ts`, replace the `// Bar` trailer of `MAPPING` (lines 114-118) with:

```ts
  // Bar
  '--bar-track': '--bar-track',
  '--bar-fill': '--bar-fill',
  '--bar-marker': '--bar-marker',
  // Glow — new in the §10.5 contract; ISA-101 chrome never blooms.
  '--glow-alarm': DERIVED,
  '--glow-focus': DERIVED,
  '--glow-accent': DERIVED,
  '--glow-trace': DERIVED,
};
```

Replace the closing three lines of `ISA101_EXPECTED` (lines 160-163) with:

```ts
  '--bar-track': '#252526',
  '--bar-fill': '#9A9A9A',
  '--bar-marker': '#CCCCCC',
  '--glow-alarm': '0 0 #0000',
  '--glow-focus': '0 0 #0000',
  '--glow-accent': '0 0 #0000',
  '--glow-trace': '0px',
};
```

- [ ] **Step 6: Run the theme suite to verify it passes**

Run: `cd packages/smart_pid_web && npx vitest run src/theme`
Expected: PASS — all files in `src/theme` green, including `tokenResolve.test.ts` (contract length 48), `isa101Mapping.test.ts` (all four blocks still declare an identical vocabulary) and `themeContrast.test.ts` (untouched).

- [ ] **Step 7: Run the full unit suite**

Run: `cd packages/smart_pid_web && npm run test`
Expected: PASS — no regression outside `src/theme`.

- [ ] **Step 8: Commit**

```bash
git add packages/smart_pid_web/src/theme/contract.ts packages/smart_pid_web/src/theme/themes.css packages/smart_pid_web/src/theme/isa101Mapping.test.ts packages/smart_pid_web/src/theme/tokenResolve.test.ts
git commit -m "feat(theme): add the four glow tokens to the token contract"
```

---

### Task 2: `--font-display` becomes per-theme

**Files:**
- Modify: `packages/smart_pid_web/src/theme/tokens.css:9-10`
- Modify: `packages/smart_pid_web/src/theme/themes.css` (all three `[data-theme]` blocks)
- Modify: `packages/smart_pid_web/src/theme/isa101Mapping.test.ts:66-118` (`MAPPING`), `:121-163` (`ISA101_EXPECTED`), `:193`
- Test: `packages/smart_pid_web/src/theme/tokenResolve.test.ts`, `packages/smart_pid_web/src/theme/isa101Mapping.test.ts`

**Interfaces:**
- Consumes: Task 1's 48-entry `CONTRACT_TOKENS`.
- Produces: `--font-display` is no longer declared in `tokens.css :root`. Every `[data-theme]` block declares it. In the three existing themes its value is the verbatim Archivo stack `'Archivo Variable', system-ui, -apple-system, 'Segoe UI', sans-serif`. `--font-ui` and `--font-data` stay in `:root` and are identical in every theme — the numeric face must never vary. `isa101Mapping.test.ts`'s `typeTokens` exception list is exactly `['--font-ui', '--font-data']`.

- [ ] **Step 1: Write the failing test**

Add this case inside the existing `describe('§6.4 token contract resolves under every [data-theme]', …)` in `packages/smart_pid_web/src/theme/tokenResolve.test.ts`, after the case added in Task 1:

```ts
  it('--font-display is per-theme while --font-ui and --font-data stay global', () => {
    const tokensCss = readFileSync(resolve(process.cwd(), 'src/theme/tokens.css'), 'utf8');
    expect(tokensCss).not.toMatch(/--font-display\s*:/);
    expect(tokensCss).toMatch(/--font-ui\s*:/);
    expect(tokensCss).toMatch(/--font-data\s*:/);

    const archivo = "'Archivo Variable', system-ui, -apple-system, 'Segoe UI', sans-serif";
    for (const id of ['recorder', 'phosphor', 'isa101']) {
      document.documentElement.setAttribute('data-theme', id);
      expect(resolved('--font-display'), id).toBe(archivo);
    }
  });
```

`readFileSync` and `resolve` are already imported at the top of that file.

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd packages/smart_pid_web && npx vitest run src/theme/tokenResolve.test.ts`
Expected: FAIL — `expected '/*\n * Theme-agnostic tokens…' not to match /--font-display\s*:/`, because `--font-display` is still declared in `tokens.css :root`.

- [ ] **Step 3: Remove `--font-display` from `:root`**

In `packages/smart_pid_web/src/theme/tokens.css`, replace lines 9-10:

```css
  /* Type faces (§6.2). --font-display is Archivo used at wdth 125 via .type-display. */
  --font-display: 'Archivo Variable', system-ui, -apple-system, 'Segoe UI', sans-serif;
```

with:

```css
  /* Type faces (§6.2). --font-display is PER-THEME (§10.6) and lives in
   * themes.css: numerals and body text are identical in all four themes, the
   * display face is not. Recorder/Phosphor/ISA-101 declare Archivo at wdth 125
   * via .type-display; neon declares Orbitron. */
```

- [ ] **Step 4: Declare `--font-display` in the three theme blocks**

In `packages/smart_pid_web/src/theme/themes.css`, add this identical line to each of `[data-theme="recorder"]`, `[data-theme="phosphor"]` and `[data-theme="isa101"]`, immediately after the `--glow-trace:` line added in Task 1:

```css
  --font-display: 'Archivo Variable', system-ui, -apple-system, 'Segoe UI', sans-serif;
```

- [ ] **Step 5: Narrow the ISA-101 type-token exception list**

In `packages/smart_pid_web/src/theme/isa101Mapping.test.ts`, replace line 193:

```ts
    const typeTokens = ['--font-display', '--font-ui', '--font-data'];
```

with:

```ts
    // §10.6: --font-display moved into the [data-theme] blocks, so ISA-101 now
    // pins it like any other per-theme value. Only --font-ui / --font-data
    // remain in :root and stay excepted.
    const typeTokens = ['--font-ui', '--font-data'];
```

Add `'--font-display'` to `MAPPING`, immediately after the `'--glow-trace': DERIVED,` line added in Task 1:

```ts
  // Type — per-theme since §10.6; ISA-101 keeps the Archivo stack.
  '--font-display': DERIVED,
```

Add the matching entry to `ISA101_EXPECTED`, immediately after the `'--glow-trace': '0px',` line added in Task 1:

```ts
  '--font-display': "'Archivo Variable', system-ui, -apple-system, 'Segoe UI', sans-serif",
```

- [ ] **Step 6: Run the theme suite to verify it passes**

Run: `cd packages/smart_pid_web && npx vitest run src/theme`
Expected: PASS. In particular `isa101Mapping.test.ts` → `--font-display resolves to 'Archivo Variable', system-ui, -apple-system, 'Segoe UI', sans-serif` passes and `covers every §6.4 token (type tokens excepted — they live in :root)` still reports `uncovered === []`.

- [ ] **Step 7: Run the full unit suite**

Run: `cd packages/smart_pid_web && npm run test`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add packages/smart_pid_web/src/theme/tokens.css packages/smart_pid_web/src/theme/themes.css packages/smart_pid_web/src/theme/isa101Mapping.test.ts packages/smart_pid_web/src/theme/tokenResolve.test.ts
git commit -m "refactor(theme): move --font-display out of :root into every [data-theme] block"
```

---

### Task 3: Vendor Orbitron

**Files:**
- Create: `packages/smart_pid_web/src/assets/fonts/orbitron-latin-var.woff2`
- Create: `packages/smart_pid_web/src/assets/fonts/OFL-Orbitron.txt`
- Modify: `packages/smart_pid_web/src/assets/fonts/fonts.css` (append a fourth `@font-face`)
- Modify: `packages/smart_pid_web/src/assets/fonts/README.md`
- Modify: `packages/smart_pid_web/index.html:7-9` (preload block)
- Test: `packages/smart_pid_web/src/theme/fonts.test.ts:6,20-27,30-40`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: the CSS family name **`'Orbitron Variable'`**, weight range `400 900`, `font-display: swap`, served from `./orbitron-latin-var.woff2` and preloaded from `index.html` at `/src/assets/fonts/orbitron-latin-var.woff2`. Task 4 references exactly this family string in the `neon` `--font-display` stack.

- [ ] **Step 1: Write the failing test**

In `packages/smart_pid_web/src/theme/fonts.test.ts`, replace line 6:

```ts
const FILES = ['archivo-latin-var.woff2', 'geist-mono-latin-400.woff2', 'geist-mono-latin-500.woff2'];
```

with:

```ts
const FILES = [
  'archivo-latin-var.woff2',
  'geist-mono-latin-400.woff2',
  'geist-mono-latin-500.woff2',
  'orbitron-latin-var.woff2',
];
```

Replace the whole `it('ships the three committed woff2 files within the 160 KB combined budget', …)` case (lines 10-19) with:

```ts
  it('ships the four committed woff2 files within the 160 KB combined budget', () => {
    let total = 0;
    for (const f of FILES) {
      const size = statSync(resolve(fontsDir, f)).size;
      expect(size, f).toBeGreaterThan(0);
      total += size;
    }
    expect(total, `combined ${Math.round(total / 1024)} KB`).toBeLessThanOrEqual(FONT_BUDGET_BYTES);
  });

  it('commits the SIL OFL 1.1 licence beside the Orbitron file (§10.6, legal requirement)', () => {
    const licence = readFileSync(resolve(fontsDir, 'OFL-Orbitron.txt'), 'utf8');
    expect(licence).toContain('SIL OPEN FONT LICENSE Version 1.1');
    expect(licence).toContain('Orbitron');
  });
```

Replace the whole `it('fonts.css declares swap-display faces matching the token stacks', …)` case (lines 21-28) with:

```ts
  it('fonts.css declares swap-display faces matching the token stacks', () => {
    const css = readFileSync(resolve(fontsDir, 'fonts.css'), 'utf8');
    expect(css).toMatch(/font-family:\s*'Archivo Variable'/);
    expect(css).toMatch(/font-stretch:\s*62\.5%\s+125%/);
    expect(css).toMatch(/font-weight:\s*100\s+900/);
    expect((css.match(/font-family:\s*'Geist Mono'/g) ?? []).length).toBe(2);
    // §10.6 display face for neon. wght only — Orbitron has no width axis.
    expect(css).toMatch(/font-family:\s*'Orbitron Variable'/);
    expect(css).toMatch(/font-weight:\s*400\s+900/);
    expect((css.match(/font-display:\s*swap/g) ?? []).length).toBe(4);
  });
```

Replace the whole `it('index.css imports fonts.css and index.html preloads all three files', …)` case (lines 30-40) with:

```ts
  it('index.css imports fonts.css and index.html preloads all four files', () => {
    const indexCss = readFileSync(resolve(root, 'src/index.css'), 'utf8');
    expect(indexCss).toMatch(/@import\s+['"]\.\/assets\/fonts\/fonts\.css['"]/);
    const html = readFileSync(resolve(root, 'index.html'), 'utf8');
    for (const f of FILES) {
      expect(html, f).toContain(`/src/assets/fonts/${f}`);
    }
    expect((html.match(/rel="preload"\s+href="\/src\/assets\/fonts\//g) ?? []).length).toBe(4);
    expect(html).toMatch(/as="font"\s+type="font\/woff2"\s+crossorigin/);
  });
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd packages/smart_pid_web && npx vitest run src/theme/fonts.test.ts`
Expected: FAIL — `ENOENT: no such file or directory, stat '…/src/assets/fonts/orbitron-latin-var.woff2'`.

- [ ] **Step 3: Download the upstream face and its licence**

Both URLs were verified while writing this plan: the TTF returns HTTP 200 / 38 576 bytes, the licence HTTP 200 / 4 426 bytes.

```bash
cd packages/smart_pid_web/src/assets/fonts
node -e "const fs=require('fs');fetch('https://raw.githubusercontent.com/google/fonts/main/ofl/orbitron/Orbitron%5Bwght%5D.ttf').then(r=>r.arrayBuffer()).then(b=>fs.writeFileSync('/tmp/Orbitron-var.ttf',Buffer.from(b)))"
node -e "const fs=require('fs');fetch('https://raw.githubusercontent.com/google/fonts/main/ofl/orbitron/OFL.txt').then(r=>r.arrayBuffer()).then(b=>fs.writeFileSync('OFL-Orbitron.txt',Buffer.from(b)))"
```

(If your harness permits `curl`, the equivalent is `curl -L -o /tmp/Orbitron-var.ttf 'https://raw.githubusercontent.com/google/fonts/main/ofl/orbitron/Orbitron%5Bwght%5D.ttf'`. Some harnesses block inline HTTP in the shell — the `node` form above always works.)

- [ ] **Step 4: Subset to latin, exactly as the Archivo file was produced**

Same unicode range and flags as the recorded Archivo command in `src/assets/fonts/README.md`, so the two faces cover identical pt-BR text:

```bash
cd packages/smart_pid_web/src/assets/fonts
uvx --from 'fonttools[woff]' pyftsubset /tmp/Orbitron-var.ttf \
  --unicodes='U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+2074,U+20AC,U+2122,U+2212' \
  --layout-features='*' --flavor=woff2 --output-file=orbitron-latin-var.woff2
```

- [ ] **Step 5: Confirm the font budget still has headroom**

```bash
cd packages/smart_pid_web/src/assets/fonts && wc -c *.woff2 | tail -1
```

Expected: a total under `163840`. The three existing files are 112 244 bytes, so Orbitron must come in under 51 596 bytes; the full unsubset TTF is only 38 576 bytes, so the latin `woff2` subset lands far below that. If the total ever exceeds the budget, narrow `--layout-features` to `--layout-features='kern,liga'` and re-run — do **not** raise `FONT_BUDGET_BYTES`.

- [ ] **Step 6: Declare the `@font-face`**

Append to `packages/smart_pid_web/src/assets/fonts/fonts.css`:

```css
/* §10.6 display face for the neon theme. wght only: Orbitron has no width
 * axis, so .type-display's `font-stretch: 125%` is inert under neon — left as
 * a harmless no-op rather than paying for a token that says "no width axis". */
@font-face {
  font-family: 'Orbitron Variable';
  src: url('./orbitron-latin-var.woff2') format('woff2-variations');
  font-weight: 400 900;
  font-style: normal;
  font-display: swap;
}
```

- [ ] **Step 7: Preload it**

In `packages/smart_pid_web/index.html`, add a fourth line immediately after line 9 (`<link rel="preload" href="/src/assets/fonts/geist-mono-latin-500.woff2" …>`):

```html
    <link rel="preload" href="/src/assets/fonts/orbitron-latin-var.woff2" as="font" type="font/woff2" crossorigin />
```

- [ ] **Step 8: Record the provenance**

In `packages/smart_pid_web/src/assets/fonts/README.md`, add this row to the table, after the `geist-mono-latin-500.woff2` row:

```markdown
| orbitron-latin-var.woff2 | Orbitron Variable | wght 400–900 · Latin | OFL 1.1 (`OFL-Orbitron.txt`) | github.com/google/fonts `ofl/orbitron/Orbitron[wght].ttf` |
```

and append this block at the end of the file:

```markdown
Orbitron regeneration (§10.6 — the `neon` display face; same subset range as Archivo):

    node -e "const fs=require('fs');fetch('https://raw.githubusercontent.com/google/fonts/main/ofl/orbitron/Orbitron%5Bwght%5D.ttf').then(r=>r.arrayBuffer()).then(b=>fs.writeFileSync('/tmp/Orbitron-var.ttf',Buffer.from(b)))"
    uvx --from 'fonttools[woff]' pyftsubset /tmp/Orbitron-var.ttf \
      --unicodes='U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+2074,U+20AC,U+2122,U+2212' \
      --layout-features='*' --flavor=woff2 --output-file=orbitron-latin-var.woff2

The SIL OFL 1.1 text is committed as `OFL-Orbitron.txt`: redistributing the face
in a commercial product requires shipping the licence beside it.
```

- [ ] **Step 9: Run the fonts gate to verify it passes**

Run: `cd packages/smart_pid_web && npx vitest run src/theme/fonts.test.ts`
Expected: PASS — three cases green, including `combined <N> KB` under 160.

- [ ] **Step 10: Run the full unit suite**

Run: `cd packages/smart_pid_web && npm run test`
Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add packages/smart_pid_web/src/assets/fonts/orbitron-latin-var.woff2 packages/smart_pid_web/src/assets/fonts/OFL-Orbitron.txt packages/smart_pid_web/src/assets/fonts/fonts.css packages/smart_pid_web/src/assets/fonts/README.md packages/smart_pid_web/index.html packages/smart_pid_web/src/theme/fonts.test.ts
git commit -m "feat(fonts): vendor Orbitron Variable latin subset with its OFL licence"
```

---

### Task 4: The `[data-theme="neon"]` block and theme registration

**Files:**
- Modify: `packages/smart_pid_web/src/theme/themes.css` (append the new block)
- Modify: `packages/smart_pid_web/src/theme/contract.ts:5`
- Modify: `packages/smart_pid_web/src/theme/ThemeProvider.tsx:6-10`
- Modify: `packages/smart_pid_web/src/theme/isa101Mapping.test.ts:254-262`
- Modify: `packages/smart_pid_web/src/theme/ThemeProvider.test.tsx:31-35,49-51`
- Modify: `packages/smart_pid_web/src/app/AppShell.test.tsx:170-176,202`

**Interfaces:**
- Consumes: Task 1's four glow tokens, Task 2's per-theme `--font-display`, Task 3's `'Orbitron Variable'` family.
- Produces: `THEME_IDS = ['recorder', 'phosphor', 'isa101', 'neon'] as const` and its derived `ContractThemeId`; `THEMES` gains `{ id: 'neon', label: 'Neon' }` as the fourth entry. `DEFAULT_THEME` is still `'recorder'` after this task — Task 6 flips it. The `[data-theme="neon"]` block declares **46** custom properties: the 41 palette tokens, the 4 glow tokens and `--font-display`.

> **Playwright goes red at this task and stays red until Task 10.** `e2e/user-role.spec.ts:165` and `:185` assert a three-theme menu. That is expected and is fixed in Task 10; Vitest stays green throughout.

- [ ] **Step 1: Write the failing test**

Replace the `it('all three themes declare the identical token vocabulary (single §6.4 set)', …)` case in `packages/smart_pid_web/src/theme/isa101Mapping.test.ts` (lines 254-262) with:

```ts
  it('all four themes declare the identical token vocabulary (single §6.4 set)', () => {
    const blocks = [...themesCss.matchAll(/\[data-theme="([a-z0-9-]+)"\]\s*\{([\s\S]*?)\n\}/g)];
    expect(blocks.map((b) => b[1])).toEqual(['recorder', 'phosphor', 'isa101', 'neon']);
    const names = blocks.map(
      (b) => [...b[2].matchAll(/(--[a-z0-9-]+)\s*:/g)].map((m) => m[1]).sort(),
    );
    expect(names[0]).toHaveLength(46); // 41 palette + 4 glow + --font-display
    expect(names[1]).toEqual(names[0]);
    expect(names[2]).toEqual(names[0]);
    expect(names[3]).toEqual(names[0]);
  });
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd packages/smart_pid_web && npx vitest run src/theme/isa101Mapping.test.ts`
Expected: FAIL — `expected [ 'recorder', 'phosphor', 'isa101' ] to deeply equal [ 'recorder', 'phosphor', 'isa101', 'neon' ]`.

- [ ] **Step 3: Append the neon block**

Append to `packages/smart_pid_web/src/theme/themes.css`. Every hex is verbatim from spec §10.3; the contrast figures in the comments were recomputed against the WCAG 2.x relative-luminance formula while writing this plan.

```css

/*
 * Neon (§10) — the fourth theme, and the default from §10.2. Derived from the
 * ui-ux-pro-max skill, deliberately DISCARDING the ISA-101 premise recorded at
 * contract.ts:22 ("green never means ok"): --state-running is neon green here.
 * That is safe only because recorder and isa101 stay in the picker untouched,
 * so a customer who needs ISA-101 conformance still has a conforming surface.
 *
 * WCAG does NOT fall with ISA-101. Every pair below passes all 43 assertions of
 * themeContrast.test.ts; tightest margins are --alarm-crit on --alarm-crit-bg
 * (4.72:1, floor 3.0) and --rule-strong on --surface (3.23:1, floor 3.0).
 *
 * Salience headroom min(alarm chroma) - max(chrome chroma) is -0.056 (§10.4):
 * a running loop is louder than an ADVISORY. Glow (§10.5) is the compensating
 * channel — alarms and focus bloom, steady chrome never does.
 */
[data-theme="neon"] {
  --bg: #07070E;            /* not #000000 — pure black smears on OLED */
  --surface: #101226;
  --surface-sunk: #0A0B18;  /* chart wells, inputs */
  --rule: #1E2038;          /* hairlines, decorative only */
  --rule-strong: #5A60A8;   /* control boundaries — 3.23:1 on surface, 3.42:1 on sunk */
  --text: #E9ECFF;  --text-soft: #A6ADDC;  --text-disabled: #5A5F85;
  --focus-ring: #00E5FF;  --selection: #1B2A5C;  --scrim: rgba(3,3,8,0.72);
  --accent: #00E5FF;  --accent-hover: #66F2FF;  --accent-sunk: #0088A0;
  --accent-soft: #0A2A38;  --on-accent: #04040A;                /* 13.29:1 */
  --alarm-crit: #FF2D6F;  --alarm-crit-bg: #3A0A1C;             /* 5.60:1 on bg */
  --alarm-warn: #FFB020;  --alarm-warn-bg: #3A2600;
  --alarm-adv:  #C77DFF;  --alarm-adv-bg:  #28123E;
  --alarm-log:  #A6ADDC;  --on-alarm: #04040A;                  /* >=5.70:1 on all four fills */
  --state-running: #39FF88;  --state-stopped: #A6ADDC;          /* the discarded premise, made visible */
  --state-error: #FF2D6F;    --state-oos: #4A4E6E;              /* oos is contrast-exempt: faded IS the signal */
  --trace-pv: #00F0FF;  --trace-sp: #B8BEE8;  --trace-co: #FFA630;
  --trend-grid: #1A1C33;  --trend-axis: #5A5F85;  --trend-bg: #07070E;
  --trend-pv-width: 2px;  --trend-sp-width: 1.5px;  --trend-co-width: 1.5px;
  --trend-sp-dash: 4 3;
  --bar-track: #12142A;  --bar-fill: #00E5FF;  --bar-marker: #FFFFFF;
  --glow-alarm: 0 0 12px rgba(255,45,111,0.55);
  --glow-focus: 0 0 10px rgba(0,229,255,0.65);
  --glow-accent: 0 0 14px rgba(0,229,255,0.45);
  --glow-trace: 8px;
  --font-display: 'Orbitron Variable', 'Archivo Variable', system-ui, sans-serif;
}
```

- [ ] **Step 4: Register the id in the contract**

In `packages/smart_pid_web/src/theme/contract.ts`, replace line 5:

```ts
export const THEME_IDS = ['recorder', 'phosphor', 'isa101'] as const;
```

with:

```ts
export const THEME_IDS = ['recorder', 'phosphor', 'isa101', 'neon'] as const;
```

- [ ] **Step 5: Register the theme in the provider**

In `packages/smart_pid_web/src/theme/ThemeProvider.tsx`, replace lines 6-10:

```tsx
export const THEMES: ReadonlyArray<{ id: ThemeId; label: string }> = [
  { id: 'recorder', label: 'Recorder' },
  { id: 'phosphor', label: 'Phosphor' },
  { id: 'isa101', label: 'ISA-101' },
];
```

with:

```tsx
export const THEMES: ReadonlyArray<{ id: ThemeId; label: string }> = [
  { id: 'recorder', label: 'Recorder' },
  { id: 'phosphor', label: 'Phosphor' },
  { id: 'isa101', label: 'ISA-101' },
  // §10.2: the siblings are instruments (paper chart recorder, CRT phosphor).
  // Neon breaks that pattern on purpose — it needs no explanation.
  { id: 'neon', label: 'Neon' },
];
```

- [ ] **Step 6: Update the provider registry test**

In `packages/smart_pid_web/src/theme/ThemeProvider.test.tsx`, replace lines 31-35:

```tsx
describe('theme registry (spec §6.8)', () => {
  it('ships exactly recorder, phosphor, isa101 — recorder default', () => {
    expect(THEMES.map((t) => t.id)).toEqual(['recorder', 'phosphor', 'isa101']);
    expect(DEFAULT_THEME).toBe('recorder');
    expect(STORAGE_KEY).toBe('spid.theme');
  });
});
```

with:

```tsx
describe('theme registry (spec §6.8 + §10.2)', () => {
  it('ships exactly recorder, phosphor, isa101, neon — recorder still default', () => {
    expect(THEMES.map((t) => t.id)).toEqual(['recorder', 'phosphor', 'isa101', 'neon']);
    expect(THEMES.map((t) => t.label)).toEqual(['Recorder', 'Phosphor', 'ISA-101', 'Neon']);
    expect(DEFAULT_THEME).toBe('recorder');
    expect(STORAGE_KEY).toBe('spid.theme');
  });
});
```

Replace line 49:

```tsx
  it.each([['recorder'], ['phosphor'], ['isa101']] as const)('valid %s passes through', (id) => {
```

with:

```tsx
  it.each([['recorder'], ['phosphor'], ['isa101'], ['neon']] as const)(
    'valid %s passes through',
    (id) => {
```

and close that arrow function's call with `},\n  );` — the case body becomes:

```tsx
  it.each([['recorder'], ['phosphor'], ['isa101'], ['neon']] as const)(
    'valid %s passes through',
    (id) => {
      expect(resolveStoredTheme(id)).toBe(id);
    },
  );
```

- [ ] **Step 7: Update the AppShell menu tests**

In `packages/smart_pid_web/src/app/AppShell.test.tsx`, replace lines 171-176 (the `getAllByRole('menuitemradio').map(…)` assertion) with:

> **Re-read the file before anchoring.** The sibling UI-corrections plan deletes the three command-palette cases from the top half of this file (its lines 85-107) and edits lines 46-72, which shifts everything below upward by roughly 23 lines. It never touches the two theme assertions edited here. Find them by content — `getAllByRole('menuitemradio')` — not by the line numbers quoted below.

```tsx
    expect(within(menu).getAllByRole('menuitemradio').map((i) => i.textContent)).toEqual([
      'Recorder',
      'Phosphor',
      'ISA-101',
      'Neon',
    ]);
```

and line 202:

```tsx
    expect(within(menu).getAllByRole('menuitemradio')).toHaveLength(3);
```

with:

```tsx
    expect(within(menu).getAllByRole('menuitemradio')).toHaveLength(4);
```

- [ ] **Step 8: Run the affected tests to verify they pass**

Run: `cd packages/smart_pid_web && npx vitest run src/theme src/app/AppShell.test.tsx`
Expected: PASS — `isa101Mapping.test.ts` reports four blocks with 46 identical names each, `tokenResolve.test.ts` resolves all 48 contract tokens under `neon` too, `AppShell.test.tsx` sees four radio items.

- [ ] **Step 9: Typecheck and run the full unit suite**

Run: `npm --prefix packages/smart_pid_web run typecheck && cd packages/smart_pid_web && npm run test`
Expected: PASS both. `ContractThemeId` now includes `'neon'`, and nothing in the tree switches exhaustively on it.

- [ ] **Step 10: Commit**

```bash
git add packages/smart_pid_web/src/theme/themes.css packages/smart_pid_web/src/theme/contract.ts packages/smart_pid_web/src/theme/ThemeProvider.tsx packages/smart_pid_web/src/theme/ThemeProvider.test.tsx packages/smart_pid_web/src/theme/isa101Mapping.test.ts packages/smart_pid_web/src/app/AppShell.test.tsx
git commit -m "feat(theme): add the neon palette and register it as the fourth theme"
```

---

### Task 5: `neon` joins the WCAG contrast gate

**Files:**
- Modify: `packages/smart_pid_web/src/theme/themeContrast.ts:6`, and append a `neon` entry to `PALETTES` (after the `phosphor` entry that ends at line 102)
- Modify: `packages/smart_pid_web/src/theme/themeContrast.test.ts:7`

**Interfaces:**
- Consumes: Task 4's `[data-theme="neon"]` CSS block — the `mirror stays in sync with themes.css` suite reads the block back out of `themes.css` and asserts every mirrored hex appears on its token there, so the two must agree byte for byte.
- Produces: `GateThemeId = 'recorder' | 'phosphor' | 'neon'` and `PALETTES.neon: ThemePalette` (all 29 fields). No change to `ThemePalette`, `TEXT_FLOOR` or `NONTEXT_FLOOR`.

- [ ] **Step 1: Write the failing test**

In `packages/smart_pid_web/src/theme/themeContrast.test.ts`, replace line 7:

```ts
const THEMES: GateThemeId[] = ['recorder', 'phosphor'];
```

with:

```ts
// §10.1/D10: WCAG is a different standard from ISA-101. The operator dropped the
// ISA-101 doctrine for neon; the accessibility floor does not move with it.
const THEMES: GateThemeId[] = ['recorder', 'phosphor', 'neon'];
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd packages/smart_pid_web && npx vitest run src/theme/themeContrast.test.ts`
Expected: FAIL — TypeScript rejects `'neon'` as a `GateThemeId` (`Type '"neon"' is not assignable to type 'GateThemeId'`), and at runtime every `neon` case throws `TypeError: Cannot read properties of undefined (reading 'text')` because `PALETTES['neon']` does not exist.

- [ ] **Step 3: Widen `GateThemeId`**

In `packages/smart_pid_web/src/theme/themeContrast.ts`, replace line 6:

```ts
export type GateThemeId = 'recorder' | 'phosphor';
```

with:

```ts
export type GateThemeId = 'recorder' | 'phosphor' | 'neon';
```

- [ ] **Step 4: Mirror the neon palette**

In the same file, add this entry to `PALETTES` immediately after the `phosphor` entry's closing `},` and before the object's closing `};`:

```ts
  neon: {
    bg: '#07070E',
    surface: '#101226',
    surfaceSunk: '#0A0B18',
    ruleStrong: '#5A60A8',
    text: '#E9ECFF',
    textSoft: '#A6ADDC',
    focusRing: '#00E5FF',
    selection: '#1B2A5C',
    accent: '#00E5FF',
    accentHover: '#66F2FF',
    onAccent: '#04040A',
    alarmCrit: '#FF2D6F',
    alarmCritBg: '#3A0A1C',
    alarmWarn: '#FFB020',
    alarmWarnBg: '#3A2600',
    alarmAdv: '#C77DFF',
    alarmAdvBg: '#28123E',
    alarmLog: '#A6ADDC',
    onAlarm: '#04040A',
    stateRunning: '#39FF88',
    stateStopped: '#A6ADDC',
    stateError: '#FF2D6F',
    tracePv: '#00F0FF',
    traceSp: '#B8BEE8',
    traceCo: '#FFA630',
    trendBg: '#07070E',
    barTrack: '#12142A',
    barFill: '#00E5FF',
    barMarker: '#FFFFFF',
  },
```

- [ ] **Step 5: Run the gate to verify it passes with no floor changed**

Run: `cd packages/smart_pid_web && npx vitest run src/theme/themeContrast.test.ts`
Expected: PASS — 13 `it.each` cases × 3 themes = 39 tests green. Confirm by reading the diff that `TEXT_FLOOR` is still `4.5`, `NONTEXT_FLOOR` is still `3.0`, and that no `expect(...)` line in the file was edited. The neon numbers, recomputed independently: `--text` on `--bg` 17.12:1, `--text-soft` on `--surface` 8.48:1, `--on-accent` on `--accent` 13.29:1, `--on-alarm` on `--alarm-crit` 5.70:1, `--alarm-crit` as text on `--surface` 5.15:1, `--rule-strong` on `--surface` 3.23:1, `--focus-ring` on `--bg` 13.05:1, `--alarm-crit` on `--alarm-crit-bg` 4.72:1, `--state-running` on `--bg` 15.14:1, `--trace-co` on `--surface-sunk` 10.01:1, `--bar-fill` on `--bar-track` 11.78:1.

- [ ] **Step 6: Verify the mirror-sync suite specifically**

Run: `cd packages/smart_pid_web && npx vitest run src/theme/themeContrast.test.ts -t "every mirrored hex appears on its token in the CSS block"`
Expected: PASS for all three themes. A failure here means a hex in `themeContrast.ts` and the same token in `themes.css` disagree — fix `themeContrast.ts` to match the CSS, never the reverse.

- [ ] **Step 7: Typecheck and run the full unit suite**

Run: `npm --prefix packages/smart_pid_web run typecheck && cd packages/smart_pid_web && npm run test`
Expected: PASS both.

- [ ] **Step 8: Commit**

```bash
git add packages/smart_pid_web/src/theme/themeContrast.ts packages/smart_pid_web/src/theme/themeContrast.test.ts
git commit -m "test(theme): gate neon on WCAG 1.4.3 and 1.4.11 with no floor changes"
```

---

### Task 6: `neon` becomes the default

**Files:**
- Modify: `packages/smart_pid_web/src/theme/ThemeProvider.tsx:12`
- Modify: `packages/smart_pid_web/index.html:2,10-25`
- Modify: `packages/smart_pid_web/src/theme/ThemeProvider.test.tsx:31-37,53-56,59-68,105-112`
- Modify: `packages/smart_pid_web/src/App.test.tsx:33`

**Interfaces:**
- Consumes: Task 4's registered `'neon'` id.
- Produces: `DEFAULT_THEME: ThemeId = 'neon'`. `resolveStoredTheme(null)` and `resolveStoredTheme('banana')` both return `'neon'`. `<html>` carries `data-theme="neon"` statically in `index.html`, and the pre-paint script's `valid` array is `['recorder', 'phosphor', 'isa101', 'neon']` with `'neon'` as its fallback. `LEGACY_THEME_MAP` is **unchanged** — a stored `ocean` still migrates to `recorder`, per §11.3.

- [ ] **Step 1: Write the failing tests**

In `packages/smart_pid_web/src/theme/ThemeProvider.test.tsx`, replace the registry case body (the one edited in Task 4) so `DEFAULT_THEME` is `'neon'`:

```tsx
describe('theme registry (spec §6.8 + §10.2)', () => {
  it('ships exactly recorder, phosphor, isa101, neon — neon default', () => {
    expect(THEMES.map((t) => t.id)).toEqual(['recorder', 'phosphor', 'isa101', 'neon']);
    expect(THEMES.map((t) => t.label)).toEqual(['Recorder', 'Phosphor', 'ISA-101', 'Neon']);
    expect(DEFAULT_THEME).toBe('neon');
    expect(STORAGE_KEY).toBe('spid.theme');
  });
});
```

Replace the `it('unknown and null fall to recorder', …)` case (lines 53-56) with:

```tsx
  it('unknown and null fall to neon (§10.2 default)', () => {
    expect(resolveStoredTheme('banana')).toBe('neon');
    expect(resolveStoredTheme(null)).toBe('neon');
  });
```

Replace the `it('defaults to recorder and sets data-theme on <html>', …)` case (lines 59-68) with:

```tsx
  it('defaults to neon and sets data-theme on <html>', () => {
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    expect(screen.getByTestId('current').textContent).toBe('neon');
    expect(document.documentElement.getAttribute('data-theme')).toBe('neon');
  });
```

Replace the pre-paint sync case (lines 105-112) with:

```tsx
  it('contains every mapping row, the valid-id list and the neon fallback', () => {
    const html = readFileSync(resolve(process.cwd(), 'index.html'), 'utf8');
    for (const [legacy, target] of Object.entries(LEGACY_THEME_MAP)) {
      expect(html).toContain(`'${legacy}': '${target}'`);
    }
    expect(html).toContain(`['recorder', 'phosphor', 'isa101', 'neon']`);
    // The static attribute and the script fallback must agree with DEFAULT_THEME,
    // or a fresh profile flashes one theme and settles on another.
    expect(html).toContain(`<html lang="pt-BR" data-theme="${DEFAULT_THEME}">`);
    expect(html).toContain(`legacy[stored] || '${DEFAULT_THEME}'`);
  });
```

In `packages/smart_pid_web/src/App.test.tsx`, replace line 33:

```tsx
    expect(document.documentElement.getAttribute('data-theme')).toBe('recorder');
```

with:

```tsx
    expect(document.documentElement.getAttribute('data-theme')).toBe('neon');
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd packages/smart_pid_web && npx vitest run src/theme/ThemeProvider.test.tsx src/App.test.tsx`
Expected: FAIL — `expected 'recorder' to be 'neon'` from the registry case, the resolve case, the provider default case and `App.test.tsx`; plus `expected '<!doctype html>…' to contain '['recorder', 'phosphor', 'isa101', 'neon']'`.

- [ ] **Step 3: Flip `DEFAULT_THEME`**

In `packages/smart_pid_web/src/theme/ThemeProvider.tsx`, replace line 12:

```tsx
export const DEFAULT_THEME: ThemeId = 'recorder';
```

with:

```tsx
/** §10.2/D9: a demo must open on the theme the directive asked for. */
export const DEFAULT_THEME: ThemeId = 'neon';
```

- [ ] **Step 4: Flip the static attribute and the pre-paint script**

In `packages/smart_pid_web/index.html`, replace line 2:

```html
<html lang="pt-BR" data-theme="recorder">
```

with:

```html
<html lang="pt-BR" data-theme="neon">
```

and replace the pre-paint `<script>` body (lines 10-25) with:

```html
    <script>
      // Pre-paint theme (§6.8): apply the persisted theme before first paint so a
      // returning Phosphor user never flashes Neon. Mirrors LEGACY_THEME_MAP in
      // src/theme/ThemeProvider.tsx — ThemeProvider.test.tsx enforces the sync,
      // including that this fallback equals DEFAULT_THEME.
      (function () {
        try {
          var stored = localStorage.getItem('spid.theme');
          var legacy = { 'dark-room': 'phosphor', 'md3-dark': 'recorder', 'md3-light': 'recorder', 'ocean': 'recorder' };
          var valid = ['recorder', 'phosphor', 'isa101', 'neon'];
          var theme = valid.indexOf(stored) >= 0 ? stored : legacy[stored] || 'neon';
          document.documentElement.setAttribute('data-theme', theme);
        } catch (e) {
          /* no storage: keep the static neon default */
        }
      })();
    </script>
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd packages/smart_pid_web && npx vitest run src/theme/ThemeProvider.test.tsx src/App.test.tsx`
Expected: PASS — including `migrates a legacy stored value ONCE and writes the migrated value back`, which still expects `ocean → recorder` and must not have been touched.

- [ ] **Step 6: Run the full unit suite**

Run: `cd packages/smart_pid_web && npm run test`
Expected: PASS.

- [ ] **Step 7: Confirm the fresh-profile paint in a real browser**

```bash
cd packages/smart_pid_web && env -u CI npx playwright test e2e/themes.spec.ts -g "persists an explicit phosphor selection across a reload"
```

Expected: PASS. This proves the pre-paint script still round-trips a stored non-default theme after the fallback flip. (The `recorder is the default when nothing is stored` case is knowingly red until Task 10.)

- [ ] **Step 8: Commit**

```bash
git add packages/smart_pid_web/src/theme/ThemeProvider.tsx packages/smart_pid_web/src/theme/ThemeProvider.test.tsx packages/smart_pid_web/index.html packages/smart_pid_web/src/App.test.tsx
git commit -m "feat(theme): make neon the default theme and the pre-paint fallback"
```

---

### Task 7: The halo follows the token, not a theme id

**Files:**
- Create: `packages/smart_pid_web/src/theme/useGlowTrace.ts`
- Create: `packages/smart_pid_web/src/theme/useGlowTrace.test.tsx`
- Modify: `packages/smart_pid_web/src/features/dashboard/TrendPanel.tsx:13,59-65,170`
- Modify: `packages/smart_pid_web/src/features/simulator/TwinTrend.tsx:8,29,73`
- Modify: `packages/smart_pid_web/src/features/dashboard/TrendPanel.test.tsx:82-96`
- Modify: `packages/smart_pid_web/src/components/Trend.tsx:42,83` (stale prop docs only — no behaviour change)

**Interfaces:**
- Consumes: Task 1's `--glow-trace` token, which resolves to `'0px'` (recorder, isa101), `'4px'` (phosphor) or `'8px'` (neon).
- Produces: `export function useGlowTrace(): boolean` from `src/theme/useGlowTrace.ts` — `true` while `Number.parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--glow-trace')) > 0`, re-evaluated whenever `<html data-theme>` changes. `TrendPanel` and `TwinTrend` pass its value to `Trend`'s existing `glow?: boolean` prop. Neither file imports `useTheme` any more, and no source file outside `src/theme/` contains the literal `'phosphor'`.

- [ ] **Step 1: Write the failing hook test**

Create `packages/smart_pid_web/src/theme/useGlowTrace.test.tsx`:

```tsx
import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { useGlowTrace } from './useGlowTrace';

/**
 * jsdom resolves custom properties from a real stylesheet (the same technique
 * tokenResolve.test.ts uses), so this drives the hook exactly the way the
 * browser does: flip <html data-theme> and let the cascade answer.
 */
const TOKENS = `
  [data-theme="recorder"] { --glow-trace: 0px; }
  [data-theme="phosphor"] { --glow-trace: 4px; }
  [data-theme="isa101"]   { --glow-trace: 0px; }
  [data-theme="neon"]     { --glow-trace: 8px; }
`;

let styleEl: HTMLStyleElement | null = null;

function withTokens(): void {
  styleEl = document.createElement('style');
  styleEl.textContent = TOKENS;
  document.head.appendChild(styleEl);
}

async function setTheme(id: string): Promise<void> {
  await act(async () => {
    document.documentElement.setAttribute('data-theme', id);
    // MutationObserver callbacks land on a microtask.
    await Promise.resolve();
  });
}

afterEach(() => {
  styleEl?.remove();
  styleEl = null;
  document.documentElement.removeAttribute('data-theme');
});

describe('useGlowTrace (§10.5 — glow is "the token is non-zero")', () => {
  it('is on wherever --glow-trace is non-zero and off where it is 0px', async () => {
    withTokens();
    document.documentElement.setAttribute('data-theme', 'recorder');
    const { result } = renderHook(() => useGlowTrace());
    expect(result.current).toBe(false);

    await setTheme('phosphor');
    expect(result.current).toBe(true);

    await setTheme('neon');
    expect(result.current).toBe(true);

    await setTheme('isa101');
    expect(result.current).toBe(false);
  });

  it('picks the token up when the attribute arrives after mount', async () => {
    withTokens();
    const { result } = renderHook(() => useGlowTrace());
    expect(result.current).toBe(false);

    await setTheme('neon');
    expect(result.current).toBe(true);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd packages/smart_pid_web && npx vitest run src/theme/useGlowTrace.test.tsx`
Expected: FAIL — `Failed to resolve import "./useGlowTrace" from "src/theme/useGlowTrace.test.tsx"`.

- [ ] **Step 3: Write the hook**

Create `packages/smart_pid_web/src/theme/useGlowTrace.ts`:

```ts
import { useEffect, useState } from 'react';

/**
 * §10.5 / D12 — the PV halo is "the `--glow-trace` token is non-zero", not
 * "the theme is Phosphor". One mechanism serves the existing CRT halo (4px)
 * and the neon one (8px), and no component needs to know a theme id.
 *
 * The token carries `px` so `parseFloat` reads it, matching the
 * `--trend-*-width` convention that `tokenResolve.test.ts` already asserts.
 *
 * The observer mirrors the one in `components/Trend.tsx`: `data-theme` is set
 * by `index.html` before first paint in the browser, but by a ThemeProvider
 * effect in jsdom — which runs AFTER this component's effect — so reading once
 * on mount is not enough.
 */
function readGlowTrace(): boolean {
  const raw = getComputedStyle(document.documentElement).getPropertyValue('--glow-trace');
  return Number.parseFloat(raw) > 0;
}

export function useGlowTrace(): boolean {
  const [on, setOn] = useState(readGlowTrace);

  useEffect(() => {
    const read = () => setOn(readGlowTrace());
    read();
    const obs = new MutationObserver(read);
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => obs.disconnect();
  }, []);

  return on;
}
```

- [ ] **Step 4: Run the hook test to verify it passes**

Run: `cd packages/smart_pid_web && npx vitest run src/theme/useGlowTrace.test.tsx`
Expected: PASS — both cases.

- [ ] **Step 5: Rewrite the TrendPanel glow test**

In `packages/smart_pid_web/src/features/dashboard/TrendPanel.test.tsx`, replace the `it('turns the phosphor halo on with the theme and off otherwise', …)` case (lines 82-96) with:

```tsx
  it('turns the halo on from --glow-trace, never from a theme id', async () => {
    const style = document.createElement('style');
    style.textContent =
      '[data-theme="recorder"] { --glow-trace: 0px; } [data-theme="neon"] { --glow-trace: 8px; }';
    document.head.appendChild(style);

    localStorage.setItem('spid.theme', 'recorder');
    const recorder = renderPanel();
    expect(recorder.getByRole('img', { name: 'Tendência PIC-005' })).toHaveAttribute(
      'data-glow',
      'off',
    );
    recorder.unmount();

    localStorage.setItem('spid.theme', 'neon');
    renderPanel();
    await waitFor(() =>
      expect(screen.getByRole('img', { name: 'Tendência PIC-005' })).toHaveAttribute(
        'data-glow',
        'on',
      ),
    );

    style.remove();
  });

  it('names no theme in its source — the halo is token-driven (§10.5/D12)', () => {
    const code = (file: string): string =>
      readFileSync(resolve(here, file), 'utf8')
        .replace(/\/\*[\s\S]*?\*\//g, '')
        .replace(/(^|[^:])\/\/[^\n]*/g, '$1');
    expect(code('TrendPanel.tsx')).not.toContain("'phosphor'");
    expect(code('../simulator/TwinTrend.tsx')).not.toContain("'phosphor'");
  });
```

Add `waitFor` to the `@testing-library/react` import on line 4 so it reads:

```tsx
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
```

- [ ] **Step 6: Run the TrendPanel test to verify it fails**

Run: `cd packages/smart_pid_web && npx vitest run src/features/dashboard/TrendPanel.test.tsx`
Expected: FAIL — `expected '…glow={theme === '"'"'phosphor'"'"'}…' not to contain "'phosphor'"`, and the halo case times out on `data-glow` staying `off` under `neon` because `TrendPanel` still compares theme ids.

- [ ] **Step 7: Switch TrendPanel to the token**

In `packages/smart_pid_web/src/features/dashboard/TrendPanel.tsx`:

Replace line 13:

```tsx
import { useTheme } from '@/theme/ThemeProvider';
```

with:

```tsx
import { useGlowTrace } from '@/theme/useGlowTrace';
```

Replace the doc comment and function head at lines 59-65:

```tsx
/**
 * Recorder strip for the selected loop (§6.7/§6.9): live window, pen tip at the
 * true latest sample, AI ticks in `--accent`, and the Phosphor halo pass. The
 * `ctx.shadowBlur` path stays banned — the halo lives in `Trend`.
 */
export function TrendPanel({ controllerId, scale }: TrendPanelProps) {
  const { theme } = useTheme();
```

with:

```tsx
/**
 * Recorder strip for the selected loop (§6.7/§6.9): live window, pen tip at the
 * true latest sample, AI ticks in `--accent`, and the halo pass on PV whenever
 * `--glow-trace` is non-zero (§10.5). The `ctx.shadowBlur` path stays banned —
 * the halo lives in `Trend`.
 */
export function TrendPanel({ controllerId, scale }: TrendPanelProps) {
  const glow = useGlowTrace();
```

Replace line 170:

```tsx
          glow={theme === 'phosphor'}
```

with:

```tsx
          glow={glow}
```

- [ ] **Step 8: Switch TwinTrend to the token**

In `packages/smart_pid_web/src/features/simulator/TwinTrend.tsx`:

Replace line 8:

```tsx
import { useTheme } from '@/theme/ThemeProvider';
```

with:

```tsx
import { useGlowTrace } from '@/theme/useGlowTrace';
```

Replace line 29:

```tsx
  const { theme } = useTheme();
```

with:

```tsx
  const glow = useGlowTrace();
```

Replace line 73:

```tsx
          glow={theme === 'phosphor'}
```

with:

```tsx
          glow={glow}
```

- [ ] **Step 8b: Refresh the now-stale prop docs in `Trend`**

`Trend` keeps its `glow?: boolean` prop — only the caller's decision rule changed — but its comment still names the deleted mechanism.

In `packages/smart_pid_web/src/components/Trend.tsx`, replace line 42:

```tsx
  /** Phosphor halo pass on PV (§6.7). Caller decides (phase 4: theme === 'phosphor'). */
```

with:

```tsx
  /** Static halo pass on PV (§6.7). Caller decides from `--glow-trace` (§10.5). */
```

and line 83 of the same file, the `drawHalo` doc comment's opening line:

```tsx
 * §6.7 Phosphor halo: re-stroke the PV path 2× wider at low alpha, then crisp
```

with:

```tsx
 * §6.7 halo: re-stroke the PV path 2× wider at low alpha, then crisp
```

Leave the rest of that comment — the `ctx.shadowBlur` ban is still load-bearing and `TrendPanel.test.tsx` asserts the identifier never appears in executable code.

- [ ] **Step 9: Run the tests to verify they pass**

Run: `cd packages/smart_pid_web && npx vitest run src/features/dashboard/TrendPanel.test.tsx src/theme/useGlowTrace.test.tsx`
Expected: PASS — including `never reaches for ctx.shadowBlur — the banned §6.7 per-frame path`, which is unaffected.

- [ ] **Step 10: Typecheck, lint and run the full unit suite**

Run: `npm --prefix packages/smart_pid_web run typecheck && npm --prefix packages/smart_pid_web run lint && cd packages/smart_pid_web && npm run test`
Expected: PASS all three. Lint matters here: `useTheme` is now an unused import if either replacement was missed.

- [ ] **Step 11: Commit**

```bash
git add packages/smart_pid_web/src/theme/useGlowTrace.ts packages/smart_pid_web/src/theme/useGlowTrace.test.tsx packages/smart_pid_web/src/features/dashboard/TrendPanel.tsx packages/smart_pid_web/src/features/dashboard/TrendPanel.test.tsx packages/smart_pid_web/src/features/simulator/TwinTrend.tsx packages/smart_pid_web/src/components/Trend.tsx
git commit -m "refactor(trend): drive the PV halo from --glow-trace instead of a theme id"
```

---

### Task 8: Apply the glows

**Files:**
- Modify: `packages/smart_pid_web/src/index.css:131-192` (the `@layer components` block)
- Modify: `packages/smart_pid_web/src/components/Badge.tsx:12-14`
- Modify: `packages/smart_pid_web/src/components/Badge.test.tsx`
- Modify: `packages/smart_pid_web/src/components/Button.tsx:20`
- Modify: `packages/smart_pid_web/src/components/Button.test.tsx:21-28`
- Create: `packages/smart_pid_web/src/theme/glow.test.ts`

**Interfaces:**
- Consumes: Task 1's `--glow-alarm`, `--glow-focus`, `--glow-accent`.
- Produces: two new hook classes, `badge-glow` (on `Badge`'s `crit`, `warn` and `adv` tones) and `btn-primary` (on `Button`'s `primary` variant), plus four CSS rules in `src/index.css`'s `@layer components`. `--glow-alarm`, `--glow-focus` and `--glow-accent` are referenced by **exactly four** rules across the whole stylesheet, and by nothing else.

**Why `--tw-shadow` for the focus ring.** Every focusable control in this codebase wears the Tailwind utilities `focus-visible:ring-2 focus-visible:ring-focus-ring`. Verified against the installed Tailwind v4.3.3, that emits `box-shadow: var(--tw-inset-shadow), var(--tw-inset-ring-shadow), var(--tw-ring-offset-shadow), var(--tw-ring-shadow), var(--tw-shadow)` in `@layer utilities`, with `--tw-shadow` registered as `@property { syntax: "*"; inherits: false; initial-value: 0 0 #0000 }`. A plain `box-shadow` rule in `@layer base` or `@layer components` would lose the cascade to that utility. Assigning `--tw-shadow` instead composes the bloom *outside* the ring in a single rule, with no per-component change. Declared layer order in the compiled output is `properties, theme, base, components, utilities`, so a `components`-layer assignment beats Tailwind's `properties`-layer fallback. (A control that also wore a `shadow-*` utility would override `--tw-shadow` and lose the bloom; `grep` confirms no `shadow-sm|md|lg|xl|2xl|none|[…]` utility exists anywhere in `src/`.)

**Why no new animation.** §10.5 requires any unacknowledged-alarm pulse to be suppressed under `prefers-reduced-motion: reduce`. The only pulse in the product is the existing `.alarm-blink .sev-icon` glyph-opacity blink, already killed by `index.css:181-183` and by the global `@layer base` kill-switch. The bloom added here is **static**: it hangs off `.alarm-row.is-unacked`, which does not animate. Adding a pulsing glow would be new motion on an operating screen for no diagnostic gain — this task therefore adds no `@keyframes`, and the test below pins that.

- [ ] **Step 1: Write the failing test**

Create `packages/smart_pid_web/src/theme/glow.test.ts`:

```ts
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

// Vitest runs from the package root (`npm run test` in packages/smart_pid_web).
const css = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8');

describe('§10.5 glow is the salience channel, not decoration', () => {
  it('blooms the focus ring through the Tailwind ring composition variable', () => {
    expect(css).toMatch(/:focus-visible\s*\{\s*--tw-shadow:\s*var\(--glow-focus\);\s*\}/);
  });

  it('blooms unacked alarm rows without dropping the 3 px severity stripe', () => {
    expect(css).toMatch(
      /\.alarm-row\.is-unacked\s*\{\s*box-shadow:\s*inset 3px 0 0 0 currentColor,\s*var\(--glow-alarm\);\s*\}/,
    );
  });

  it('blooms severity badges and primary-button hover/active', () => {
    expect(css).toMatch(/\.badge-glow\s*\{\s*box-shadow:\s*var\(--glow-alarm\);\s*\}/);
    expect(css).toMatch(
      /\.btn-primary:hover,\s*\.btn-primary:active\s*\{\s*box-shadow:\s*var\(--glow-accent\);\s*\}/,
    );
  });

  it('reaches exactly four rules — no state dot, card border, header or body text blooms', () => {
    const uses = css.match(/var\(--glow-(?:alarm|focus|accent)\)/g) ?? [];
    expect(uses).toHaveLength(4);
  });

  it('adds no motion: the bloom is static and the only pulse stays reduced-motion safe', () => {
    expect(css).not.toMatch(/@keyframes\s+[a-z-]*glow/);
    const componentsRm = css.slice(
      css.indexOf('@media (prefers-reduced-motion: reduce)', css.indexOf('@layer components')),
    );
    expect(componentsRm).toMatch(/\.alarm-blink \.sev-icon\s*\{\s*animation:\s*none;/);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd packages/smart_pid_web && npx vitest run src/theme/glow.test.ts`
Expected: FAIL — four of the five cases fail; `expected '@import 'tailwindcss';…' to match /:focus-visible\s*\{\s*--tw-shadow:…/` and `expected [] to have a length of 4 but got 0`.

- [ ] **Step 3: Add the glow rules to `index.css`**

In `packages/smart_pid_web/src/index.css`, replace lines 172-178:

```css
  /* 3 px severity stripe on unacknowledged rows — a shape cue, not a fill. */
  .alarm-row.is-unacked {
    box-shadow: inset 3px 0 0 0 currentColor;
  }
  .alarm-row.sev-critical.is-unacked { background: var(--alarm-crit-bg); }
  .alarm-row.sev-warning.is-unacked { background: var(--alarm-warn-bg); }
  .alarm-row.sev-advisory.is-unacked { background: var(--alarm-adv-bg); }
```

with:

```css
  /*
   * §10.5 glow. Four rules, four surfaces: unacked alarm rows, severity badges,
   * the focus ring and primary-button hover/active. Nothing else — no state dot,
   * no card border, no header, no body text. Outside neon every token is
   * `0 0 #0000`, a valid no-op <shadow>, so these rules cost nothing there.
   *
   * The bloom is STATIC. The only pulse on an unacked alarm is the glyph blink
   * above, already killed under prefers-reduced-motion.
   */

  /* 3 px severity stripe on unacknowledged rows — a shape cue, not a fill. */
  .alarm-row.is-unacked {
    box-shadow: inset 3px 0 0 0 currentColor, var(--glow-alarm);
  }
  .alarm-row.sev-critical.is-unacked { background: var(--alarm-crit-bg); }
  .alarm-row.sev-warning.is-unacked { background: var(--alarm-warn-bg); }
  .alarm-row.sev-advisory.is-unacked { background: var(--alarm-adv-bg); }

  /* Severity badges (Badge tones crit/warn/adv). */
  .badge-glow {
    box-shadow: var(--glow-alarm);
  }

  /*
   * Focus ring. Tailwind's `ring-2` composes `var(--tw-shadow)` as the outermost
   * layer of its box-shadow, so assigning that variable blooms the ring without
   * a per-component class and without out-cascading the ring itself. A plain
   * `box-shadow` here would be beaten by the utility layer and do nothing.
   */
  :focus-visible {
    --tw-shadow: var(--glow-focus);
  }

  /* Primary button, pressed or hovered — interactive affordance, not chrome. */
  .btn-primary:hover,
  .btn-primary:active {
    box-shadow: var(--glow-accent);
  }
```

- [ ] **Step 4: Hook the severity badges**

In `packages/smart_pid_web/src/components/Badge.tsx`, replace lines 12-14:

```tsx
        crit: 'border-alarm-crit text-alarm-crit',
        warn: 'border-alarm-warn text-alarm-warn',
        adv: 'border-alarm-adv text-alarm-adv',
```

with:

```tsx
        // `badge-glow` is the §10.5 bloom hook (src/index.css). Severity only —
        // `neutral` and `log` are chrome and must never bloom.
        crit: 'badge-glow border-alarm-crit text-alarm-crit',
        warn: 'badge-glow border-alarm-warn text-alarm-warn',
        adv: 'badge-glow border-alarm-adv text-alarm-adv',
```

- [ ] **Step 5: Hook the primary button**

In `packages/smart_pid_web/src/components/Button.tsx`, replace line 20:

```tsx
        primary: 'bg-accent text-on-accent hover:bg-accent-hover active:bg-accent-sunk',
```

with:

```tsx
        // `btn-primary` is the §10.5 hover/active bloom hook (src/index.css).
        primary: 'btn-primary bg-accent text-on-accent hover:bg-accent-hover active:bg-accent-sunk',
```

- [ ] **Step 6: Pin the hook classes in the component tests**

Append this case to `describe('Badge', …)` in `packages/smart_pid_web/src/components/Badge.test.tsx`:

```tsx
  it('carries the §10.5 bloom hook on severity tones and never on chrome tones', () => {
    const { rerender } = render(<Badge tone="crit">crit</Badge>);
    expect(screen.getByText('crit').className).toContain('badge-glow');
    rerender(<Badge tone="warn">warn</Badge>);
    expect(screen.getByText('warn').className).toContain('badge-glow');
    rerender(<Badge tone="adv">adv</Badge>);
    expect(screen.getByText('adv').className).toContain('badge-glow');
    rerender(<Badge tone="neutral">neutral</Badge>);
    expect(screen.getByText('neutral').className).not.toContain('badge-glow');
    rerender(<Badge tone="log">log</Badge>);
    expect(screen.getByText('log').className).not.toContain('badge-glow');
  });
```

In `packages/smart_pid_web/src/components/Button.test.tsx`, replace the `variant classes are token-only` case (lines 21-28) with:

```tsx
  it('variant classes are token-only', () => {
    const { rerender } = render(<Button variant="primary">a</Button>);
    expect(screen.getByRole('button').className).toContain('bg-accent');
    // §10.5 bloom hook — primary only; secondary/ghost/destructive stay flat.
    expect(screen.getByRole('button').className).toContain('btn-primary');
    rerender(<Button variant="destructive">a</Button>);
    expect(screen.getByRole('button').className).toContain('bg-alarm-crit');
    expect(screen.getByRole('button').className).not.toContain('btn-primary');
    rerender(<Button variant="ghost">a</Button>);
    expect(screen.getByRole('button').className).toContain('text-text-soft');
    expect(screen.getByRole('button').className).not.toContain('btn-primary');
  });
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd packages/smart_pid_web && npx vitest run src/theme/glow.test.ts src/components/Badge.test.tsx src/components/Button.test.tsx`
Expected: PASS — `glow.test.ts` reports 5 passing, including `reaches exactly four rules`.

- [ ] **Step 8: Prove the ring survives in a browser, in both bloom states**

```bash
cd packages/smart_pid_web && env -u CI npx playwright test e2e/target-size.spec.ts e2e/login-dashboard.spec.ts
```

Expected: PASS. Then, in the same running dev server, confirm the focus ring is still painted where the glow token is a no-op — the regression this task most plausibly causes is an invalid composed `box-shadow` erasing the ring outside `neon`:

```bash
cd packages/smart_pid_web && env -u CI npx playwright test e2e/themes.spec.ts -g "the dashboard renders under recorder"
```

Expected: PASS.

- [ ] **Step 9: Run the full unit suite, typecheck and lint**

Run: `npm --prefix packages/smart_pid_web run typecheck && npm --prefix packages/smart_pid_web run lint && cd packages/smart_pid_web && npm run test`
Expected: PASS all three, including `src/__tests__/token-guard.test.ts` — `badge-glow` and `btn-primary` are not colour literals and not named-palette utilities.

- [ ] **Step 10: Commit**

```bash
git add packages/smart_pid_web/src/index.css packages/smart_pid_web/src/components/Badge.tsx packages/smart_pid_web/src/components/Badge.test.tsx packages/smart_pid_web/src/components/Button.tsx packages/smart_pid_web/src/components/Button.test.tsx packages/smart_pid_web/src/theme/glow.test.ts
git commit -m "feat(theme): bloom alarm rows, severity badges, focus ring and primary hover"
```

---

### Task 9: `TEST_E2E.md` — E2E-045 and E2E-046

**Files:**
- Modify: `TEST_E2E.md:340-350` (the two procedure blocks), `TEST_E2E.md:424-425` (the summary rows)

**Interfaces:**
- Consumes: Task 6's `neon` default, Task 7's token-driven halo.
- Produces: nothing consumed by later tasks. **Do not touch E2E-006, E2E-036 or E2E-049** — those belong to the sibling UI-corrections plan, which edits the same file.

No assertion is weakened. E2E-045 gains a fourth theme and an explicit pre-paint requirement; E2E-046 stops naming a theme and states the token rule that replaced it, which is strictly more specific than "only in Phosphor".

- [ ] **Step 1: Re-specify E2E-045**

In `TEST_E2E.md`, replace lines 340-344:

```markdown
#### E2E-045 — Theme switch and persistence
- **Steps:** Switch Recorder→Phosphor→ISA-101; inspect `<html data-theme>`; reload each.
- **Expected:** Attribute and visual treatment change and persist; Recorder is default in a fresh browser storage profile.
- **Evidence:** `test-evidence/E2E-045-themes.png`
- **Result:** [x] PASS [ ] FAIL
```

with:

```markdown
#### E2E-045 — Theme switch and persistence
- **Steps:** From the `Configurações` menu cycle Neon→Recorder→Phosphor→ISA-101→Neon; inspect
  `<html data-theme>` and `localStorage['spid.theme']` after each pick; reload after each. Then clear
  `localStorage` through CDP and load `/` in a fresh storage profile.
- **Expected:** The menu offers exactly four themes — `Neon`, `Recorder`, `Phosphor`, `ISA-101`.
  The attribute, the stored value and the visual treatment change together and survive every reload.
  In a fresh storage profile the app opens on `Neon`, and `data-theme="neon"` is already on `<html>`
  before React mounts — no flash of another theme at any point.
- **Evidence:** `test-evidence/E2E-045-themes.png`
- **Result:** [ ] PASS [ ] FAIL
```

- [ ] **Step 2: Re-specify E2E-046**

In `TEST_E2E.md`, replace lines 346-350:

```markdown
#### E2E-046 — Phosphor-only halo and legacy migration
- **Steps:** Compare PV trace Recorder/Phosphor; set localStorage `spid.theme='ocean'` through CDP and reload.
- **Expected:** Static PV halo appears only in Phosphor; no `shadowBlur`-style frame collapse; legacy ocean migrates to Recorder and storage updates.
- **Evidence:** `test-evidence/E2E-046-halo-migration.png`
- **Result:** [x] PASS [ ] FAIL
```

with:

```markdown
#### E2E-046 — Token-driven PV halo and legacy migration
- **Steps:** Compare the PV trace under all four themes. In each, read
  `getComputedStyle(document.documentElement).getPropertyValue('--glow-trace')` and the trend
  container's `data-glow` attribute. Then set localStorage `spid.theme='ocean'` through CDP and reload.
- **Expected:** The static PV halo is present wherever `--glow-trace` is non-zero — Phosphor (`4px`)
  and Neon (`8px`) — and absent wherever it is `0px` — Recorder and ISA-101. `data-glow` tracks the
  token in every case. No component decides this from a theme id. No `shadowBlur`-style frame
  collapse in any of the four themes. Legacy `ocean` still migrates to Recorder and storage updates.
- **Evidence:** `test-evidence/E2E-046-halo-migration.png`
- **Result:** [ ] PASS [ ] FAIL
```

- [ ] **Step 3: Update the two summary rows**

In `TEST_E2E.md`, replace lines 424-425:

```markdown
| E2E-045 | Theme persistence | PASS | `E2E-045-themes.png` | All three themes persist across reload; Recorder default in a fresh profile |
| E2E-046 | Halo/migration | PASS | `E2E-046-halo-migration.png` |  |
```

with:

```markdown
| E2E-045 | Theme persistence | RE-RUN | `E2E-045-themes.png` | Procedure re-specified for the fourth theme: four themes persist across reload; Neon is the fresh-profile default and paints pre-mount. Awaiting the re-run in §12 step 11. |
| E2E-046 | Halo/migration | RE-RUN | `E2E-046-halo-migration.png` | Procedure re-specified: the halo follows `--glow-trace`, so it is present in Phosphor **and** Neon and absent in Recorder and ISA-101. Strictly more specific than the old "only in Phosphor". Awaiting the re-run in §12 step 11. |
```

`RE-RUN` is honest bookkeeping, not a weakened assertion: the procedure text changed, so the recorded `PASS` no longer describes a run that happened. Task 11 executes both and the operator flips them back to `PASS`.

- [ ] **Step 4: Verify nothing else in the file moved**

Run: `git diff --stat TEST_E2E.md && git diff -U0 TEST_E2E.md | grep -c '^[+-]'`
Expected: only `TEST_E2E.md` listed, and the changed-line count is 20 (10 removed, 10 added). If `E2E-006`, `E2E-036` or `E2E-049` appear in the diff, revert those hunks — they belong to the sibling plan.

- [ ] **Step 5: Commit**

```bash
git add TEST_E2E.md
git commit -m "docs(e2e): re-specify E2E-045 and E2E-046 for the neon theme"
```

---

### Task 10: Playwright — four-theme matrix and new baselines

**Files:**
- Modify: `packages/smart_pid_web/e2e/themes.spec.ts:1-12` (header comment), `:14`, `:16-20`, `:28-31`, `:56-67`, `:99` (the visual-baseline comment)
- Modify: `packages/smart_pid_web/e2e/user-role.spec.ts:165`, `:185`
- Create: `packages/smart_pid_web/e2e/themes.spec.ts-snapshots/dashboard-neon-320-linux.png`
- Create: `packages/smart_pid_web/e2e/themes.spec.ts-snapshots/dashboard-neon-768-linux.png`
- Create: `packages/smart_pid_web/e2e/themes.spec.ts-snapshots/dashboard-neon-1024-linux.png`
- Create: `packages/smart_pid_web/e2e/themes.spec.ts-snapshots/dashboard-neon-1440-linux.png`

**Interfaces:**
- Consumes: Task 4's registered theme and `Neon` label, Task 6's default flip, Task 7's token-driven `data-glow`.
- Produces: a 4-theme × 4-viewport visual matrix (16 dashboard PNGs) plus the one faceplate PNG in `faceplate.spec.ts` — 17 baselines total, up from 13.

- [ ] **Step 1: Update the theme matrix header and lists**

In `packages/smart_pid_web/e2e/themes.spec.ts`, replace lines 1-20:

```ts
import { expect, test, type Page } from '@playwright/test';
import { FIC101, TIC202, emitFrames, faceplate, gotoDashboard, settleForShot } from './helpers/harness';

// §6.8 theme matrix. Three themes ship: recorder (default), phosphor, isa101.
// MD3 dark/light and Ocean are dropped; Dark Room is superseded by Phosphor, and
// stored legacy values migrate rather than silently falling back.
//
// Phase 11 adds the terminal visual baseline set: 3 themes x 4 viewports = 12
// dashboard PNGs here, plus one faceplate PNG in faceplate.spec.ts = 13 total.
// The obsolete 5x4 matrix (ocean / md3-dark / md3-light / dark-room / isa101)
// was deleted in 7603b80.

const THEMES = ['recorder', 'phosphor', 'isa101'] as const;
const LOOPS = [FIC101, TIC202];

const THEME_LABEL: Record<(typeof THEMES)[number], string> = {
  recorder: 'Recorder',
  phosphor: 'Phosphor',
  isa101: 'ISA-101',
};
```

with:

```ts
import { expect, test, type Page } from '@playwright/test';
import { FIC101, TIC202, emitFrames, faceplate, gotoDashboard, settleForShot } from './helpers/harness';

// §6.8 + §10 theme matrix. Four themes ship: recorder, phosphor, isa101 and
// neon — neon is the default (§10.2). MD3 dark/light and Ocean are dropped;
// Dark Room is superseded by Phosphor, and stored legacy values migrate rather
// than silently falling back (a stored `ocean` still resolves to recorder).
//
// Visual baseline set: 4 themes x 4 viewports = 16 dashboard PNGs here, plus
// one faceplate PNG in faceplate.spec.ts = 17 total. The obsolete 5x4 matrix
// (ocean / md3-dark / md3-light / dark-room / isa101) was deleted in 7603b80.

const THEMES = ['recorder', 'phosphor', 'isa101', 'neon'] as const;
const LOOPS = [FIC101, TIC202];

const THEME_LABEL: Record<(typeof THEMES)[number], string> = {
  recorder: 'Recorder',
  phosphor: 'Phosphor',
  isa101: 'ISA-101',
  neon: 'Neon',
};
```

- [ ] **Step 2: Update the default-theme test**

Replace lines 28-31:

```ts
test('recorder is the default when nothing is stored', async ({ page }) => {
  await gotoDashboard(page, { loops: LOOPS });
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'recorder');
});
```

with:

```ts
test('neon is the default when nothing is stored', async ({ page }) => {
  await gotoDashboard(page, { loops: LOOPS });
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'neon');
  // The pre-paint script in index.html and the static attribute agree, so the
  // stored value is only written once the operator picks something.
  expect(await page.evaluate(() => localStorage.getItem('spid.theme'))).toBeNull();
});
```

- [ ] **Step 3: Make the halo test token-driven**

Replace lines 56-67:

```ts
test('the phosphor halo pass is on only under phosphor', async ({ page }) => {
  await gotoDashboard(page, { loops: LOOPS, theme: 'phosphor' });
  await expect(page.getByRole('img', { name: 'Tendência FIC-101' })).toHaveAttribute(
    'data-glow',
    'on',
  );

  await selectTheme(page, 'recorder');
  await expect(page.getByRole('img', { name: 'Tendência FIC-101' })).toHaveAttribute(
    'data-glow',
    'off',
  );
});
```

with:

```ts
// §10.5/D12: the halo is "--glow-trace is non-zero", not "the theme is Phosphor".
// Phosphor declares 4px and Neon 8px; Recorder and ISA-101 declare 0px.
const GLOW_TRACE: Record<(typeof THEMES)[number], { token: string; glow: 'on' | 'off' }> = {
  recorder: { token: '0px', glow: 'off' },
  phosphor: { token: '4px', glow: 'on' },
  isa101: { token: '0px', glow: 'off' },
  neon: { token: '8px', glow: 'on' },
};

test('the PV halo follows --glow-trace, in every theme', async ({ page }) => {
  await gotoDashboard(page, { loops: LOOPS, theme: 'phosphor' });

  for (const theme of THEMES) {
    if ((await page.locator('html').getAttribute('data-theme')) !== theme) {
      await selectTheme(page, theme);
    }
    const expected = GLOW_TRACE[theme];
    const token = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--glow-trace').trim(),
    );
    expect(token, `${theme} --glow-trace`).toBe(expected.token);
    await expect(
      page.getByRole('img', { name: 'Tendência FIC-101' }),
      `${theme} data-glow`,
    ).toHaveAttribute('data-glow', expected.glow);
  }
});
```

- [ ] **Step 4: Update the two `user-role.spec.ts` counts**

In `packages/smart_pid_web/e2e/user-role.spec.ts`, replace line 165:

```ts
  await expect(menu.getByRole('menuitemradio')).toHaveText(['Recorder', 'Phosphor', 'ISA-101']);
```

with:

```ts
  await expect(menu.getByRole('menuitemradio')).toHaveText([
    'Recorder',
    'Phosphor',
    'ISA-101',
    'Neon',
  ]);
```

and line 185:

```ts
  await expect(menu.getByRole('menuitemradio')).toHaveCount(3);
```

with:

```ts
  await expect(menu.getByRole('menuitemradio')).toHaveCount(4);
```

- [ ] **Step 5: Run the non-visual theme and role specs to verify they pass**

```bash
cd packages/smart_pid_web && env -u CI npx playwright test e2e/user-role.spec.ts e2e/themes.spec.ts --grep-invert "renders identically"
```

Expected: PASS — including `neon is the default when nothing is stored`, `the PV halo follows --glow-trace, in every theme`, `persists an explicit neon selection across a reload` and `the dashboard renders under neon`.

- [ ] **Step 6: Run the visual matrix and watch the four neon shots fail**

```bash
cd packages/smart_pid_web && env -u CI npx playwright test e2e/themes.spec.ts --grep "renders identically"
```

Expected: the 12 existing recorder/phosphor/isa101 shots PASS unchanged (the glow tokens are `0 0 #0000` there and `--font-display` is the same Archivo stack, so nothing about those three themes moved a pixel); the four neon shots FAIL with `A snapshot doesn't exist at …/dashboard-neon-320-linux.png, writing actual.` If any of the 12 existing shots regressed, stop and find out why before writing new baselines — a moved pixel in Recorder means a glow rule leaked out of `neon`.

- [ ] **Step 7: Write the four neon baselines**

```bash
cd packages/smart_pid_web && env -u CI npx playwright test e2e/themes.spec.ts --grep "renders identically under neon" --update-snapshots
```

Expected: 4 passed. Then confirm the files exist and nothing else was rewritten:

```bash
cd packages/smart_pid_web && ls e2e/themes.spec.ts-snapshots && git status --porcelain e2e/themes.spec.ts-snapshots
```

Expected: 16 PNGs listed; `git status` shows exactly four new untracked `dashboard-neon-*.png` files and **no** modified existing baseline.

- [ ] **Step 8: Inspect the new baselines by eye**

Open `e2e/themes.spec.ts-snapshots/dashboard-neon-1440-linux.png`. Confirm: near-black `#07070E` background, cyan accents, neon-green running state dots, the PV trace carrying a visible halo, Orbitron on the `SMART PID` wordmark, and Geist Mono numerals in the readouts. A shot that looks like Phosphor means `data-theme` never reached `neon` — do not commit it.

- [ ] **Step 9: Run the whole Playwright suite**

```bash
cd packages/smart_pid_web && env -u CI npx playwright test
```

Expected: PASS. Every spec is green again — this is the point at which the Playwright red opened by Task 4 closes.

- [ ] **Step 10: Commit**

```bash
git add packages/smart_pid_web/e2e/themes.spec.ts packages/smart_pid_web/e2e/user-role.spec.ts packages/smart_pid_web/e2e/themes.spec.ts-snapshots
git commit -m "test(e2e): extend the theme matrix to neon with four new visual baselines"
```

---

### Task 11: Verification sweep (spec §12 steps 6–10)

**Files:**
- Modify: none, unless a check fails.
- Test: the whole frontend gate.

**Interfaces:**
- Consumes: everything from Tasks 1–10.
- Produces: recorded evidence that spec §10.8 holds. Nothing later depends on this task; it is the stop condition for this plan.

§12 steps 1–3 are the standard gate and are run first here. Steps 4 and 5 (the CDP rail sweep and the 320 px nav re-measurement) belong to the sibling UI-corrections plan and are **not** run here. Step 11 covers only E2E-045 and E2E-046, the two procedures this plan owns. Step 12 stands: the backend suite is not re-run, this work touches no Python.

- [ ] **Step 1: Typecheck, lint and full Vitest (§12 steps 1–2)**

```bash
npm --prefix packages/smart_pid_web run typecheck && npm --prefix packages/smart_pid_web run lint && cd packages/smart_pid_web && npm run test
```

Expected: PASS all three, zero failures, zero warnings from `eslint`.

- [ ] **Step 2: Full Playwright (§12 step 3)**

```bash
cd packages/smart_pid_web && env -u CI npx playwright test
```

Expected: PASS. Do **not** substitute the omp `browser` tool: it does not deliver CDP input to the page and has previously produced false "dead control" reports.

- [ ] **Step 3: Theme gate — the contrast and resolution gates (§12 step 6)**

```bash
cd packages/smart_pid_web && npx vitest run src/theme/themeContrast.test.ts src/theme/tokenResolve.test.ts
```

Expected: PASS. Then prove no floor moved and no assertion was dropped:

```bash
git diff c594f09 -- packages/smart_pid_web/src/theme/themeContrast.test.ts
```

Expected: exactly one changed line — `const THEMES: GateThemeId[]` gaining `'neon'` — plus the two-line comment above it. `TEXT_FLOOR = 4.5` and `NONTEXT_FLOOR = 3.0` must be untouched, and no `expect(` line may have been removed.

Confirm the 48-token resolution explicitly:

```bash
cd packages/smart_pid_web && npx vitest run src/theme/tokenResolve.test.ts -t "every contract token resolves non-empty"
```

Expected: 4 passing — one per theme id.

- [ ] **Step 4: Fresh-profile paint check (§12 step 7)**

Start the dev server and drive it with Playwright — not with the `browser` tool.

```bash
cd packages/smart_pid_web && env -u CI npx playwright test e2e/themes.spec.ts -g "neon is the default when nothing is stored"
```

Expected: PASS. Then confirm the *pre-mount* half directly, which the spec assertion requires and the test above only implies. Add this throwaway check to a scratch spec, run it, then delete the file:

```ts
// packages/smart_pid_web/e2e/__scratch-prepaint.spec.ts
import { expect, test } from '@playwright/test';

test('neon is on <html> before React mounts', async ({ page }) => {
  const seen: string[] = [];
  await page.addInitScript(() => {
    // Runs before any page script, including the pre-paint block.
    (window as unknown as { __themes: string[] }).__themes = [];
    new MutationObserver(() => {
      (window as unknown as { __themes: string[] }).__themes.push(
        document.documentElement.getAttribute('data-theme') ?? 'null',
      );
    }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  });
  await page.goto('/');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'neon');
  seen.push(
    ...(await page.evaluate(() => (window as unknown as { __themes: string[] }).__themes)),
  );
  // The static attribute is already `neon`, so no transition to another theme
  // may ever have been recorded.
  expect(seen.filter((t) => t !== 'neon')).toEqual([]);
});
```

```bash
cd packages/smart_pid_web && env -u CI npx playwright test e2e/__scratch-prepaint.spec.ts && rm packages/smart_pid_web/e2e/__scratch-prepaint.spec.ts
```

Expected: PASS, then the scratch file is gone. Capture the browser screenshot as `test-evidence/E2E-045-themes.png`.

- [ ] **Step 5: No external font request on any route (§12 step 8)**

```bash
cd packages/smart_pid_web && grep -rn 'fonts.googleapis.com\|fonts.gstatic.com\|@import url(' src index.html
```

Expected: no matches. Then prove it at runtime across every route. Add this throwaway spec, run it, delete it:

```ts
// packages/smart_pid_web/e2e/__scratch-nocdn.spec.ts
import { expect, test } from '@playwright/test';
import { FIC101, gotoDashboard } from './helpers/harness';

const ROUTES = ['/', '/trends', '/alarms', '/simulator', '/executive', '/projects', '/settings', '/connection', '/users'];

test('no route requests a font from a CDN', async ({ page }) => {
  const external: string[] = [];
  page.on('request', (r) => {
    const url = r.url();
    if (url.includes('fonts.googleapis.com') || url.includes('fonts.gstatic.com')) external.push(url);
  });
  await gotoDashboard(page, { loops: [FIC101], role: 'admin' });
  for (const route of ROUTES) {
    await page.goto(route);
    await page.waitForLoadState('networkidle');
  }
  expect(external).toEqual([]);
});
```

```bash
cd packages/smart_pid_web && env -u CI npx playwright test e2e/__scratch-nocdn.spec.ts && rm packages/smart_pid_web/e2e/__scratch-nocdn.spec.ts
```

Expected: PASS, then the scratch file is gone. Capture the network panel as `test-evidence/MOD1-043-no-cdn.png` if that evidence slot exists in the gate you are running; otherwise keep it with the E2E-045 evidence.

- [ ] **Step 6: Glow placement audit (§12 step 9)**

Static half — the four-rule bound is already pinned by `src/theme/glow.test.ts`:

```bash
cd packages/smart_pid_web && npx vitest run src/theme/glow.test.ts
```

Expected: PASS, 5 cases.

Visual half — run the dev server, log in as `admin` under `neon`, force a CRITICAL alarm, and confirm by eye:

- the unacknowledged alarm row blooms pink and its severity badge blooms;
- tabbing to any button, input, switch or menu item produces a cyan bloom **around** the 2 px ring, with the ring still visibly present;
- hovering the primary `Salvar` / `Exportar CSV` button blooms cyan;
- the PV trace carries its halo;
- **nothing else blooms** — check a `RUNNING` state dot, a card border, the top-bar header and a paragraph of body text.

Then re-check with reduced motion emulated:

```bash
cd packages/smart_pid_web && env -u CI npx playwright test e2e/themes.spec.ts -g "the dashboard renders under neon"
```

and, in the running browser, apply `prefers-reduced-motion: reduce` via DevTools rendering emulation. Expected: the unacknowledged alarm's glyph blink stops, the bloom stays static and present, and the row's bold/underline reduced-motion encoding appears. No pulsing bloom at any point.

Capture as `test-evidence/E2E-046-halo-migration.png`.

- [ ] **Step 7: Visual baselines exist and are stable (§12 step 10)**

```bash
cd packages/smart_pid_web && env -u CI npx playwright test e2e/themes.spec.ts --grep "renders identically" && ls e2e/themes.spec.ts-snapshots | wc -l
```

Expected: 16 passed, and `16` PNGs on disk. Run the same command a second time — a baseline that only passes once is non-deterministic and must be re-captured with `settleForShot` investigated, not accepted.

- [ ] **Step 8: Re-run the two owned `TEST_E2E.md` procedures (§12 step 11, this plan's half)**

Execute **E2E-045** and **E2E-046** exactly as re-specified in Task 9, by hand against the running app, and save the two evidence PNGs to `test-evidence/`. Flip both `- **Result:**` lines to `[x] PASS [ ] FAIL` and both summary-table cells from `RE-RUN` to `PASS`, replacing the "Awaiting the re-run" sentence in each note with the observed outcome.

If either fails, fix the source and re-run — do not soften the procedure.

- [ ] **Step 9: Bundle budget**

```bash
cd packages/smart_pid_web && npm run build:budget
```

Expected: PASS. `fonts: <N> KB raw (4 woff2)` under the 160 KB budget, and no `+10 KB` regression flag against `bundle-baseline.json`. If the fonts line trips the ±10 KB regression tolerance, update `bundle-baseline.json` in the same commit and say so in the message — Orbitron is a deliberate, budgeted addition.

- [ ] **Step 10: Commit the evidence and the flipped gate**

```bash
git add TEST_E2E.md test-evidence
git commit -m "test(e2e): re-run E2E-045 and E2E-046 against the neon theme"
```

---

## Spec coverage

| Spec §10.x | Requirement | Task |
|---|---|---|
| 10.1 | Fourth theme, ISA-101 premise discarded, `recorder`/`isa101` untouched as the conformance path | 4 |
| 10.1 | WCAG gate does not fall with ISA-101 — `neon` joins `GateThemeId` | 5 |
| 10.1 | Skill recommendations not adopted: no scanlines, no glitch keyframes, no CDN import, no second mono | 3 (self-hosted, no CDN), 8 (no keyframes), 11 step 5 (no CDN at runtime) |
| 10.2 | `id: 'neon'`, label `Neon` | 4 |
| 10.2 | `neon` becomes `DEFAULT_THEME` | 6 |
| 10.3 | The 41 non-type tokens, verbatim | 4 |
| 10.3 | `CONTRACT_TOKENS` 44 → 48 | 1 |
| 10.3 | The neon block declares 46 names (41 + 4 glow + `--font-display`) | 4 |
| 10.3 | Every colour pair passes all 43 assertions of the existing gate | 5 |
| 10.4 | The −0.056 salience headroom is recorded, not litigated | 4 (recorded in the `themes.css` block comment) |
| 10.5 | Four new glow tokens; the other three themes declare them too | 1 |
| 10.5 | Glow applied to alarm rows, severity badges, focus ring, primary-button hover/active | 8 |
| 10.5 | Glow applied to the PV trace | 1 (`--glow-trace: 8px`), 7 (the halo reads it) |
| 10.5 | Glow applied to **nothing else** — no state dot, body text, card border, header or static chrome | 8 (the "exactly four rules" assertion), 11 step 6 |
| 10.5 | `--glow-trace` carries `px` for `parseFloat` | 1 |
| 10.5 | `theme === 'phosphor'` deleted from `TrendPanel.tsx` and `TwinTrend.tsx` | 7 |
| 10.5 | Any unacked-alarm pulse suppressed under `prefers-reduced-motion: reduce` | 8 |
| 10.6 | Only `--font-display` becomes per-theme; `--font-ui` and `--font-data` stay in `:root` | 2 |
| 10.6 | `neon` declares `'Orbitron Variable', 'Archivo Variable', system-ui, sans-serif` | 4 |
| 10.6 | Vendored as `orbitron-latin-var.woff2`, wght 400–900, no CDN | 3 |
| 10.6 | SIL OFL 1.1 committed alongside the font | 3 |
| 10.6 | Preloaded in `index.html` | 3 |
| 10.6 | `.type-display` keeps `font-stretch: 125%`, inert under Orbitron, commented not tokenised | 3 (the comment lands on the `@font-face`; `index.css:98-103` is left untouched) |
| 10.7 row 1 | `contract.ts` — `THEME_IDS`, `CONTRACT_TOKENS` | 1, 4 |
| 10.7 row 2 | `ThemeProvider.tsx` — `THEMES`, `DEFAULT_THEME` | 4, 6 |
| 10.7 row 3 | `themes.css` — new block, glow + `--font-display` on the other three | 1, 2, 4 |
| 10.7 row 4 | `tokens.css` — `--font-display` removed from `:root` | 2 |
| 10.7 row 5 | `themeContrast.ts` — `GateThemeId`, mirrored palette | 5 |
| 10.7 row 6 | `themeContrast.test.ts:7` | 5 |
| 10.7 row 7 | `isa101Mapping.test.ts:256` — four-block expectation | 4 |
| 10.7 row 8 | `isa101Mapping.test.ts:193` — type-token exception list, `ISA101_EXPECTED` | 2 |
| 10.7 row 9 | `fonts.test.ts:27` — `font-display: swap` 3 → 4 | 3 |
| 10.7 row 10 | `index.html` — static `data-theme`, `valid` array, fallback, preload | 3, 6 |
| 10.7 row 11 | `App.test.tsx:33` | 6 |
| 10.7 row 12 | `themes.spec.ts:28` — the default test | 10 |
| 10.7 row 13 | `themes.spec.ts` — `THEMES`, `THEME_LABEL`, new baselines | 10 |
| 10.7 row 14 | `user-role.spec.ts:185` — count 3 → 4 | 10 |
| 10.7 row 15 | `TrendPanel.tsx:170`, `TwinTrend.tsx:73` | 7 |
| 10.8 | `themeContrast.test.ts` green with no floor relaxed | 5, 11 step 3 |
| 10.8 | `tokenResolve.test.ts` resolves all 48 tokens under all four themes | 1, 11 step 3 |
| 10.8 | Fresh profile paints `neon` pre-mount, no flash | 6, 11 step 4 |
| 10.8 | Orbitron in wordmark and dialog titles; numerals stay Geist Mono | 2, 3, 4 |
| 10.8 | Zero requests to `fonts.googleapis.com` / `fonts.gstatic.com` | 3, 11 step 5 |
| 10.8 | Glow present on the four intended surfaces, absent everywhere else | 8, 11 step 6 |
| 10.8 | `prefers-reduced-motion: reduce` suppresses the alarm pulse | 8, 11 step 6 |
| 11.1 | `ThemeProvider.test.tsx`, `themeContrast.test.ts`, `isa101Mapping.test.ts`, `fonts.test.ts`, `tokenResolve.test.ts`, `App.test.tsx` | 1–6 |
| 11.2 | `themes.spec.ts`, `user-role.spec.ts` | 10 |
| 11.3 | E2E-045 four-theme cycle with `Neon` as the fresh-profile default | 9 |
| 11.3 | E2E-046 token-driven halo — Phosphor **and** Neon, not Recorder or ISA-101 | 9 |
| 12 step 6 | Theme gate green | 11 step 3 |
| 12 step 7 | Fresh-profile paint check | 11 step 4 |
| 12 step 8 | Network check on every route | 11 step 5 |
| 12 step 9 | Glow placement audit, including reduced motion | 11 step 6 |
| 12 step 10 | New `dashboard-neon-<width>.png` baselines at the four breakpoints | 10, 11 step 7 |
</content>
<parameter name="i">Writing the neon theme implementation plan