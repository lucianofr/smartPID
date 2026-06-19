import { describe, it, expect } from 'vitest';
import {
  fromRestStats, fromWsStats, aggregate, isAutoMode,
  formatKpi, variabilityOutOfTarget, type StatsResponseLike,
} from './kpi';
import type { StatsData } from '../realtime/envelope';

const rest: StatsResponseLike = {
  controller_id: 1, iae: 12.5, itae: 200, ise: 30, mse: 1.1,
  std_dev: 0.8, total_variation: 4.2, variability_sp: 0.03,
  variability_range: 0.04, sample_count: 600,
};

describe('fromRestStats', () => {
  it('maps REST field names onto the unified LoopKpis shape', () => {
    const k = fromRestStats(rest);
    expect(k).toEqual({
      controllerId: 1, iae: 12.5, itae: 200, ise: 30, mse: 1.1,
      sigma: 0.8, tv: 4.2, variabilitySp: 0.03, variabilityRange: 0.04,
      sampleCount: 600,
    });
  });
});

describe('fromWsStats', () => {
  it('maps WS StatsData (snake_case) onto the same unified shape', () => {
    const ws: StatsData = {
      iae: 12.5, itae: 200, ise: 30, mse: 1.1,
      std_dev: 0.8, total_variation: 4.2, variability_sp: 0.03, variability_range: 0.04,
    };
    const k = fromWsStats(1, ws);
    expect(k.tv).toBe(4.2);
    expect(k.variabilityRange).toBe(0.04);
    expect(k.sampleCount).toBe(0); // WS frame carries no sample count
  });
});

describe('isAutoMode', () => {
  it.each(['AUTO', 'CAS', 'RCAS'])('treats %s as AUTO-family', (m) => {
    expect(isAutoMode(m)).toBe(true);
  });
  it.each(['MAN', 'OOS', 'IMAN', 'LO', 'ROUT', 'BYPASS'])('treats %s as non-AUTO', (m) => {
    expect(isAutoMode(m)).toBe(false);
  });
});

describe('aggregate', () => {
  it('computes loopCount, avg variability/IAE, total TV, and AUTO%', () => {
    const a = fromRestStats(rest);
    const b = fromRestStats({ ...rest, controller_id: 2, iae: 7.5, total_variation: 1.8, variability_range: 0.06 });
    const modes = new Map([[1, 'AUTO'], [2, 'MAN']]);
    const agg = aggregate([a, b], modes);
    expect(agg.loopCount).toBe(2);
    expect(agg.avgIae).toBeCloseTo(10.0, 6);
    expect(agg.totalTv).toBeCloseTo(6.0, 6);
    expect(agg.avgVariabilityRange).toBeCloseTo(0.05, 6);
    expect(agg.autoPct).toBeCloseTo(50, 6);
  });

  it('returns zeros (no NaN) for an empty loop set', () => {
    const agg = aggregate([], new Map());
    expect(agg).toEqual({ loopCount: 0, avgVariabilityRange: 0, totalTv: 0, avgIae: 0, autoPct: 0 });
  });
});

describe('formatKpi', () => {
  it('renders variability as a percentage with one decimal', () => {
    expect(formatKpi(0.042, 'pct')).toBe('4.2%');
  });
  it('renders an index with two decimals', () => {
    expect(formatKpi(12.5, 'index')).toBe('12.50');
  });
  it('renders a count as an integer', () => {
    expect(formatKpi(2, 'count')).toBe('2');
  });
});

describe('variabilityOutOfTarget', () => {
  it('flags > 5% by default', () => {
    expect(variabilityOutOfTarget(0.06)).toBe(true);
    expect(variabilityOutOfTarget(0.04)).toBe(false);
  });
});
