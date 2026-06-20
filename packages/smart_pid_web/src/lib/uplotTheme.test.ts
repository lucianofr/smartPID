import { describe, it, expect } from 'vitest';
import { buildUplotTheme, type TrendTokens } from './uplotTheme';

const tokens: TrendTokens = {
  pv: '#E0E0E0', sp: '#33AAFF', co: '#FFB000',
  grid: '#3A3A3D', axis: '#57575B', bg: '#252526',
  pvWidth: 2, spWidth: 1.5, coWidth: 1,
  font: '12px JetBrains Mono',
};

describe('buildUplotTheme (§7.1)', () => {
  const t = buildUplotTheme(tokens);

  it('maps axis + grid + bg from trend tokens', () => {
    expect(t.axesStroke).toBe('#57575B');
    expect(t.gridStroke).toBe('#3A3A3D');
    expect(t.bg).toBe('#252526');
  });
  it('PV/SP/CO series use the right strokes, SP is dashed, CO uses co scale', () => {
    expect(t.series.pv).toMatchObject({ stroke: '#E0E0E0' });
    expect(t.series.sp).toMatchObject({ stroke: '#33AAFF', dash: [6, 4] });
    expect(t.series.co).toMatchObject({ stroke: '#FFB000', scale: 'co' });
  });
  it('line weights come from the trend line-weight tokens', () => {
    expect(t.series.pv.width).toBe(2);
    expect(t.series.sp.width).toBe(1.5);
    expect(t.series.co.width).toBe(1);
  });
  it('axis label font comes from the --font-data token', () => {
    expect(t.axisFont).toBe('12px JetBrains Mono');
  });
  it('exposes a crosshair cursor on both axes', () => {
    expect(t.cursor).toMatchObject({ x: true, y: true });
  });
  it('no area fill on any series', () => {
    for (const s of Object.values(t.series)) {
      expect((s as Record<string, unknown>).fill).toBeUndefined();
    }
  });
});
