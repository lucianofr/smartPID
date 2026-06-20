import { readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, relative, resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

/**
 * ISA-101 source-guard (Task 0.4 — Vitest pivot).
 *
 * ORIGINAL MECHANISM: this gate was specced as two ESLint `no-restricted-syntax`
 * rules in `eslint.config.js`. That file is hard-blocked by the ECC
 * config-protection hook and cannot be edited, so the same intent is enforced
 * here as a self-contained Vitest source-guard: it reads source files directly
 * and asserts that the ENFORCED dirs contain no forbidden ISA-101 patterns
 * (raw colors / non-token color utilities / non-flat surfaces).
 *
 * Phase 9.3: expand ENFORCED_DIRS to all migrated surfaces / optionally port to
 * ESLint if config-protection is lifted.
 */

const here = dirname(fileURLToPath(import.meta.url));
const srcRoot = resolve(here, '..'); // .../src

/**
 * Directories whose source MUST already be ISA-101-clean. Each later migration
 * phase appends the dirs it migrates. Globs are relative to `src/`.
 */
export const ENFORCED_DIRS: readonly string[] = [
  'components/ui',
  'components/shell',
  // Phase 4 (Task 4.1): alarms — the ONLY surface where color is allowed
  // (CRIT/WARN/DIAG). Color lives in CSS tokens (--alarm-*) folded into index.css,
  // never as raw literals in source, so the whole dir passes the guard. `__tests__`
  // is excluded via EXCLUDE_DIRS.
  'features/alarms',
];

/**
 * Individual files (relative to `src/`) that MUST be ISA-101-clean even though
 * their parent directory is NOT enforced. `src/components/` is a flat dir with
 * many un-migrated siblings (ControllerCard, Faceplate, …), so it is enforced
 * file-by-file as each is migrated rather than as a whole directory.
 *
 * Phase 2 (Task 2.1): AnalogBar — the ISA-101 "boldness budget" signature bar.
 * Phase 2 (Task 2.2): ControllerCard + LoopHealthRow — flat token-utility cards.
 * Phase 3 (Task 3.1): Faceplate — the design-system "vitrine".
 * Phase 5 (Task 5.1): Trends — RealtimeTrend + PeriodSelector + uplotTheme and the
 *   multitrend DOM chrome (chart wrapper, selector, history, export, stats). Enforced
 *   file-by-file (not the whole `features/multitrend` dir) because `signals.ts` emits a
 *   sanctioned `color-mix(in oklch, …)` data-viz stroke that must stay outside the guard.
 * Phase 6 (Task 6.1): Executive dashboard — ExecutiveKPICard (the sanctioned big-number
 *   hero), TuningRecommendationCard, and the ExecutiveDashboardPage. §6b latitude is
 *   layout/typography only; the screen stays flat token-colored and motion-only (the
 *   guard forbids raw colors + box-shadow/gradient, not opacity/transform motion).
 * Phase 7 (Task 7.1): Login — LoginPage. §6b latitude (refined central card, modern
 *   type scale, ONE compositor-only entrance via the `.login-card-enter` class folded
 *   into index.css). Flat token-colored; error state uses the desaturated `--alarm-diag`
 *   token (via the `text-alarm-diag`/`border-alarm-diag` utilities), never critical red.
 * Phase 8 (Task 8.2): loop-config form bodies — LoopConfigDialog, AiPanel, CardControls.
 *   Inline-style blocks migrated to flat token utilities. Native mode `<select>`, the
 *   NONE/FUZZY/RL radios, and the Structure/Objective selects stay native (frozen tests)
 *   but restyled flat; error text uses the `--alarm-warning` token via `text-alarm-warning`.
 * Phase 8 (Task 8.3): peripheral surfaces — connection (ConnectionPanel, TagBrowser),
 *   settings (SettingsForm), projects (ProjectImportDropzone, ProjectList, WelcomeDialog),
 *   simulator (DynamicsSliders, SimulationModeBanner, SimulatorControlPanel) and their
 *   pages (Connection/Projects/Settings/Simulator). The 13 sibling `.css` files were
 *   deleted and folded into flat token utilities. Sanctioned color uses: the destructive
 *   Delete button + error text via the `--alarm-critical` token, the simulation banner via
 *   `--alarm-diag` + its paired `--on-alarm` contrast, and the data-driven OPC state dot /
 *   tag glyph via inline `var(--state-running)/--alarm-*` (state-dependent, not literals).
 *   WelcomeDialog stays a non-portal overlay (NOT the Radix Dialog) with the sanctioned
 *   `bg-black/70` scrim; DynamicsSliders keeps a native `<input type="range">` (frozen
 *   `toHaveValue`/`fireEvent.change` test) restyled flat.
 */
export const ENFORCED_FILES: readonly string[] = [
  'auth/LoginPage.tsx',
  // Phase 9 (Task 9.1): mandated missing states (§6a). Flat, token-only loading
  // (static placeholder bars, NO shimmer), empty, and error/WS-disconnect
  // (desaturated --alarm-diag) surfaces + the DashboardPage that consumes them.
  'components/MissingState.tsx',
  'components/WsConnectionBanner.tsx',
  'pages/DashboardPage.tsx',
  'components/AnalogBar.tsx',
  'components/ControllerCard.tsx',
  'components/LoopHealthRow.tsx',
  'components/Faceplate.tsx',
  'components/RealtimeTrend.tsx',
  'components/PeriodSelector.tsx',
  'lib/uplotTheme.ts',
  'features/multitrend/MultiTrendChart.tsx',
  'features/multitrend/SeriesSelector.tsx',
  'features/multitrend/StatsPanel.tsx',
  'features/multitrend/HistoryQuery.tsx',
  'features/multitrend/ExportButton.tsx',
  'components/ExecutiveKPICard.tsx',
  'components/TuningRecommendationCard.tsx',
  'pages/ExecutiveDashboardPage.tsx',
  'features/loop-config/LoopConfigDialog.tsx',
  'features/loop-config/AiPanel.tsx',
  'features/loop-config/CardControls.tsx',
  // Phase 8 (Task 8.3): peripheral surfaces (connection / settings / projects / simulator).
  'features/connection/ConnectionPanel.tsx',
  'features/connection/TagBrowser.tsx',
  'features/settings/SettingsForm.tsx',
  'features/projects/ProjectImportDropzone.tsx',
  'features/projects/ProjectList.tsx',
  'features/projects/WelcomeDialog.tsx',
  'features/simulator/DynamicsSliders.tsx',
  'features/simulator/SimulationModeBanner.tsx',
  'features/simulator/SimulatorControlPanel.tsx',
  'pages/ConnectionPage.tsx',
  'pages/ProjectsPage.tsx',
  'pages/SettingsPage.tsx',
  'pages/SimulatorPage.tsx',
  // Final-review followups: surfaces already migrated/clean but missing from scope.
  // ConfirmApplyTuningDialog migrated to the shadcn Dialog + flat token utilities
  // (warning/error via the --alarm-warning/--alarm-critical tokens, no hex fallback).
  'features/loop-config/ConfirmApplyTuningDialog.tsx',
  // MultiTrendPage chrome migrated from BEM (.multitrend-page__*) + sibling .css to
  // flat token utilities (the .css file was deleted).
  'pages/MultiTrendPage.tsx',
  // Simulator child controls (Phase 8.3 surface) — flat native form controls with no
  // raw color, completing the simulator migrated-set == enforced-set invariant.
  'features/simulator/AutoToggles.tsx',
  'features/simulator/DisturbanceControls.tsx',
  'features/simulator/PresetSelector.tsx',
  'features/simulator/StartStopControl.tsx',
  'features/simulator/TwinOutputModeControl.tsx',
];

/**
 * Paths (relative to `src/`) excluded from the enforced scope:
 *  - `__tests__`   — test code, not shipped UI.
 *
 * (The legacy hand-rolled `Dialog.tsx` was deleted in Task 8.1; its exclusion is gone and the
 *  whole `components/ui/` dir — including the flat shadcn `dialog.tsx` — is now enforced.)
 */
const EXCLUDE_FILES: ReadonlySet<string> = new Set();
const EXCLUDE_DIRS: ReadonlySet<string> = new Set(['__tests__', '__lintfixtures__']);

const SOURCE_EXT = /\.(?:ts|tsx|js|jsx)$/;

type Pattern = { readonly id: string; readonly re: RegExp; readonly label: string };

/**
 * Forbidden ISA-101 patterns. `black`/`white` and `/NN` opacity utilities are
 * deliberately NOT in the named-palette set, so the sanctioned modal scrim
 * (`bg-black/60` in `dialog-primitive.tsx`) passes naturally.
 */
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
  { id: 'box-shadow', label: 'box-shadow / boxShadow (non-flat surface)', re: /box-?[sS]hadow/ },
  { id: 'gradient', label: 'linear-gradient / radial-gradient', re: /(?:linear|radial)-gradient/ },
  { id: 'bevel', label: 'bevel effect', re: /\bbevel\b/i },
];

