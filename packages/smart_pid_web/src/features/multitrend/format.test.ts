import { describe, it, expect } from 'vitest';
import { toStatsRow, formatMetric, formatVariabilityPct } from './format';

describe('toStatsRow', () => {
  it('maps snake_case StatsResponse fields to the camelCase StatsRow', () => {
    const row = toStatsRow(2, {
      iae: 1.5,
      itae: 2.5,
      ise: 3.5,
      mse: 0.25,
      std_dev: 0.4,
      total_variation: 12,
      variability_range: 0.08,
      variability_sp: 0.02,
    });
    expect(row).toEqual({
      loopId: 2,
      iae: 1.5,
      itae: 2.5,
      ise: 3.5,
      mse: 0.25,
      sigma: 0.4,
      tv: 12,
      varRange: 0.08,
      varSp: 0.02,
    });
  });
});

describe('formatMetric', () => {
  it('renders fixed-precision tabular numbers', () => {
    expect(formatMetric(1.23456)).toBe('1.235');
    expect(formatMetric(0)).toBe('0.000');
  });
  it('renders an em-dash for non-finite values', () => {
    expect(formatMetric(Number.NaN)).toBe('—');
    expect(formatMetric(Infinity)).toBe('—');
  });
});

describe('formatVariabilityPct', () => {
  it('renders a ratio as a percentage', () => {
    expect(formatVariabilityPct(0.08)).toBe('8.0%');
    expect(formatVariabilityPct(0.025)).toBe('2.5%');
  });
  it('renders an em-dash for non-finite values', () => {
    expect(formatVariabilityPct(Number.NaN)).toBe('—');
    expect(formatVariabilityPct(Infinity)).toBe('—');
  });
});
