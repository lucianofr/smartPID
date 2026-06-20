import { describe, it, expect } from 'vitest';
import { hex as wcagHex } from 'wcag-contrast';
import { calcAPCA } from 'apca-w3';
import { PALETTES, type ThemeId } from './themeContrast';

const THEMES: ThemeId[] = ['isa101', 'dark-room', 'md3-dark', 'md3-light', 'ocean'];

// --- Hand-rolled helpers (retained as a CROSS-CHECK against wcag-contrast). ---
function luminance(hex: string): number {
  const h = hex.replace('#', '');
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
  const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}
function contrast(a: string, b: string): number {
  const la = luminance(a);
  const lb = luminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}
function hue(hex: string): number {
  const h = hex.replace('#', '');
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  if (max === min) return 0;
  const d = max - min;
  let hh = max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
  hh *= 60;
  return hh < 0 ? hh + 360 : hh;
}
function deltaHue(a: string, b: string): number {
  const d = Math.abs(hue(a) - hue(b));
  return Math.min(d, 360 - d);
}

// --- Source of truth: wcag-contrast. APCA: cross-check via apca-w3. ---
const wcagContrast = (a: string, b: string): number => wcagHex(a, b);
const apcaLc = (text: string, surface: string): number => Math.abs(calcAPCA(text, surface) as number);

// Thresholds (spec §4 / design-system §8.1, §8.4 reconciliation 2026-06-20).
const TEXT_FLOOR = 4.5; // WCAG 1.4.3 normal text
const ISA101_TEXT_FLOOR = 5.0; // ISA-101 is held to a stricter bar
const NONTEXT_FLOOR = 3.0; // WCAG 1.4.11 (alarm stripe + geometric glyph)
const DELTA_L_FLOOR = 0.2; // luminance separation for required text pairs
const HUE_DELTA_FLOOR = 25; // alarm hue separation so CRIT/WARN/DIAG stay distinguishable
const APCA_BODY_FLOOR = 60; // Lc 60 ~= body-text floor (cross-check on --text body surfaces)

const SURFACES = ['bg', 'surface', 'surfaceHigh'] as const;
const ALARMS = ['alarmCritical', 'alarmWarning', 'alarmDiag'] as const;

function textFloor(id: ThemeId): number {
  return id === 'isa101' ? ISA101_TEXT_FLOOR : TEXT_FLOOR;
}

// wcag-contrast must agree with the hand-rolled formula (sanity that the source of truth is sound).
describe('wcag-contrast agrees with the hand-rolled cross-check (<= 0.01)', () => {
  it.each(THEMES)('%s: --text on --surface matches within tolerance', (id) => {
    const p = PALETTES[id];
    expect(Math.abs(wcagContrast(p.text, p.surface) - contrast(p.text, p.surface))).toBeLessThan(
      0.01,
    );
  });
});

// §4 text matrix: --text and --text-secondary on every surface.
// Primary --text is the body-text contract: strict 4.5:1 (isa101 5:1), ΔL >= 0.2, APCA cross-check.
describe('§4 text matrix — --text (primary) on {--bg, --surface, --surface-container-high}', () => {
  for (const surface of SURFACES) {
    it.each(THEMES)(`%s: --text on --${surface} >= floor (4.5:1 / isa101 5:1)`, (id) => {
      const p = PALETTES[id];
      expect(wcagContrast(p.text, p[surface])).toBeGreaterThanOrEqual(textFloor(id));
    });
    it.each(THEMES)(`%s: --text on --${surface} ΔL >= 0.2`, (id) => {
      const p = PALETTES[id];
      expect(Math.abs(luminance(p.text) - luminance(p[surface]))).toBeGreaterThanOrEqual(
        DELTA_L_FLOOR,
      );
    });
  }
});

// APCA cross-check (apca-w3) for the body-text pairs the spec §8.1 holds authoritative:
// --text over --surface and --bg. APCA Lc is compared at the integer the spec convention rounds to.
describe('§4 APCA cross-check — |APCA(--text, surface)| >= Lc 60 (body-text floor)', () => {
  it.each(THEMES)('%s: --text on --surface >= Lc 60', (id) => {
    const p = PALETTES[id];
    expect(Math.round(apcaLc(p.text, p.surface))).toBeGreaterThanOrEqual(APCA_BODY_FLOOR);
  });
  it.each(THEMES)('%s: --text on --bg >= Lc 60', (id) => {
    const p = PALETTES[id];
    expect(Math.round(apcaLc(p.text, p.bg))).toBeGreaterThanOrEqual(APCA_BODY_FLOOR);
  });
});

// --text-secondary is muted UI text. Per §8.4 reconciliation it is NOT held to the 4.5:1 body
// floor (dark-room #666670 / ocean #7E97AC are committed identity tokens below 4.5:1); the gate
// enforces the non-text / large-text 3:1 floor so it stays legible without altering identity hues.
describe('§4 text matrix — --text-secondary on every surface >= 3:1 (large/secondary text)', () => {
  for (const surface of SURFACES) {
    it.each(THEMES)(`%s: --text-secondary on --${surface} >= 3:1`, (id) => {
      const p = PALETTES[id];
      expect(wcagContrast(p.textSecondary, p[surface])).toBeGreaterThanOrEqual(NONTEXT_FLOOR);
    });
  }
});

// §8.4 alarm matrix: CRIT/WARN/DIAG are NON-TEXTUAL indicators (3px stripe + 10px geometric icon)
// -> WCAG 1.4.11 = 3:1 vs every surface. Colorblind safety = shape redundancy (§8.2), not luminance.
describe('§8.4 alarm matrix — CRIT/WARN/DIAG vs {--bg, --surface, --surface-container-high} >= 3:1', () => {
  for (const alarm of ALARMS) {
    for (const surface of SURFACES) {
      it.each(THEMES)(`%s: --${alarm} on --${surface} >= 3:1`, (id) => {
        const p = PALETTES[id];
        expect(wcagContrast(p[alarm], p[surface])).toBeGreaterThanOrEqual(NONTEXT_FLOOR);
      });
    }
  }
});

// Pairwise alarm separation: CRIT/WARN/DIAG must differ by hue so the three severities are
// distinguishable beyond the shared shape channel. Floor 25deg (spec example).
describe('§8.4 alarm hue-delta — every alarm pair >= 25deg', () => {
  it.each(THEMES)('%s: CRIT/WARN hue-delta >= 25', (id) => {
    const p = PALETTES[id];
    expect(deltaHue(p.alarmCritical, p.alarmWarning)).toBeGreaterThanOrEqual(HUE_DELTA_FLOOR);
  });
  it.each(THEMES)('%s: CRIT/DIAG hue-delta >= 25', (id) => {
    const p = PALETTES[id];
    expect(deltaHue(p.alarmCritical, p.alarmDiag)).toBeGreaterThanOrEqual(HUE_DELTA_FLOOR);
  });
  it.each(THEMES)('%s: WARN/DIAG hue-delta >= 25', (id) => {
    const p = PALETTES[id];
    expect(deltaHue(p.alarmWarning, p.alarmDiag)).toBeGreaterThanOrEqual(HUE_DELTA_FLOOR);
  });
});
