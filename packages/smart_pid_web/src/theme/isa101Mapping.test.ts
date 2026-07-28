import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { buildUplotTheme, readTrendTokens } from '../lib/uplotTheme';
import { CONTRACT_TOKENS } from './contract';

/**
 * Phase 11 — ISA-101 5→3 retokenisation, proved by computed style.
 *
 * `OLD_ISA101` is the pre-rewrite `[data-theme='isa101']` block read verbatim
 * from git at `ca0a6f6` (the parent of `38005e9`, the phase-2 commit that
 * deleted legacy `src/`), plus the three theme-agnostic `--trend-*-width`
 * values that lived in the old `tokens.css :root`. No color is inferred.
 *
 * `MAPPING` is the executable form of docs/isa101-token-mapping.md: for every
 * §6.4 name it records the OLD token whose hex it inherits, or `DERIVED` when
 * the name is new to v2 (its value is then justified in the doc and pinned by
 * ISA101_EXPECTED alone).
 */

const OLD_ISA101 = {
  '--bg': '#1E1E1E',
  '--surface': '#2D2D30',
  '--surface-container': '#2D2D30',
  '--surface-container-high': '#333337',
  '--field-bg': '#252526',
  '--border': '#454548',
  '--border-strong': '#57575B',
  '--divider': '#3A3A3D',
  '--text': '#E0E0E0',
  '--text-secondary': '#ABABAB',
  '--text-disabled': '#666666',
  '--focus-ring': '#C8C8C8',
  '--alarm-critical': '#FF3333',
  '--alarm-critical-bg': '#3A0E0E',
  '--alarm-warning': '#FF8800',
  '--alarm-warning-bg': '#3A2200',
  '--alarm-diag': '#AA55FF',
  '--alarm-diag-bg': '#260A3A',
  '--alarm-info': '#33AAFF',
  '--on-alarm': '#FFFFFF',
  '--text-on-alarm': '#1E1E1E',
  '--state-running': '#9A9A9A',
  '--state-stopped': '#ABABAB',
  '--state-error': '#FF3333',
  '--state-oos': '#666666',
  '--trend-pv': '#E0E0E0',
  '--trend-sp': '#33AAFF',
  '--trend-co': '#FFB000',
  '--trend-grid': '#3A3A3D',
  '--trend-axis': '#57575B',
  '--trend-bg': '#252526',
  '--bar-track': '#252526',
  '--bar-fill': '#9A9A9A',
  '--bar-marker': '#CCCCCC',
  // tokens.css :root — unitless in v1, carried over as CSS px in v2.
  '--trend-pv-width': '1.5',
  '--trend-sp-width': '1.5',
  '--trend-co-width': '1.5',
} as const satisfies Record<string, string>;

type OldToken = keyof typeof OLD_ISA101;
/** No pre-rewrite equivalent: the value is argued in the mapping doc. */
const DERIVED = null;

