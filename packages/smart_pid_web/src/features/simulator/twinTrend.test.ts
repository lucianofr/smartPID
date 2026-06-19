import { describe, it, expect } from 'vitest';
import type { FFSignal, StatusData } from '../../realtime/envelope';
import { EMPTY_TREND, appendTwinSample } from './twinTrend';

function sig(value: number): FFSignal {
  return { value, severity: 'GOOD', limit_bits: '', sub_status: '' };
}

function status(pv: number, sp: number, co: number, timestamp: string | number): StatusData {
  return {
    pv: sig(pv),
    sp: sig(sp),
    co: sig(co),
    bkcal_in: sig(0),
    bkcal_out: sig(0),
    mode: 'MAN',
    kp: 1,
    ti: 1,
    td: 0,
    integral_val: 0,
    timestamp,
  };
}

describe('appendTwinSample', () => {
  it('returns prev unchanged when status is undefined', () => {
    const prev: typeof EMPTY_TREND = [[1], [10], [20], [5]];
    expect(appendTwinSample(prev, undefined)).toBe(prev);
  });

  it('extracts .value from FFSignal pv/sp/co and appends one sample', () => {
    const result = appendTwinSample(EMPTY_TREND, status(42, 50, 30, 100));
    expect(result[0]).toEqual([100]); // x = epoch seconds
    expect(result[1]).toEqual([42]); // pv.value
    expect(result[2]).toEqual([50]); // sp.value
    expect(result[3]).toEqual([30]); // co.value
  });

  it('does not mutate the previous TrendData (immutable append)', () => {
    const prev: typeof EMPTY_TREND = [[1], [10], [20], [5]];
    const result = appendTwinSample(prev, status(2, 3, 4, 2));
    expect(prev[0]).toEqual([1]); // original untouched
    expect(result[0]).toEqual([1, 2]);
    expect(result[1]).toEqual([10, 2]);
  });

  it('parses ISO-8601 timestamp to epoch seconds', () => {
    const result = appendTwinSample(EMPTY_TREND, status(1, 1, 1, '1970-01-01T00:01:00Z'));
    expect(result[0][0]).toBe(60); // 60s past epoch
  });

  it('caps at the limit keeping the newest samples', () => {
    let trend = EMPTY_TREND;
    for (let i = 0; i < 5; i++) {
      trend = appendTwinSample(trend, status(i, i, i, i), 3);
    }
    expect(trend[0]).toEqual([2, 3, 4]); // oldest two dropped
    expect(trend[1]).toEqual([2, 3, 4]);
    expect(trend[2]).toEqual([2, 3, 4]);
    expect(trend[3]).toEqual([2, 3, 4]);
  });

  it('keeps all four series equal-length', () => {
    let trend = EMPTY_TREND;
    for (let i = 0; i < 10; i++) {
      trend = appendTwinSample(trend, status(i, i, i, i), 4);
    }
    const len = trend[0].length;
    expect(trend[1].length).toBe(len);
    expect(trend[2].length).toBe(len);
    expect(trend[3].length).toBe(len);
  });
});
