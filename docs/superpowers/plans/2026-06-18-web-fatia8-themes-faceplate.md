# Fatia 8: Themes + Faceplate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Close total visual + functional parity with the legacy PySide6 HMI by completing all 5 identity themes (Dark Room, ISA-101, MD3 dark, MD3 light, Ocean) as `[data-theme]` CSS custom-property sets, adding a persisted theme switcher, instrumenting the canonical `AnalogBar` so value/scale/alarm reflect real `status` data, and shipping the `Faceplate` control widget (PV/SP/CO, 8 ControllerMode segmented control, analog bars, actions) that consumes the `status` WS frame and reuses Fatia 2 command hooks. After this fatia the PySide6 HMI can be retired.

**Architecture:** React/Vite SPA (`packages/smart_pid_web`), hexagonal-on-the-backend (UNCHANGED here). Tokens are a stable CONTRACT defined once in `src/theme/tokens.css` (Fatia 0+1); this fatia only adds per-theme VALUE overrides in `src/theme/themes.css` keyed on `[data-theme="…"]` and extends `ThemeProvider.tsx` with a persisted switcher. `AnalogBar` (canonical, base shipped in Fatia 0+1) is instrumented here. `Faceplate` is a new Level-3 control panel that reads live data from the canonical `useRealtime()` hook (`lastStatus` map, keyed by `loop_id`) and issues commands exclusively through the Fatia 2 command hooks (`useSetSetpoint`/`useSetMode`/`useSetOutput`/`useApplyTuning`). Scale (`pv_scale.eu_min/eu_max/unit`) is read from the REST `ControllerResponse`, NOT from the `status` frame.

**Tech Stack:** React 18 + TypeScript (strict), Vite, TanStack Query, uPlot (themed per palette), Vitest + Testing Library (jsdom), Playwright (visual snapshots), `wcag-contrast` (programmatic contrast assertion). No backend changes; Python toolchain untouched.

## Global Constraints

Every task inherits the Foundation Contract §9 (verbatim):

- **Backend:** bind `127.0.0.1` (config `SPID_API_HOST`); serve SPA via `app.mount('/', StaticFiles(directory=dist, html=True))` mounted **after** routers (single-origin → no CORS in prod); dev CORS allowlist `http://127.0.0.1:5173` only; add security headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, basic CSP). Validate `Origin` on `/ws/realtime`.
- **RealtimeWS:** it is the **2nd EventBus consumer**; one recv-loop per client; **never** concurrent recv on the same socket. Coalesce last-value only for `status`/`stats`; `alarm`/`ai`/system are **lossless bounded** (on overflow, close the socket so the client re-syncs via REST). `ConnectionManager` with async lock + resilient broadcast.
- **TDD (mandatory):** failing test → run it red → minimal impl → run it green → commit. Bite-sized steps (2–5 min each), checkbox `- [ ]` syntax.
- **Branching (inviolable):** each fatia is implemented on a **new dedicated branch from `main`** (e.g. `feat/web-fatia08-themes-faceplate`). Never reuse another task's branch, never commit to `main` directly, never touch `feat/windows-installers`. Merge to `main` only with explicit user approval.
- **Subagents:** `model: opus` (project rule).
- **Commits:** conventional (`feat(web): …`, `fix(web): …`); **no attribution trailers**.
- **Python toolchain:** Python 3.13, `uv`. Lint `uv run --with ruff ruff check`.

**This fatia's branch:** `feat/web-fatia8-themes-faceplate` (create from `main`).

**Fatia-specific invariants:**

1. **NO BACKEND CHANGE.** This fatia touches only `packages/smart_pid_web/`. State this explicitly in the PR.
2. **Do NOT redefine the token CONTRACT.** `tokens.css` and `ThemeProvider`'s base API are owned by Fatia 0+1. This fatia ADDS value overrides to `themes.css` and EXTENDS `ThemeProvider` with the switcher only.
3. **Do NOT duplicate command logic.** The Faceplate reuses the Fatia 2 command hooks (`useSetSetpoint`, `useSetMode`, `useSetOutput`, `useApplyTuning`). If a hook name differs in the merged Fatia 2 code, adapt the import — do NOT re-implement the mutation.
4. **Canonical files** (`AnalogBar.tsx`, `RealtimeTrend.tsx`, `Faceplate.tsx`, `theme/*`): instrument/extend, never fork.
5. **`status` is the canonical WS type.** The spec text says "telemetry (WS)" loosely; the canonical `RealtimeType` for the live dashboard frame is **`status`** (`StatusData`). `mode` is a `ControllerMode` string value. Scale bounds come from REST.

## File Structure

```
packages/smart_pid_web/
  src/
    theme/
      themes.css                      # EXTEND: add dark-room, md3-dark, md3-light, ocean blocks (isa101 already in 0+1)
      ThemeProvider.tsx               # EXTEND: THEMES list + persisted setTheme + useTheme
      themeContrast.ts                # NEW: token-pair contrast helpers (build-time data + runtime read)
      __tests__/
        contrast.test.ts              # NEW: per-theme WCAG AA + alarm-matrix assertions
        ThemeProvider.test.tsx        # NEW: switch + localStorage persistence
    components/
      AnalogBar.tsx                   # INSTRUMENT: value/scale/alarm props → measurable position + alarm fill
      AnalogBar.test.tsx              # NEW: position-maps-to-PV + alarm-only-on-abnormal
      Faceplate.tsx                   # NEW: §5.3 control panel
      Faceplate.test.tsx              # NEW: render-by-mode/state; commands wired to Fatia 2 hooks
      shell/
        ThemeSwitcher.tsx             # NEW: persisted dropdown in TopBar
        ThemeSwitcher.test.tsx        # NEW
    lib/
      scale.ts                        # NEW: pv→fraction mapping (pure, unit-tested)
      scale.test.ts                   # NEW
      uplotTheme.ts                   # EXTEND/NEW: read trend-* tokens per palette (§7.1)
      uplotTheme.test.ts              # NEW
  e2e/
    themes.spec.ts                    # NEW: visual snapshots per theme @ 320/768/1024/1440
    faceplate.spec.ts                 # NEW: faceplate functional flow snapshot
```

---

### Task 1: Branch + theme registry scaffolding

**Files:** `src/theme/ThemeProvider.tsx`, `src/theme/themes.css`

**Interfaces:**
```ts
// ThemeProvider canonical API (Fatia 0+1) is EXTENDED — not replaced:
export type ThemeId = 'isa101' | 'dark-room' | 'md3-dark' | 'md3-light' | 'ocean';
export const THEMES: ReadonlyArray<{ id: ThemeId; label: string }>;
export function useTheme(): { theme: ThemeId; setTheme: (t: ThemeId) => void; themes: typeof THEMES };
```

- [ ] **Step 1:** Create the branch.
  ```bash
  cd /home/luciano/Documentos/ProjetosClaudeCode/smartPID && git checkout main && git pull --ff-only && git checkout -b feat/web-fatia8-themes-faceplate
  ```
  Expected: `Switched to a new branch 'feat/web-fatia8-themes-faceplate'`.

- [ ] **Step 2:** RED — write the theme-registry test. Create `src/theme/__tests__/ThemeProvider.test.tsx`:
  ```tsx
  import { render, screen, act } from '@testing-library/react';
  import { describe, it, expect, beforeEach } from 'vitest';
  import { ThemeProvider, useTheme, THEMES } from '../ThemeProvider';

  function Probe() {
    const { theme, setTheme, themes } = useTheme();
    return (
      <div>
        <span data-testid="current">{theme}</span>
        <span data-testid="count">{themes.length}</span>
        <button onClick={() => setTheme('ocean')}>ocean</button>
      </div>
    );
  }

  describe('ThemeProvider registry', () => {
    beforeEach(() => {
      localStorage.clear();
      document.documentElement.removeAttribute('data-theme');
    });

    it('exposes all 5 themes', () => {
      const ids = THEMES.map((t) => t.id);
      expect(ids).toEqual(
        expect.arrayContaining(['isa101', 'dark-room', 'md3-dark', 'md3-light', 'ocean']),
      );
      expect(ids).toHaveLength(5);
    });

    it('defaults to isa101 and sets data-theme on the html element', () => {
      render(<ThemeProvider><Probe /></ThemeProvider>);
      expect(screen.getByTestId('current').textContent).toBe('isa101');
      expect(document.documentElement.getAttribute('data-theme')).toBe('isa101');
    });
  });
  ```
  Run RED:
  ```bash
  cd packages/smart_pid_web && npm test -- src/theme/__tests__/ThemeProvider.test.tsx
  ```
  Expected: FAIL (`THEMES` has fewer than 5 entries, or `useTheme` missing `themes`).

