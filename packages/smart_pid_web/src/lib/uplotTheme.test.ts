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
  '--trend-sp-dash': '6 4',
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
    apply();
    root.style.removeProperty('--trend-co-width');
    expect(readTrendTokens(getComputedStyle(root)).coWidth).toBe(1.5);
  });
});

describe('buildUplotTheme', () => {
  it('maps series treatments: SP dash from the token, CO on the co scale', () => {
    const theme = buildUplotTheme(readTrendTokens(apply()));
    expect(theme.series.sp.dash).toEqual([6, 4]);
    expect(theme.series.co.scale).toBe('co');
    expect(theme.series.pv.width).toBe(2);
    expect(theme.axisFont).toContain('Geist Mono');
  });

  it('SP renders SOLID when --trend-sp-dash is none (ISA-101 §6.3 rule)', () => {
    apply();
    root.style.setProperty('--trend-sp-dash', 'none');
    expect(buildUplotTheme(readTrendTokens(getComputedStyle(root))).series.sp.dash).toEqual([]);
  });

  it('SP falls back to solid when the dash token is missing or unparseable', () => {
    apply();
    root.style.removeProperty('--trend-sp-dash');
    expect(readTrendTokens(getComputedStyle(root)).spDash).toEqual([]);
    root.style.setProperty('--trend-sp-dash', 'dotted');
    expect(readTrendTokens(getComputedStyle(root)).spDash).toEqual([]);
  });
});