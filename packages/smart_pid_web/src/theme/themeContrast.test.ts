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
    // Normalize CSS whitespace: recorder/phosphor declarations mix 1- and 2-space
    // separators after `:` (spec formatting preserved verbatim) — flatten so the
    // token: hex assertion matches regardless of how many spaces the spec used.
    const flat = block.replace(/\s+/g, ' ');
    for (const [field, token] of Object.entries(TOKEN_OF) as [keyof ThemePalette, string][]) {
      const value = PALETTES[id][field];
      expect(flat, `${token}: ${value}`).toContain(`${token}: ${value}`);
    }
  });
});