- [ ] **Step 3:** GREEN — extend `ThemeProvider.tsx`. Add the full registry and ensure `setTheme` writes `data-theme` on `document.documentElement`. (Keep Fatia 0+1's persistence wiring; only ADD the missing theme ids.)
  ```tsx
  import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';

  export type ThemeId = 'isa101' | 'dark-room' | 'md3-dark' | 'md3-light' | 'ocean';

  export const THEMES: ReadonlyArray<{ id: ThemeId; label: string }> = [
    { id: 'isa101', label: 'ISA-101' },
    { id: 'dark-room', label: 'Dark Room' },
    { id: 'md3-dark', label: 'Material 3 Dark' },
    { id: 'md3-light', label: 'Material 3 Light' },
    { id: 'ocean', label: 'Ocean' },
  ];

  const STORAGE_KEY = 'spid.theme';
  const DEFAULT_THEME: ThemeId = 'isa101';

  function readStored(): ThemeId {
    const v = localStorage.getItem(STORAGE_KEY);
    return THEMES.some((t) => t.id === v) ? (v as ThemeId) : DEFAULT_THEME;
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
  Run GREEN:
  ```bash
  cd packages/smart_pid_web && npm test -- src/theme/__tests__/ThemeProvider.test.tsx
  ```
  Expected: PASS.

- [ ] **Step 4:** Commit.
  ```bash
  git add packages/smart_pid_web/src/theme && git commit -m "feat(web): theme registry with all 5 theme ids"
  ```

---

### Task 2: Persistence test + ThemeSwitcher

**Files:** `src/theme/__tests__/ThemeProvider.test.tsx`, `src/components/shell/ThemeSwitcher.tsx`, `src/components/shell/ThemeSwitcher.test.tsx`, `src/components/shell/TopBar.tsx`

**Interfaces:**
```tsx
export function ThemeSwitcher(): JSX.Element; // dropdown bound to useTheme()
```

- [ ] **Step 1:** RED — add the persistence + switch assertion to `ThemeProvider.test.tsx`:
  ```tsx
  it('persists theme choice to localStorage and applies data-theme', () => {
    render(<ThemeProvider><Probe /></ThemeProvider>);
    act(() => { screen.getByText('ocean').click(); });
    expect(screen.getByTestId('current').textContent).toBe('ocean');
    expect(document.documentElement.getAttribute('data-theme')).toBe('ocean');
    expect(localStorage.getItem('spid.theme')).toBe('ocean');
  });

  it('rehydrates the persisted theme on remount', () => {
    localStorage.setItem('spid.theme', 'md3-light');
    render(<ThemeProvider><Probe /></ThemeProvider>);
    expect(screen.getByTestId('current').textContent).toBe('md3-light');
    expect(document.documentElement.getAttribute('data-theme')).toBe('md3-light');
  });
  ```
  Run:
  ```bash
  cd packages/smart_pid_web && npm test -- src/theme/__tests__/ThemeProvider.test.tsx
  ```
  Expected: PASS already if Step 1 wiring is correct (persistence is core API). If FAIL, fix `setTheme` to write storage. Treat green here as a regression lock.

- [ ] **Step 2:** RED — write `src/components/shell/ThemeSwitcher.test.tsx`:
  ```tsx
  import { render, screen, fireEvent } from '@testing-library/react';
  import { describe, it, expect, beforeEach } from 'vitest';
  import { ThemeProvider } from '../../../theme/ThemeProvider';
  import { ThemeSwitcher } from './ThemeSwitcher';

  describe('ThemeSwitcher', () => {
    beforeEach(() => { localStorage.clear(); document.documentElement.removeAttribute('data-theme'); });

    it('lists all 5 themes and switches on select', () => {
      render(<ThemeProvider><ThemeSwitcher /></ThemeProvider>);
      const select = screen.getByLabelText('Theme') as HTMLSelectElement;
      expect(select.options).toHaveLength(5);
      fireEvent.change(select, { target: { value: 'dark-room' } });
      expect(document.documentElement.getAttribute('data-theme')).toBe('dark-room');
      expect(localStorage.getItem('spid.theme')).toBe('dark-room');
    });
  });
  ```
  Run RED:
  ```bash
  cd packages/smart_pid_web && npm test -- src/components/shell/ThemeSwitcher.test.tsx
  ```
  Expected: FAIL (`ThemeSwitcher` does not exist).

- [ ] **Step 3:** GREEN — create `src/components/shell/ThemeSwitcher.tsx`:
  ```tsx
  import { useTheme } from '../../theme/ThemeProvider';

  export function ThemeSwitcher() {
    const { theme, setTheme, themes } = useTheme();
    return (
      <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
        <span className="sr-only" aria-hidden={false}>Theme</span>
        <select
          aria-label="Theme"
          value={theme}
          onChange={(e) => setTheme(e.target.value as typeof theme)}
        >
          {themes.map((t) => (
            <option key={t.id} value={t.id}>{t.label}</option>
          ))}
        </select>
      </label>
    );
  }
  ```
  Run GREEN:
  ```bash
  cd packages/smart_pid_web && npm test -- src/components/shell/ThemeSwitcher.test.tsx
  ```
  Expected: PASS.

- [ ] **Step 4:** Mount `<ThemeSwitcher />` in `TopBar.tsx` (add to the existing right-aligned controls cluster; do not restructure the shell). Then run the shell tests:
  ```bash
  cd packages/smart_pid_web && npm test -- src/components/shell
  ```
  Expected: PASS (no regressions).

- [ ] **Step 5:** Commit.
  ```bash
  git add packages/smart_pid_web/src && git commit -m "feat(web): persisted theme switcher in top bar"
  ```

---

### Task 3: Complete the 4 remaining theme token blocks

**Files:** `src/theme/themes.css`

**Interfaces:** none (CSS). Token CONTRACT names are owned by `tokens.css` (Fatia 0+1); this task supplies VALUES only. ISA-101 is already shipped in Fatia 0+1 — do not duplicate it.

- [ ] **Step 1:** Append the **Dark Room** block to `themes.css` (values verbatim from design-system §2.1):
  ```css
  [data-theme="dark-room"] {
    --bg: #000000;
    --surface: #0D0D11;
    --surface-container: #0D0D11;
    --surface-container-high: #15151A;
    --field-bg: #050508;
    --border: #222228;
    --border-strong: #2C2C34;
    --divider: #1A1A20;
    --text: #B0B0B8;
    --text-secondary: #666670;
    --text-disabled: #3A3A42;
    --focus-ring: #8A8A94;
    --alarm-critical: #D92525; --alarm-critical-bg: #2A0A0A;
    --alarm-warning:  #D9A000; --alarm-warning-bg:  #2A2000;
    --alarm-diag:     #8A6AD9; --alarm-info:        #4A8AD9;
    --on-alarm: #F2E6E6;       --text-on-alarm: #F2E6E6;
    --state-running: #4A4A52;  --state-stopped: #666670;
    --state-error: #D92525;    --state-oos: #3A3A42;
    --trend-pv: #C8C8D0;       --trend-sp: #6E6E78;   --trend-co: #B07A2A;
    --trend-grid: #1A1A20;     --trend-axis: #3A3A42; --trend-bg: #000000;
    --bar-track: #050508;      --bar-fill: #4A4A52;   --bar-marker: #888890;
  }
  ```

- [ ] **Step 2:** Append the **MD3 dark** block (values verbatim from design-system §2.3 — note the shape tokens are exclusive to MD3):
  ```css
  [data-theme="md3-dark"] {
    --bg: #141218;
    --surface: #211F26;
    --surface-container: #1D1B20;
    --surface-container-high: #2B2930;
    --field-bg: #1D1B20;
    --border: #49454F;
    --border-strong: #938F99;
    --divider: #36343B;
    --text: #E6E0E9;
    --text-secondary: #CAC4D0;
    --text-disabled: #605D66;
    --focus-ring: #CAC4D0;
    --alarm-critical: #F2B8B5; --alarm-critical-bg: #8C1D18;
    --alarm-warning:  #FFDC99; --alarm-warning-bg:  #4D3300;
    --alarm-diag:     #D0BCFF; --alarm-info:        #99CBFF;
    --on-alarm: #F9DEDC;       --text-on-alarm: #601410;
    --state-running: #938F99;  --state-stopped: #CAC4D0;
    --state-error: #F2B8B5;    --state-oos: #605D66;
    --trend-pv: #E6E0E9;       --trend-sp: #99CBFF;  --trend-co: #FFD8A8;
    --trend-grid: #36343B;     --trend-axis: #49454F; --trend-bg: #141218;
    --bar-track: #2B2930;      --bar-fill: #938F99;  --bar-marker: #CAC4D0;
    --radius-card: 12px; --radius-control: 8px; --radius-pill: 999px;
  }
  ```

- [ ] **Step 3:** Append the **MD3 light** block (values verbatim from design-system §2.4 — only light theme; no pure-white background):
  ```css
  [data-theme="md3-light"] {
    --bg: #FDF8FD;
    --surface: #F7F2FA;
    --surface-container: #F2ECF4;
    --surface-container-high: #ECE6F0;
    --field-bg: #FFFFFF;
    --border: #CAC4D0;
    --border-strong: #79747E;
    --divider: #E0DAE4;
    --text: #1D1B20;
    --text-secondary: #49454F;
    --text-disabled: #9A949F;
    --focus-ring: #49454F;
    --alarm-critical: #B3261E; --alarm-critical-bg: #F9DEDC;
    --alarm-warning:  #8A5000; --alarm-warning-bg:  #FFE2BC;
    --alarm-diag:     #6750A4; --alarm-info:        #1E5D9E;
    --on-alarm: #FFFFFF;       --text-on-alarm: #FFFFFF;
    --state-running: #79747E;  --state-stopped: #49454F;
    --state-error: #B3261E;    --state-oos: #9A949F;
    --trend-pv: #1D1B20;       --trend-sp: #1E5D9E;  --trend-co: #9A5B00;
    --trend-grid: #E0DAE4;     --trend-axis: #CAC4D0; --trend-bg: #FFFFFF;
    --bar-track: #ECE6F0;      --bar-fill: #79747E;  --bar-marker: #49454F;
    --radius-card: 12px; --radius-control: 8px; --radius-pill: 999px;
  }
  ```

- [ ] **Step 4:** Append the **Ocean** block (values verbatim from design-system §2.5 — saturation lives only in surfaces/chrome, never in process-state meaning):
  ```css
  [data-theme="ocean"] {
    --bg: #0A1620;
    --surface: #0F2030;
    --surface-container: #0F2030;
    --surface-container-high: #16304A;
    --field-bg: #081019;
    --border: #1E3A52;
    --border-strong: #2A4E6E;
    --divider: #16283A;
    --text: #D6E2EC;
    --text-secondary: #7E97AC;
    --text-disabled: #44586A;
    --focus-ring: #8FB6D6;
    --alarm-critical: #FF4D4D; --alarm-critical-bg: #3A0E0E;
    --alarm-warning:  #FFB020; --alarm-warning-bg:  #3A2A00;
    --alarm-diag:     #9B6BFF; --alarm-info:        #45B0FF;
    --on-alarm: #FFFFFF;       --text-on-alarm: #081019;
    --state-running: #5E7E96;  --state-stopped: #7E97AC;
    --state-error: #FF4D4D;    --state-oos: #44586A;
    --trend-pv: #CFE0EC;       --trend-sp: #45B0FF;  --trend-co: #FFB020;
    --trend-grid: #16283A;     --trend-axis: #1E3A52; --trend-bg: #081019;
    --bar-track: #081019;      --bar-fill: #5E7E96;  --bar-marker: #8FB6D6;
  }
  ```

- [ ] **Step 5:** Verify the stylesheet parses (the build catches malformed CSS) and run the existing suite to confirm no regressions:
  ```bash
  cd packages/smart_pid_web && npm run build && npm test -- src/theme
  ```
  Expected: build succeeds; theme tests still PASS.

- [ ] **Step 6:** Commit.
  ```bash
  git add packages/smart_pid_web/src/theme/themes.css && git commit -m "feat(web): complete dark-room, md3-dark, md3-light, ocean theme tokens"
  ```

---

### Task 4: Per-theme contrast gate (WCAG AA + alarm matrix)

**Files:** `src/theme/themeContrast.ts`, `src/theme/__tests__/contrast.test.ts`

**Interfaces:**
```ts
// Canonical per-theme token VALUE map used for build-time contrast assertions.
// Mirrors themes.css exactly; the test asserts the pairs designers committed to.
export interface ThemePalette {
  bg: string; surface: string; surfaceHigh: string;
  text: string; textSecondary: string;
  alarmCritical: string; alarmWarning: string; alarmDiag: string;
  onAlarm: string;
}
export const PALETTES: Record<ThemeId, ThemePalette>;
```

- [ ] **Step 1:** Add the dependency (pure-JS, no DOM needed):
  ```bash
  cd packages/smart_pid_web && npm install --save-dev wcag-contrast
  ```
  Expected: `wcag-contrast` added to devDependencies.

- [ ] **Step 2:** RED — write `src/theme/__tests__/contrast.test.ts`. This is the HARD GATE: normal text ≥ 4.5:1 against its surface for every theme, plus the §8.4 alarm matrix (CRIT vs background, CRIT distinguishable from WARN by luminance).
  ```ts
  import { describe, it, expect } from 'vitest';
  // @ts-expect-error — wcag-contrast ships no types
  import { hex as contrastHex } from 'wcag-contrast';
  import { PALETTES, type ThemeId } from '../themeContrast';

  // relative luminance per WCAG, for the CRIT-vs-WARN luminance-distinct check
  function luminance(hexColor: string): number {
    const h = hexColor.replace('#', '');
    const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
    const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
  }

  const THEMES: ThemeId[] = ['isa101', 'dark-room', 'md3-dark', 'md3-light', 'ocean'];

  describe('per-theme WCAG AA normal-text contrast (>= 4.5:1)', () => {
    it.each(THEMES)('%s: --text on --surface >= 4.5:1', (id) => {
      const p = PALETTES[id];
      expect(contrastHex(p.text, p.surface)).toBeGreaterThanOrEqual(4.5);
    });
    it.each(THEMES)('%s: --text on --bg >= 4.5:1', (id) => {
      const p = PALETTES[id];
      expect(contrastHex(p.text, p.bg)).toBeGreaterThanOrEqual(4.5);
    });
  });

  describe('§8.4 cross-theme alarm matrix', () => {
    it.each(THEMES)('%s: CRIT vs surface meets threshold', (id) => {
      const p = PALETTES[id];
      // matrix floor is 4.5 (ISA-101 demands >= 5; assert the higher bar there)
      const floor = id === 'isa101' ? 5 : 4.5;
      expect(contrastHex(p.alarmCritical, p.surface)).toBeGreaterThanOrEqual(floor);
    });
    it.each(THEMES)('%s: CRIT and WARN are luminance-distinct (do not rely on hue alone)', (id) => {
      const p = PALETTES[id];
      const dL = Math.abs(luminance(p.alarmCritical) - luminance(p.alarmWarning));
      expect(dL).toBeGreaterThan(0.05);
    });
  });
  ```
  Run RED:
  ```bash
  cd packages/smart_pid_web && npm test -- src/theme/__tests__/contrast.test.ts
  ```
  Expected: FAIL (`themeContrast` not found).

- [ ] **Step 3:** GREEN — create `src/theme/themeContrast.ts`. The `PALETTES` map mirrors `themes.css` exactly (same hex values), so the test asserts the colors designers actually committed. For each theme, `surface` is the card surface used in the §8.4 matrix; ISA-101's matrix row uses `#2D2D30` (which is its `--surface`).
  ```ts
  import type { ThemeId } from './ThemeProvider';
  export type { ThemeId };

  export interface ThemePalette {
    bg: string; surface: string; surfaceHigh: string;
    text: string; textSecondary: string;
    alarmCritical: string; alarmWarning: string; alarmDiag: string;
    onAlarm: string;
  }

  export const PALETTES: Record<ThemeId, ThemePalette> = {
    isa101: {
      bg: '#1E1E1E', surface: '#2D2D30', surfaceHigh: '#333337',
      text: '#E0E0E0', textSecondary: '#ABABAB',
      alarmCritical: '#FF3333', alarmWarning: '#FF8800', alarmDiag: '#AA55FF', onAlarm: '#FFFFFF',
    },
    'dark-room': {
      bg: '#000000', surface: '#0D0D11', surfaceHigh: '#15151A',
      text: '#B0B0B8', textSecondary: '#666670',
      alarmCritical: '#D92525', alarmWarning: '#D9A000', alarmDiag: '#8A6AD9', onAlarm: '#F2E6E6',
    },
    'md3-dark': {
      bg: '#141218', surface: '#211F26', surfaceHigh: '#2B2930',
      text: '#E6E0E9', textSecondary: '#CAC4D0',
      alarmCritical: '#F2B8B5', alarmWarning: '#FFDC99', alarmDiag: '#D0BCFF', onAlarm: '#F9DEDC',
    },
    'md3-light': {
      bg: '#FDF8FD', surface: '#F7F2FA', surfaceHigh: '#ECE6F0',
      text: '#1D1B20', textSecondary: '#49454F',
      alarmCritical: '#B3261E', alarmWarning: '#8A5000', alarmDiag: '#6750A4', onAlarm: '#FFFFFF',
    },
    ocean: {
      bg: '#0A1620', surface: '#0F2030', surfaceHigh: '#16304A',
      text: '#D6E2EC', textSecondary: '#7E97AC',
      alarmCritical: '#FF4D4D', alarmWarning: '#FFB020', alarmDiag: '#9B6BFF', onAlarm: '#FFFFFF',
    },
  };
  ```
  Run GREEN:
  ```bash
  cd packages/smart_pid_web && npm test -- src/theme/__tests__/contrast.test.ts
  ```
  Expected: PASS. If any pair falls below threshold, that is a real design-system defect — STOP and report it (do NOT loosen the threshold). The committed §2.x / §8.4 values are designed to pass.

- [ ] **Step 4:** Commit.
  ```bash
  git add packages/smart_pid_web/src/theme packages/smart_pid_web/package.json packages/smart_pid_web/package-lock.json && git commit -m "feat(web): per-theme WCAG AA + alarm-matrix contrast gate"
  ```

---

### Task 5: Pure scale-mapping helper (PV → bar fraction)

**Files:** `src/lib/scale.ts`, `src/lib/scale.test.ts`

**Interfaces:**
```ts
export interface Scale { euMin: number; euMax: number; unit: string }
/** Maps a value to [0,1] fraction of the scale span, clamped. */
export function valueToFraction(value: number, scale: Scale): number;
```

- [ ] **Step 1:** RED — write `src/lib/scale.test.ts`. This locks the measurable PV→position mapping the AnalogBar relies on.
  ```ts
  import { describe, it, expect } from 'vitest';
  import { valueToFraction } from './scale';

  const scale = { euMin: 0, euMax: 200, unit: '°C' };

  describe('valueToFraction', () => {
    it('maps mid-span to 0.5', () => {
      expect(valueToFraction(100, scale)).toBeCloseTo(0.5, 5);
    });
    it('maps min to 0 and max to 1', () => {
      expect(valueToFraction(0, scale)).toBe(0);
      expect(valueToFraction(200, scale)).toBe(1);
    });
    it('clamps below min and above max', () => {
      expect(valueToFraction(-50, scale)).toBe(0);
      expect(valueToFraction(250, scale)).toBe(1);
    });
    it('monotonic: higher PV -> higher fraction', () => {
      expect(valueToFraction(150, scale)).toBeGreaterThan(valueToFraction(50, scale));
    });
    it('handles a non-zero min span (e.g. 4-20 range)', () => {
      expect(valueToFraction(12, { euMin: 4, euMax: 20, unit: 'mA' })).toBeCloseTo(0.5, 5);
    });
    it('degenerate span returns 0 (no div-by-zero)', () => {
      expect(valueToFraction(5, { euMin: 10, euMax: 10, unit: '' })).toBe(0);
    });
  });
  ```
  Run RED:
  ```bash
  cd packages/smart_pid_web && npm test -- src/lib/scale.test.ts
  ```
  Expected: FAIL (`scale.ts` not found).

- [ ] **Step 2:** GREEN — create `src/lib/scale.ts`:
  ```ts
  export interface Scale {
    euMin: number;
    euMax: number;
    unit: string;
  }

  export function valueToFraction(value: number, scale: Scale): number {
    const span = scale.euMax - scale.euMin;
    if (span <= 0) return 0;
    const f = (value - scale.euMin) / span;
    return f < 0 ? 0 : f > 1 ? 1 : f;
  }
  ```
  Run GREEN:
  ```bash
  cd packages/smart_pid_web && npm test -- src/lib/scale.test.ts
  ```
  Expected: PASS.

- [ ] **Step 3:** Commit.
  ```bash
  git add packages/smart_pid_web/src/lib/scale.ts packages/smart_pid_web/src/lib/scale.test.ts && git commit -m "feat(web): pure pv-to-fraction scale mapping helper"
  ```

---

### Task 6: Instrument AnalogBar (value/scale/alarm reflect real data)

**Files:** `src/components/AnalogBar.tsx`, `src/components/AnalogBar.test.tsx`

**Interfaces:**
```tsx
export type AlarmLevel = 'normal' | 'warning' | 'critical';
export interface AnalogBarProps {
  label: string;            // 'PV' | 'SP' | 'CO'
  value: number;
  scale: { euMin: number; euMax: number; unit: string };
  spValue?: number;         // optional SP marker (PV-bar only)
  alarm?: AlarmLevel;       // default 'normal'
  size?: 'card' | 'faceplate';
}
export function AnalogBar(props: AnalogBarProps): JSX.Element;
```
(Per design-system §5.1: `role="meter"`, `aria-valuemin/max/now`, alarm changes the FILL color abruptly and bumps the numeric weight; the rest of the card stays neutral. SP marker only on PV-bar. Instrument the canonical file — do not fork.)

- [ ] **Step 1:** RED — write `src/components/AnalogBar.test.tsx`. The two REQUIRED instrumented assertions: (a) bar position maps measurably to PV vs scale; (b) alarm coloring triggers ONLY on abnormal state.
  ```tsx
  import { render, screen } from '@testing-library/react';
  import { describe, it, expect } from 'vitest';
  import { AnalogBar } from './AnalogBar';

  const scale = { euMin: 0, euMax: 200, unit: '°C' };

  function fillWidth(el: HTMLElement): number {
    // fill is a child with inline width: NN% (or scaleX transform); read the % number
    const fill = el.querySelector('[data-testid="bar-fill"]') as HTMLElement;
    const w = fill.style.width || fill.style.transform;
    const m = /([\d.]+)/.exec(w);
    return m ? parseFloat(m[1]) : NaN;
  }

  describe('AnalogBar instrumentation', () => {
    it('meter exposes aria value bounds and current value', () => {
      render(<AnalogBar label="PV" value={150.2} scale={scale} />);
      const meter = screen.getByRole('meter');
      expect(meter).toHaveAttribute('aria-valuemin', '0');
      expect(meter).toHaveAttribute('aria-valuemax', '200');
      expect(meter).toHaveAttribute('aria-valuenow', '150.2');
    });

    it('fill position maps measurably to PV vs scale (50 < 100 < 150)', () => {
      const { rerender, container } = render(<AnalogBar label="PV" value={50} scale={scale} />);
      const low = fillWidth(container);
      rerender(<AnalogBar label="PV" value={100} scale={scale} />);
      const mid = fillWidth(container);
      rerender(<AnalogBar label="PV" value={150} scale={scale} />);
      const high = fillWidth(container);
      expect(mid).toBeCloseTo(50, 1);   // 100/200 = 50%
      expect(low).toBeLessThan(mid);
      expect(mid).toBeLessThan(high);
    });

    it('renders neutral fill when alarm is normal (no alarm token applied)', () => {
      const { container } = render(<AnalogBar label="PV" value={100} scale={scale} alarm="normal" />);
      const fill = container.querySelector('[data-testid="bar-fill"]') as HTMLElement;
      expect(fill.getAttribute('data-alarm')).toBe('normal');
    });

    it('applies critical alarm fill ONLY on abnormal state', () => {
      const { container } = render(<AnalogBar label="PV" value={195} scale={scale} alarm="critical" />);
      const fill = container.querySelector('[data-testid="bar-fill"]') as HTMLElement;
      expect(fill.getAttribute('data-alarm')).toBe('critical');
      const value = screen.getByTestId('bar-value');
      expect(value).toHaveStyle({ fontWeight: '600' });
    });

    it('shows SP marker only when spValue is given (PV-bar signature)', () => {
      const { rerender, container } = render(<AnalogBar label="PV" value={150} scale={scale} />);
      expect(container.querySelector('[data-testid="sp-marker"]')).toBeNull();
      rerender(<AnalogBar label="PV" value={150} scale={scale} spValue={152} />);
      expect(container.querySelector('[data-testid="sp-marker"]')).not.toBeNull();
    });
  });
  ```
  Run RED:
  ```bash
  cd packages/smart_pid_web && npm test -- src/components/AnalogBar.test.tsx
  ```
  Expected: FAIL (uninstrumented AnalogBar lacks `role="meter"`, `data-testid` hooks, alarm/SP behavior).

- [ ] **Step 2:** GREEN — instrument `src/components/AnalogBar.tsx`. Keep the Fatia 0+1 visual shell; add the data-driven fill, ARIA, alarm fill switch, and SP marker. Colors come from tokens (alarm switches `--bar-fill` → `--alarm-*`); position uses `valueToFraction`.
  ```tsx
  import { valueToFraction, type Scale } from '../lib/scale';

  export type AlarmLevel = 'normal' | 'warning' | 'critical';

  export interface AnalogBarProps {
    label: string;
    value: number;
    scale: Scale;
    spValue?: number;
    alarm?: AlarmLevel;
    size?: 'card' | 'faceplate';
  }

  const ALARM_FILL: Record<AlarmLevel, string> = {
    normal: 'var(--bar-fill)',
    warning: 'var(--alarm-warning)',
    critical: 'var(--alarm-critical)',
  };

  export function AnalogBar({
    label, value, scale, spValue, alarm = 'normal', size = 'card',
  }: AnalogBarProps) {
    const fraction = valueToFraction(value, scale);
    const pct = (fraction * 100).toFixed(2);
    const spPct = spValue !== undefined
      ? (valueToFraction(spValue, scale) * 100).toFixed(2)
      : null;
    const trackHeight = size === 'faceplate' ? 14 : 8;
    const showSp = label === 'PV' && spPct !== null;

    return (
      <div className="analog-bar" data-size={size} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span className="analog-bar__label" style={{ color: 'var(--text-secondary)' }}>{label}</span>
        <div
          className="analog-bar__track"
          role="meter"
          aria-label={`${label} ${value} ${scale.unit}`}
          aria-valuemin={scale.euMin}
          aria-valuemax={scale.euMax}
          aria-valuenow={value}
          style={{
            position: 'relative', flex: 1, height: trackHeight,
            background: 'var(--bar-track)', borderRadius: 'var(--radius-pill, 0)',
          }}
        >
          <div
            data-testid="bar-fill"
            data-alarm={alarm}
            style={{
              position: 'absolute', left: 0, top: 0, bottom: 0,
              width: `${pct}%`,
              background: ALARM_FILL[alarm],
            }}
          />
          {showSp && (
            <span
              data-testid="sp-marker"
              aria-hidden
              style={{
                position: 'absolute', top: -3, left: `${spPct}%`,
                width: 0, height: 0,
                borderLeft: '4px solid transparent',
                borderRight: '4px solid transparent',
                borderTop: '5px solid var(--bar-marker)',
                transform: 'translateX(-50%)',
              }}
            />
          )}
        </div>
        <span
          data-testid="bar-value"
          className="analog-bar__value"
          style={{
            color: 'var(--text)',
            fontVariantNumeric: 'tabular-nums',
            fontWeight: alarm === 'normal' ? 400 : 600,
          }}
        >
          {value.toFixed(1)} <span style={{ color: 'var(--text-secondary)' }}>{scale.unit}</span>
        </span>
      </div>
    );
  }
  ```
  Run GREEN:
  ```bash
  cd packages/smart_pid_web && npm test -- src/components/AnalogBar.test.tsx
  ```
  Expected: PASS.

- [ ] **Step 3:** Run the full suite to confirm the ControllerCard (which renders AnalogBar) still passes:
  ```bash
  cd packages/smart_pid_web && npm test -- src/components
  ```
  Expected: PASS (if ControllerCard asserted a stale AnalogBar API, fix the CARD's usage — do not weaken AnalogBar).

- [ ] **Step 4:** Commit.
  ```bash
  git add packages/smart_pid_web/src/components/AnalogBar.tsx packages/smart_pid_web/src/components/AnalogBar.test.tsx && git commit -m "feat(web): instrument AnalogBar with data-driven value/scale/alarm"
  ```

---

### Task 7: uPlot per-palette theming

**Files:** `src/lib/uplotTheme.ts`, `src/lib/uplotTheme.test.ts`

**Interfaces:**
```ts
/** Read --trend-* tokens from a resolved CSSStyleDeclaration and build a uPlot opts fragment (§7.1). */
export interface TrendTokens {
  pv: string; sp: string; co: string; grid: string; axis: string; bg: string;
}
export function readTrendTokens(style: CSSStyleDeclaration): TrendTokens;
export function buildUplotTheme(tokens: TrendTokens): {
  axesStroke: string; gridStroke: string; bg: string;
  series: { pv: object; sp: object; co: object };
};
```
(Per §7.1: axes/grid/ticks from `--trend-axis`/`--trend-grid`, bg from `--trend-bg`; series PV `{stroke, width:1.5}`, SP `{stroke, width:1.5, dash:[6,4]}`, CO `{stroke, width:1.5, scale:'co'}`; NO `fill` (zero area-fill).)

- [ ] **Step 1:** RED — write `src/lib/uplotTheme.test.ts`:
  ```ts
  import { describe, it, expect } from 'vitest';
  import { buildUplotTheme, type TrendTokens } from './uplotTheme';

  const tokens: TrendTokens = {
    pv: '#E0E0E0', sp: '#33AAFF', co: '#FFB000',
    grid: '#3A3A3D', axis: '#57575B', bg: '#252526',
  };

  describe('buildUplotTheme (§7.1)', () => {
    const t = buildUplotTheme(tokens);

    it('maps axis + grid + bg from trend tokens', () => {
      expect(t.axesStroke).toBe('#57575B');
      expect(t.gridStroke).toBe('#3A3A3D');
      expect(t.bg).toBe('#252526');
    });
    it('PV/SP/CO series use the right strokes, SP is dashed, CO uses co scale', () => {
      expect(t.series.pv).toMatchObject({ stroke: '#E0E0E0', width: 1.5 });
      expect(t.series.sp).toMatchObject({ stroke: '#33AAFF', width: 1.5, dash: [6, 4] });
      expect(t.series.co).toMatchObject({ stroke: '#FFB000', width: 1.5, scale: 'co' });
    });
    it('no area fill on any series', () => {
      for (const s of Object.values(t.series)) {
        expect((s as Record<string, unknown>).fill).toBeUndefined();
      }
    });
  });
  ```
  Run RED:
  ```bash
  cd packages/smart_pid_web && npm test -- src/lib/uplotTheme.test.ts
  ```
  Expected: FAIL (file/function not found, or returns wrong shape).

- [ ] **Step 2:** GREEN — create/extend `src/lib/uplotTheme.ts`:
  ```ts
  export interface TrendTokens {
    pv: string; sp: string; co: string;
    grid: string; axis: string; bg: string;
  }

  export function readTrendTokens(style: CSSStyleDeclaration): TrendTokens {
    const get = (n: string) => style.getPropertyValue(n).trim();
    return {
      pv: get('--trend-pv'), sp: get('--trend-sp'), co: get('--trend-co'),
      grid: get('--trend-grid'), axis: get('--trend-axis'), bg: get('--trend-bg'),
    };
  }

  export function buildUplotTheme(tokens: TrendTokens) {
    return {
      axesStroke: tokens.axis,
      gridStroke: tokens.grid,
      bg: tokens.bg,
      series: {
        pv: { stroke: tokens.pv, width: 1.5 },
        sp: { stroke: tokens.sp, width: 1.5, dash: [6, 4] },
        co: { stroke: tokens.co, width: 1.5, scale: 'co' },
      },
    };
  }
  ```
  Run GREEN:
  ```bash
  cd packages/smart_pid_web && npm test -- src/lib/uplotTheme.test.ts
  ```
  Expected: PASS.

- [ ] **Step 3:** Wire `RealtimeTrend.tsx` to call `readTrendTokens(getComputedStyle(document.documentElement))` + `buildUplotTheme(...)` on mount AND on theme change (re-run when the `data-theme` attribute changes; a `MutationObserver` on `documentElement` or a `useTheme()` dependency both satisfy §7.1). Keep the canonical chart component — only feed it themed opts. Run:
  ```bash
  cd packages/smart_pid_web && npm test -- src/components/RealtimeTrend* 2>/dev/null; npm run build
  ```
  Expected: build succeeds; existing RealtimeTrend tests (if any) PASS.

- [ ] **Step 4:** Commit.
  ```bash
  git add packages/smart_pid_web/src/lib/uplotTheme.ts packages/smart_pid_web/src/lib/uplotTheme.test.ts packages/smart_pid_web/src/components/RealtimeTrend.tsx && git commit -m "feat(web): theme uPlot per palette from trend tokens"
  ```

---

### Task 8: Faceplate widget — render by mode/state

**Files:** `src/components/Faceplate.tsx`, `src/components/Faceplate.test.tsx`

**Interfaces:**
```tsx
import type { ControllerMode } from '../api/types'; // 8 modes + BYPASS (from generated openapi or a local union)
export const CONTROLLER_MODES = ['OOS','IMAN','LO','MAN','AUTO','CAS','RCAS','ROUT'] as const;

export interface FaceplateProps {
  controllerId: number;
  tag: string;
  description?: string;
  scale: { euMin: number; euMax: number; unit: string }; // from REST ControllerResponse.pv_scale
  // live status comes from useRealtime().lastStatus.get(controllerId) inside the component
}
export function Faceplate(props: FaceplateProps): JSX.Element;
```
Per design-system §5.3: header TAG (mono 700) + description + loop state; primary PV in `--text-3xl`, SP/CO in `--text-xl`; faceplate-size AnalogBars (PV with SP marker, plus SP and CO bars); segmented mode control with all 8 modes (RCas/ROut may sit in an overflow); SP numeric stepper; manual CO slider ENABLED ONLY in MAN; `apply-tuning` button (strong border, NOT alarm color) opening the Fatia 2 confirmation modal. The Faceplate reads `mode`/`pv`/`sp`/`co` from the `status` frame. It MUST reuse Fatia 2 command hooks — do NOT duplicate mutation logic.

- [ ] **Step 1:** RED — write `src/components/Faceplate.test.tsx`. Mock `useRealtime` to supply a `lastStatus` map, and mock the Fatia 2 command hooks to assert wiring without re-implementing them.
  ```tsx
  import { render, screen, fireEvent } from '@testing-library/react';
  import { describe, it, expect, vi, beforeEach } from 'vitest';

  const setMode = vi.fn();
  const setSetpoint = vi.fn();
  const setOutput = vi.fn();
  const applyTuning = vi.fn();

  // Mock the canonical realtime hook
  const statusMap = new Map<number, any>();
  vi.mock('../realtime/useRealtime', () => ({
    useRealtime: () => ({
      connected: true,
      lastStatus: statusMap,
      lastStats: new Map(),
      subscribe: () => () => {},
      onResync: () => () => {},
    }),
  }));

  // Mock Fatia 2 command hooks (reuse, do not duplicate)
  vi.mock('../features/commands/hooks', () => ({
    useSetMode: () => ({ mutate: setMode, isPending: false }),
    useSetSetpoint: () => ({ mutate: setSetpoint, isPending: false }),
    useSetOutput: () => ({ mutate: setOutput, isPending: false }),
    useApplyTuning: () => ({ mutate: applyTuning, isPending: false }),
  }));

  import { Faceplate } from './Faceplate';

  const scale = { euMin: 0, euMax: 200, unit: '°C' };
  const baseStatus = {
    pv: 150.2, sp: 152.0, co: 64.0, bkcal_in: 0, bkcal_out: 0,
    mode: 'AUTO', kp: 1, ti: 30, td: 0, integral_val: 0, timestamp: 0,
  };

  describe('Faceplate', () => {
    beforeEach(() => {
      statusMap.clear();
      statusMap.set(5, { ...baseStatus });
      vi.clearAllMocks();
    });

    it('renders PV/SP/CO and the live tag', () => {
      render(<Faceplate controllerId={5} tag="PIC-005" scale={scale} />);
      expect(screen.getByText('PIC-005')).toBeInTheDocument();
      expect(screen.getByText(/150\.2/)).toBeInTheDocument();
      expect(screen.getByText(/152\.0/)).toBeInTheDocument();
      expect(screen.getByText(/64\.0/)).toBeInTheDocument();
    });

    it('offers all 8 controller modes and highlights the active one', () => {
      render(<Faceplate controllerId={5} tag="PIC-005" scale={scale} />);
      for (const m of ['OOS','IMAN','LO','MAN','AUTO','CAS','RCAS','ROUT']) {
        expect(screen.getByRole('button', { name: new RegExp(`^${m}$`, 'i') })).toBeInTheDocument();
      }
      expect(screen.getByRole('button', { name: /^AUTO$/i })).toHaveAttribute('aria-pressed', 'true');
    });

    it('issues a mode command via the Fatia 2 hook (no duplicated logic)', () => {
      render(<Faceplate controllerId={5} tag="PIC-005" scale={scale} />);
      fireEvent.click(screen.getByRole('button', { name: /^MAN$/i }));
      expect(setMode).toHaveBeenCalledWith({ controller_id: 5, mode: 'MAN' });
    });

    it('disables the manual CO control unless in MAN mode', () => {
      const { rerender } = render(<Faceplate controllerId={5} tag="PIC-005" scale={scale} />);
      expect(screen.getByLabelText('Manual CO')).toBeDisabled();
      statusMap.set(5, { ...baseStatus, mode: 'MAN' });
      rerender(<Faceplate controllerId={5} tag="PIC-005" scale={scale} />);
      expect(screen.getByLabelText('Manual CO')).not.toBeDisabled();
    });

    it('renders the PV AnalogBar instrumented from status (meter present)', () => {
      render(<Faceplate controllerId={5} tag="PIC-005" scale={scale} />);
      const meters = screen.getAllByRole('meter');
      expect(meters.length).toBeGreaterThanOrEqual(1);
      expect(meters[0]).toHaveAttribute('aria-valuenow', '150.2');
    });

    it('shows a waiting state when no status frame is available yet', () => {
      statusMap.clear();
      render(<Faceplate controllerId={5} tag="PIC-005" scale={scale} />);
      expect(screen.getByText(/no data|aguardando|waiting/i)).toBeInTheDocument();
    });
  });
  ```
  Run RED:
  ```bash
  cd packages/smart_pid_web && npm test -- src/components/Faceplate.test.tsx
  ```
  Expected: FAIL (`Faceplate` not found).

- [ ] **Step 2:** GREEN — create `src/components/Faceplate.tsx`. Read live data from `useRealtime().lastStatus.get(controllerId)`; import command hooks from the merged Fatia 2 location (`../features/commands/hooks` — adjust the import path to wherever Fatia 2 placed them). Render header, primary readouts, three faceplate-size AnalogBars, the 8-mode segmented control, the MAN-gated manual CO, the SP stepper, and the apply-tuning button.
  ```tsx
  import { useRealtime } from '../realtime/useRealtime';
  import { useSetMode, useSetSetpoint, useSetOutput, useApplyTuning } from '../features/commands/hooks';
  import { AnalogBar } from './AnalogBar';
  import type { Scale } from '../lib/scale';

  export const CONTROLLER_MODES = ['OOS','IMAN','LO','MAN','AUTO','CAS','RCAS','ROUT'] as const;
  export type ControllerMode = (typeof CONTROLLER_MODES)[number];

  export interface FaceplateProps {
    controllerId: number;
    tag: string;
    description?: string;
    scale: Scale;
  }

  export function Faceplate({ controllerId, tag, description, scale }: FaceplateProps) {
    const { lastStatus } = useRealtime();
    const status = lastStatus.get(controllerId);
    const setMode = useSetMode();
    const setSetpoint = useSetSetpoint();
    const setOutput = useSetOutput();
    const applyTuning = useApplyTuning();

    if (!status) {
      return (
        <aside className="faceplate" aria-label={`Faceplate ${tag}`}>
          <header><strong style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{tag}</strong></header>
          <p>Waiting for data…</p>
        </aside>
      );
    }

    const mode = status.mode as ControllerMode;
    const isMan = mode === 'MAN';

    return (
      <aside className="faceplate" aria-label={`Faceplate ${tag}`}
        style={{ width: 'clamp(360px, 30vw, 420px)', background: 'var(--surface)', color: 'var(--text)' }}>
        <header>
          <strong style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 'var(--text-xl)' }}>{tag}</strong>
          {description && <span style={{ color: 'var(--text-secondary)' }}> · {description}</span>}
        </header>

        <div className="faceplate__readout">
          <div style={{ fontSize: 'var(--text-3xl)', fontVariantNumeric: 'tabular-nums' }}>
            {status.pv.toFixed(1)} <span style={{ color: 'var(--text-secondary)' }}>{scale.unit}</span>
          </div>
          <div style={{ fontSize: 'var(--text-xl)', fontVariantNumeric: 'tabular-nums' }}>
            SP {status.sp.toFixed(1)} · CO {status.co.toFixed(1)}%
          </div>
        </div>

        <AnalogBar label="PV" value={status.pv} scale={scale} spValue={status.sp} size="faceplate" />
        <AnalogBar label="SP" value={status.sp} scale={scale} size="faceplate" />
        <AnalogBar label="CO" value={status.co} scale={{ euMin: 0, euMax: 100, unit: '%' }} size="faceplate" />

        <div role="group" aria-label="Controller mode" className="faceplate__modes">
          {CONTROLLER_MODES.map((m) => (
            <button
              key={m}
              type="button"
              aria-pressed={m === mode}
              onClick={() => setMode.mutate({ controller_id: controllerId, mode: m })}
            >
              {m}
            </button>
          ))}
        </div>

        <label>
          SP
          <input
            type="number"
            aria-label="Setpoint"
            defaultValue={status.sp}
            onBlur={(e) => setSetpoint.mutate({ controller_id: controllerId, value: Number(e.target.value) })}
          />
        </label>

        <label>
          Manual CO
          <input
            type="range" min={0} max={100} step={0.5}
            aria-label="Manual CO"
            defaultValue={status.co}
            disabled={!isMan}
            onMouseUp={(e) => setOutput.mutate({ controller_id: controllerId, value: Number((e.target as HTMLInputElement).value) })}
          />
        </label>

        <button
          type="button"
          className="faceplate__apply-tuning"
          style={{ border: '1px solid var(--border-strong)' }}
          onClick={() => applyTuning.mutate({ controller_id: controllerId })}
        >
          Apply tuning…
        </button>
      </aside>
    );
  }
  ```
  > Note: `setMode.mutate`/`setSetpoint.mutate` payload shapes must match the Fatia 2 hook contracts. If Fatia 2 used a different argument shape (e.g. positional, or `{ id, value }`), adapt the call sites and the test mocks together — do NOT add a translation layer that re-implements command behavior. The `apply-tuning` confirmation modal is OWNED by Fatia 2; this button just triggers that flow.

  Run GREEN:
  ```bash
  cd packages/smart_pid_web && npm test -- src/components/Faceplate.test.tsx
  ```
  Expected: PASS.

- [ ] **Step 3:** Confirm the Fatia 2 hook import path is correct against the merged code:
  ```bash
  cd packages/smart_pid_web && grep -rn "useSetMode\|useSetSetpoint\|useApplyTuning" src/features src/components --include=*.ts --include=*.tsx | grep -v Faceplate
  ```
  Expected: the hooks exist at the imported path. If the path differs, fix the import in `Faceplate.tsx` and the `vi.mock` target in the test, then re-run Step 2.

- [ ] **Step 4:** Commit.
  ```bash
  git add packages/smart_pid_web/src/components/Faceplate.tsx packages/smart_pid_web/src/components/Faceplate.test.tsx && git commit -m "feat(web): faceplate widget consuming status WS + Fatia 2 commands"
  ```

---

### Task 9: Visual regression snapshots per theme + faceplate (Playwright)

**Files:** `e2e/themes.spec.ts`, `e2e/faceplate.spec.ts`

**Interfaces:** none. Uses the running dev server + a seeded/mocked status frame. Breakpoints: 320, 768, 1024, 1440.

- [ ] **Step 1:** Write `e2e/themes.spec.ts` — iterate all 5 themes × 4 breakpoints, switch theme via the persisted switcher, snapshot the dashboard. Light theme (`md3-light`) and dark themes both covered.
  ```ts
  import { test, expect } from '@playwright/test';

  const THEMES = ['isa101', 'dark-room', 'md3-dark', 'md3-light', 'ocean'] as const;
  const WIDTHS = [320, 768, 1024, 1440] as const;

  test.describe('theme visual parity', () => {
    for (const theme of THEMES) {
      for (const width of WIDTHS) {
        test(`${theme} @ ${width}`, async ({ page }) => {
          await page.addInitScript((t) => localStorage.setItem('spid.theme', t), theme);
          await page.setViewportSize({ width, height: 900 });
          await page.goto('/');
          // wait for the shell to mount under the chosen theme
          await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
          await expect(page).toHaveScreenshot(`dashboard-${theme}-${width}.png`, {
            maxDiffPixelRatio: 0.02,
          });
        });
      }
    }
  });
  ```

- [ ] **Step 2:** Write `e2e/faceplate.spec.ts` — open the faceplate for a controller, assert PV/SP/CO render and snapshot it in the default theme.
  ```ts
  import { test, expect } from '@playwright/test';

  test('faceplate renders PV/SP/CO and mode control', async ({ page }) => {
    await page.goto('/');
    // open the first controller's faceplate (selector per AppShell wiring)
    await page.getByRole('button', { name: /open faceplate|details/i }).first().click();
    const faceplate = page.getByRole('complementary', { name: /faceplate/i });
    await expect(faceplate).toBeVisible();
    await expect(faceplate.getByRole('group', { name: /controller mode/i })).toBeVisible();
    await expect(faceplate).toHaveScreenshot('faceplate-default.png', { maxDiffPixelRatio: 0.02 });
  });
  ```

- [ ] **Step 3:** Generate baselines, then verify a clean re-run:
  ```bash
  cd packages/smart_pid_web && npm run test:e2e -- --update-snapshots && npm run test:e2e
  ```
  Expected: first run writes baselines; second run PASSES against them. If the faceplate open-selector differs from the AppShell wiring, adjust the selector — do not change component behavior to satisfy a snapshot.

- [ ] **Step 4:** Commit (include the generated `*-snapshots/` baselines).
  ```bash
  git add packages/smart_pid_web/e2e && git commit -m "test(web): visual snapshots per theme at key breakpoints + faceplate"
  ```

---

### Task 10: Full suite, lint, build, parity note, PR

**Files:** none new — verification + docs.

- [ ] **Step 1:** Run the complete Vitest suite + lint + production build (the contrast gate and all instrumented assertions must be green together):
  ```bash
  cd packages/smart_pid_web && npm test && npm run lint && npm run build
  ```
  Expected: all unit tests PASS (theme switch + persistence, per-theme contrast gate, AnalogBar instrumentation, scale mapping, uPlot theme, faceplate by mode/state); lint clean; build succeeds.

- [ ] **Step 2:** Run the e2e suite once more for confidence:
  ```bash
  cd packages/smart_pid_web && npm run test:e2e
  ```
  Expected: all snapshots PASS.

- [ ] **Step 3:** Record parity closure in the design docs. Append a short note to the umbrella spec (`docs/superpowers/specs/2026-06-18-web-hmi-react-migration-design.md`) under its Fatia 8 / status section: "Fatia 8 complete — all 5 themes shipped, theme switcher persisted, AnalogBar instrumented, Faceplate functional. Total visual + functional parity reached; PySide6 HMI can be retired." (UI specs must be updated alongside UI code — project rule.)
  ```bash
  git add docs/superpowers/specs/2026-06-18-web-hmi-react-migration-design.md && git commit -m "docs(web): mark Fatia 8 parity complete, PySide6 retirement unblocked"
  ```

- [ ] **Step 4:** Push and open the PR (state NO backend change explicitly).
  ```bash
  git push -u origin feat/web-fatia8-themes-faceplate
  gh pr create --base main --title "feat(web): Fatia 8 — themes + faceplate (closes parity)" \
    --body "$(cat <<'EOF'
  ## Fatia 8 — Themes + Faceplate

  **NO BACKEND CHANGE.** Frontend-only (`packages/smart_pid_web/`).

  - All 5 themes complete as `[data-theme]` token sets (Dark Room, ISA-101, MD3 dark, MD3 light, Ocean).
  - Persisted theme switcher (localStorage) in the top bar.
  - Instrumented `AnalogBar` (value/scale/alarm reflect real `status` data; measurable PV→position; alarm fill only on abnormal state).
  - `Faceplate` widget (PV/SP/CO, 8 ControllerMode segmented control, faceplate AnalogBars, SP stepper, MAN-gated manual CO, apply-tuning) — consumes `status` WS + reuses Fatia 2 command hooks.
  - HARD GATES: per-theme WCAG AA ≥ 4.5:1 normal text + §8.4 cross-theme alarm matrix, asserted programmatically (build fails below threshold). uPlot themed per palette (§7.1).
  - Visual snapshots per theme @ 320/768/1024/1440 + faceplate.

  Closes total parity → PySide6 HMI can be retired.

  ## Test plan
  - [x] `npm test` — theme switch/persist, contrast gate, AnalogBar, scale, uPlot, faceplate
  - [x] `npm run test:e2e` — per-theme + faceplate snapshots
  - [x] `npm run lint && npm run build`
  EOF
  )"
  ```
  Expected: PR opened against `main`. Await explicit user approval before merge (inviolable branching rule).

---

## Self-Review

Against the spec acceptance and the foundation contract:

- [ ] **Backend untouched** — no file outside `packages/smart_pid_web/` is modified except the umbrella spec doc note (Task 10 Step 3). PR body states NO backend change. ✓
- [ ] **All 5 themes** as `[data-theme]` value overrides in `themes.css`, names from the stable `tokens.css` contract (not redefined): Dark Room §2.1, ISA-101 §2.2 (pre-existing), MD3 dark §2.3, MD3 light §2.4, Ocean §2.5 — all hex values copied verbatim. ✓
- [ ] **Persisted theme switcher** — `ThemeProvider` writes `localStorage['spid.theme']` and `data-theme`; `ThemeSwitcher` in TopBar; tests cover switch + rehydrate. ✓
- [ ] **Instrumented AnalogBar** — Task 6 asserts (a) fill position maps measurably to PV vs scale (50<100<150, mid≈50%) and (b) alarm coloring triggers only on abnormal state (`data-alarm` + weight 600 only when `alarm!=='normal'`); `role="meter"` + ARIA. ✓
- [ ] **Faceplate** (`src/components/Faceplate.tsx`) — PV/SP/CO, all 8 ControllerMode buttons (active highlighted), faceplate AnalogBars, SP stepper, MAN-gated manual CO, apply-tuning; reads `useRealtime().lastStatus`; reuses Fatia 2 hooks (mocked in tests, not re-implemented); waiting state when no frame. ✓
- [ ] **HARD GATES objective** — Task 4 asserts per-theme `--text` vs `--surface`/`--bg` ≥ 4.5:1 and the §8.4 alarm matrix (CRIT vs surface, ISA-101 ≥ 5; CRIT/WARN luminance-distinct) via `wcag-contrast`; build fails if any pair drops below target. ISA-101 saturated/alarm hue reserved for abnormal states is enforced by tokens (alarm colors applied only via `alarm` prop, never to normal fill). ✓
- [ ] **uPlot per palette** — Task 7 reads `--trend-*` tokens, builds opts (§7.1: SP dashed, CO `scale:'co'`, no fill); `RealtimeTrend` re-themes on mount + theme change. ✓
- [ ] **Tests** — Vitest: theme switch+persistence, faceplate render by mode/state, AnalogBar instrumented assertions, per-theme contrast assertions; Playwright snapshots per theme at 320/768/1024/1440 + faceplate. ✓
- [ ] **Acceptance** — theme switch applies tokens app-wide + persists; faceplate functional and matched to `status`+commands; every theme meets contrast + ISA-101 semantics by objective check. ✓
- [ ] **TDD + bite-sized + checkboxes + conventional commits (no trailers) + dedicated branch from `main`.** ✓
- [ ] **Parity closure** noted; PySide6 retirement unblocked (Task 10 Step 3). ✓

**Open follow-ups (flag at implementation):**
1. **Fatia 2 hook contract** — exact hook names/payload shapes (`useSetMode`/`useSetSetpoint`/`useSetOutput`/`useApplyTuning`) must be confirmed against the merged Fatia 2 code (Task 8 Step 3). The plan assumes `{ controller_id, mode|value }` payloads matching `POST /commands/{mode,setpoint,output}` (cid in BODY) and `POST /commands/apply-tuning/{id}` (cid in PATH, supervisor-gated). Adapt call sites + mocks together; do not add a re-implementation layer.
2. **AnalogBar base API** — if the Fatia 0+1 `AnalogBar` already exported a prop shape, the instrumentation in Task 6 must extend it compatibly; reconcile with any existing `ControllerCard` usage (Task 6 Step 3).
3. **Scale source** — `pv_scale.eu_min/eu_max/unit` comes from the REST `ControllerResponse` (`ScaleConfig`), passed into `Faceplate` as `scale`; the `status` WS frame carries no scale. The dashboard page supplies it from its controllers query.