/**
 * Strip JS/TS comments so explanatory prose (e.g. "no shadow, no bevel") does
 * not trip the matcher. The line-comment pass avoids eating `http://` by
 * requiring the `//` not be preceded by `:`.
 */
function stripComments(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/(^|[^:])\/\/[^\n]*/g, '$1');
}

type Violation = { readonly file: string; readonly line: number; readonly pattern: string; readonly snippet: string };

/** Return every forbidden-pattern hit in `text` (comments stripped). */
export function findViolations(text: string, file = '<input>'): Violation[] {
  const stripped = stripComments(text);
  const lines = stripped.split('\n');
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

/** Recursively collect source files under `dir`, skipping excluded dirs/files. */
function walkSourceFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const abs = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (EXCLUDE_DIRS.has(entry.name)) continue;
      out.push(...walkSourceFiles(abs));
    } else if (entry.isFile() && SOURCE_EXT.test(entry.name)) {
      if (EXCLUDE_FILES.has(relative(srcRoot, abs))) continue;
      out.push(abs);
    }
  }
  return out;
}

function enforcedFiles(): string[] {
  const fromDirs = ENFORCED_DIRS.flatMap((d) => walkSourceFiles(resolve(srcRoot, d)));
  const fromFiles = ENFORCED_FILES.map((f) => resolve(srcRoot, f));
  return [...new Set([...fromDirs, ...fromFiles])];
}