const MAPPING: Record<string, OldToken | typeof DERIVED> = {
  // Surfaces — the 5-step ladder collapses to 3.
  '--bg': '--bg',
  '--surface': '--surface', // --surface-container and -high collapse in here
  '--surface-sunk': '--field-bg',
  // Lines — --divider (10 uses) collapses into --border (65 uses); its hex
  // survives untouched on --trend-grid.
  '--rule': '--border',
  '--rule-strong': '--border-strong',
  // Text
  '--text': '--text',
  '--text-soft': '--text-secondary',
  '--text-disabled': '--text-disabled',
  // Focus / selection / overlay
  '--focus-ring': '--focus-ring',
  '--selection': '--surface-container-high', // the old hover/selected raise
  '--scrim': DERIVED, // old app hard-coded the sanctioned `bg-black/60` scrim
  // Accent — ISA-101 has no accent hue; the family is the old neutral chrome.
  '--accent': '--border-strong',
  '--accent-hover': '--text-disabled',
  '--accent-sunk': '--border',
  '--accent-soft': '--surface-container-high',
  '--on-accent': '--on-alarm',
  // Alarm
  '--alarm-crit': '--alarm-critical',
  '--alarm-crit-bg': '--alarm-critical-bg',
  '--alarm-warn': '--alarm-warning',
  '--alarm-warn-bg': '--alarm-warning-bg',
  '--alarm-adv': '--alarm-diag',
  '--alarm-adv-bg': '--alarm-diag-bg',
  '--alarm-log': '--text-secondary', // `.sev-icon--dot` (LOG glyph) was text-secondary
  '--on-alarm': '--on-alarm',
  // State
  '--state-running': '--state-running',
  '--state-stopped': '--state-stopped',
  '--state-error': '--state-error',
  '--state-oos': '--state-oos',
  // Trend
  '--trace-pv': '--trend-pv',
  '--trace-sp': '--trend-sp',
  '--trace-co': '--trend-co',
  '--trend-grid': '--trend-grid',
  '--trend-axis': '--trend-axis',
  '--trend-bg': '--trend-bg',
  '--trend-pv-width': '--trend-pv-width',
  '--trend-sp-width': '--trend-sp-width',
  '--trend-co-width': '--trend-co-width',
  '--trend-sp-dash': DERIVED, // encodes §6.3's solid ISA SP, unimplemented in v1
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

/** Every §6.4 color/geometry token and its exact final ISA-101 value. */
const ISA101_EXPECTED: Record<string, string> = {
  '--bg': '#1E1E1E',
  '--surface': '#2D2D30',
  '--surface-sunk': '#252526',
  '--rule': '#454548',
  '--rule-strong': '#57575B',
  '--text': '#E0E0E0',
  '--text-soft': '#ABABAB',
  '--text-disabled': '#666666',
  '--focus-ring': '#C8C8C8',
  '--selection': '#333337',
  '--scrim': 'rgba(0, 0, 0, 0.6)',
  '--accent': '#57575B',
  '--accent-hover': '#666666',
  '--accent-sunk': '#454548',
  '--accent-soft': '#333337',
  '--on-accent': '#FFFFFF',
  '--alarm-crit': '#FF3333',
  '--alarm-crit-bg': '#3A0E0E',
  '--alarm-warn': '#FF8800',
  '--alarm-warn-bg': '#3A2200',
  '--alarm-adv': '#AA55FF',
  '--alarm-adv-bg': '#260A3A',
  '--alarm-log': '#ABABAB',
  '--on-alarm': '#FFFFFF',
  '--state-running': '#9A9A9A',
  '--state-stopped': '#ABABAB',
  '--state-error': '#FF3333',
  '--state-oos': '#666666',
  '--trace-pv': '#E0E0E0',
  '--trace-sp': '#33AAFF',
  '--trace-co': '#FFB000',
  '--trend-grid': '#3A3A3D',
  '--trend-axis': '#57575B',
  '--trend-bg': '#252526',
  '--trend-pv-width': '1.5px',
  '--trend-sp-width': '1.5px',
  '--trend-co-width': '1.5px',
  '--trend-sp-dash': 'none',
  '--bar-track': '#252526',
  '--bar-fill': '#9A9A9A',
  '--bar-marker': '#CCCCCC',
  '--glow-alarm': '0 0 #0000',
  '--glow-focus': '0 0 #0000',
  '--glow-accent': '0 0 #0000',
  '--glow-trace': '0px',
};

const CSS_FILES = ['src/theme/tokens.css', 'src/theme/themes.css'];
const themesCss = readFileSync(resolve(process.cwd(), 'src/theme/themes.css'), 'utf8');
const root = document.documentElement;
let styleEl: HTMLStyleElement;

const resolved = (token: string): string =>
  getComputedStyle(root).getPropertyValue(token).trim();

beforeAll(() => {
  styleEl = document.createElement('style');
  styleEl.textContent = CSS_FILES.map((p) =>
    readFileSync(resolve(process.cwd(), p), 'utf8'),
  ).join('\n');
  document.head.appendChild(styleEl);
  root.setAttribute('data-theme', 'isa101');
});

afterAll(() => {
  styleEl.remove();
  root.removeAttribute('data-theme');
});

describe('ISA-101 computed style matches the recorded mapping', () => {
  it.each(Object.entries(ISA101_EXPECTED))('%s resolves to %s', (token, expected) => {
    expect(resolved(token)).toBe(expected);
  });

  it('covers every §6.4 token (type tokens excepted — they live in :root)', () => {
    const typeTokens = ['--font-display', '--font-ui', '--font-data'];
    const covered = new Set(Object.keys(ISA101_EXPECTED));
    const uncovered = CONTRACT_TOKENS.filter(
      (t) => !covered.has(t) && !typeTokens.includes(t),
    );
    expect(uncovered).toEqual([]);
    for (const t of typeTokens) expect(resolved(t)).not.toBe('');
  });
});

describe('every value traces to the pre-rewrite palette', () => {
  it.each(
    Object.entries(MAPPING).filter((e): e is [string, OldToken] => e[1] !== DERIVED),
  )('%s inherits the hex of %s', (token, oldToken) => {
    const old = OLD_ISA101[oldToken];
    // Widths gained a CSS unit; colors are byte-identical.
    const expected = token.endsWith('-width') ? `${old}px` : old;
    expect(ISA101_EXPECTED[token]).toBe(expected);
  });

  it('maps every §6.4 token exactly once, with no stale name left over', () => {
    expect(Object.keys(MAPPING).sort()).toEqual(Object.keys(ISA101_EXPECTED).sort());
  });

  it('leaves only the four deliberately absorbed old tokens unmapped', () => {
    const claimed = new Set(Object.values(MAPPING).filter(Boolean));
    const orphans = Object.keys(OLD_ISA101).filter((t) => !claimed.has(t as OldToken));
    // --surface-container == --surface; --divider folds into --rule (its hex lives
    // on --trend-grid); --alarm-info was the unused 4th slot (`sev-log` had no CSS
    // rule) and its hex lives on --trace-sp; --text-on-alarm was never referenced.
    expect(orphans.sort()).toEqual([
      '--alarm-info',
      '--divider',
      '--surface-container',
      '--text-on-alarm',
    ]);
  });
});

describe('ISA-101 keeps its own trace rules (§6.3)', () => {
  it('SP is SOLID blue, never dashed', () => {
    const theme = buildUplotTheme(readTrendTokens(getComputedStyle(root)));
    expect(theme.series.sp.dash).toEqual([]);
    expect(theme.series.sp.stroke).toBe('#33AAFF');
  });

  it('PV is neutral gray — no alarm hue leaks into the trace language', () => {
    expect(resolved('--trace-pv')).toBe(resolved('--text'));
    const alarms = ['--alarm-crit', '--alarm-warn', '--alarm-adv'].map(resolved);
    for (const trace of ['--trace-pv', '--trace-sp', '--trace-co']) {
      expect(alarms).not.toContain(resolved(trace));
    }
  });
});

describe('the retokenisation is finished', () => {
  it('no interim marker survives in themes.css', () => {
    expect(themesCss).not.toContain('interim');
    expect(themesCss).not.toContain('INTERIM');
  });

  it('all three themes declare the identical token vocabulary (single §6.4 set)', () => {
    const blocks = [...themesCss.matchAll(/\[data-theme="([a-z0-9-]+)"\]\s*\{([\s\S]*?)\n\}/g)];
    expect(blocks.map((b) => b[1])).toEqual(['recorder', 'phosphor', 'isa101']);
    const names = blocks.map(
      (b) => [...b[2].matchAll(/(--[a-z0-9-]+)\s*:/g)].map((m) => m[1]).sort(),
    );
    expect(names[1]).toEqual(names[0]);
    expect(names[2]).toEqual(names[0]);
  });
});
