import { describe, it, expect } from 'vitest';
import { PALETTES, type ThemeId } from './themeContrast';

const THEMES: ThemeId[] = ['isa101', 'dark-room', 'md3-dark', 'md3-light', 'ocean'];

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

// Normal text AA — strict (WCAG 1.4.3).
describe('per-theme text contrast (>= 4.5:1)', () => {
  it.each(THEMES)('%s: --text on --surface >= 4.5:1', (id) => {
    const p = PALETTES[id];
    expect(contrast(p.text, p.surface)).toBeGreaterThanOrEqual(4.5);
  });
  it.each(THEMES)('%s: --text on --bg >= 4.5:1', (id) => {
    const p = PALETTES[id];
    expect(contrast(p.text, p.bg)).toBeGreaterThanOrEqual(4.5);
  });
});

// Alarm indicators are non-text graphical objects (3px stripe + 10px shaped icon) -> WCAG 1.4.11 = 3:1.
// Colorblind safety comes from ISA-101 shape redundancy (octagon/triangle/diamond), not luminance.
describe('§8.4 alarm matrix — non-text 3:1 vs surface (WCAG 1.4.11)', () => {
  it.each(THEMES)('%s: CRIT vs surface >= 3:1', (id) => {
    expect(contrast(PALETTES[id].alarmCritical, PALETTES[id].surface)).toBeGreaterThanOrEqual(3);
  });
  it.each(THEMES)('%s: WARN vs surface >= 3:1', (id) => {
    expect(contrast(PALETTES[id].alarmWarning, PALETTES[id].surface)).toBeGreaterThanOrEqual(3);
  });
  it.each(THEMES)('%s: DIAG vs surface >= 3:1', (id) => {
    expect(contrast(PALETTES[id].alarmDiag, PALETTES[id].surface)).toBeGreaterThanOrEqual(3);
  });
  it.each(THEMES)('%s: CRIT and WARN are distinct by hue or luminance', (id) => {
    const p = PALETTES[id];
    expect(p.alarmCritical).not.toBe(p.alarmWarning);
    const distinct =
      deltaHue(p.alarmCritical, p.alarmWarning) >= 15 ||
      Math.abs(luminance(p.alarmCritical) - luminance(p.alarmWarning)) >= 0.05;
    expect(distinct).toBe(true);
  });
});