const FIXTURES_DIR = resolve(srcRoot, '__lintfixtures__');
const readFixture = (name: string): string => readFileSync(resolve(FIXTURES_DIR, name), 'utf8');

describe('ISA-101 source-guard', () => {
  it('enforced UI surfaces contain no forbidden ISA-101 patterns', () => {
    const files = enforcedFiles();
    expect(files.length).toBeGreaterThan(0); // guard against a broken glob silently passing

    const violations = files.flatMap((f) => findViolations(readFileSync(f, 'utf8'), relative(srcRoot, f)));

    if (violations.length > 0) {
      const report = violations
        .map((v) => `  ${v.file}:${v.line} — ${v.pattern}\n    ${v.snippet}`)
        .join('\n');
      throw new Error(`ISA-101 violations in enforced scope:\n${report}`);
    }
    expect(violations).toEqual([]);
  });

  // Self-test: the matcher must flag the violation fixtures and pass the clean ones.
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

  it('flags the box-shadow violation fixture', () => {
    const v = findViolations(readFixture('box-shadow-violation.tsx'));
    expect(v.map((x) => x.pattern)).toContain('box-shadow / boxShadow (non-flat surface)');
  });

  it('passes the token-only clean fixture', () => {
    expect(findViolations(readFixture('token-color-clean.tsx'))).toEqual([]);
  });

  it('passes the sanctioned dialog scrim fixture (bg-black/60)', () => {
    expect(findViolations(readFixture('scrim-allowed.tsx'))).toEqual([]);
  });
});
