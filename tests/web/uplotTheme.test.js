import { describe, expect, it } from 'vitest';
import { buildUplotTheme, readTrendTokens } from '@/lib/uplotTheme';

function fakeStyle(props) {
  return {
    getPropertyValue(name) {
      return props[name] ?? '';
    },
  };
}

describe('readTrendTokens', () => {
  it('parses dash patterns, rejecting none/empty/garbage as solid', () => {
    const dash = (v) => readTrendTokens(fakeStyle({ '--trend-sp-dash': v })).spDash;
    expect(dash('6 4')).toEqual([6, 4]);
    expect(dash('none')).toEqual([]);
    expect(dash('')).toEqual([]);
    expect(dash('6 x 4')).toEqual([]);
  });

  it('defaults line width to 1.5 when the CSS value is missing or invalid', () => {
    const missing = readTrendTokens(fakeStyle({}));
    expect(missing.pvWidth).toBe(1.5);
    const explicit = readTrendTokens(fakeStyle({ '--trend-pv-width': '2px' }));
    expect(explicit.pvWidth).toBe(2);
  });

  it('falls back to monospace font when --font-data is unset', () => {
    const tokens = readTrendTokens(fakeStyle({}));
    expect(tokens.font).toBe('12px ui-monospace, monospace');
  });
});

describe('buildUplotTheme', () => {
  it('maps tokens onto uPlot series and chrome', () => {
    const tokens = readTrendTokens(
      fakeStyle({
        '--trace-pv': '#f00',
        '--trace-sp': '#00f',
        '--trace-co': '#0f0',
        '--trend-grid': '#111',
        '--trend-axis': '#222',
        '--trend-bg': '#000',
        '--accent': '#ff0',
        '--trend-sp-dash': '6 4',
      }),
    );
    const theme = buildUplotTheme(tokens);
    expect(theme.series.pv).toEqual({ stroke: '#f00', width: 1.5 });
    expect(theme.series.sp.dash).toEqual([6, 4]);
    expect(theme.series.co.scale).toBe('co');
    expect(theme.gridStroke).toBe('#111');
    expect(theme.accent).toBe('#ff0');
  });
});
