import { describe, it, expect } from 'vitest';
import { valueAt, selectSeries } from './multiTrendData';
import type { StatusData, FFSignal } from '../../realtime/envelope';

const sig = (value: number): FFSignal => ({
  value,
  severity: 'GOOD',
  limit_bits: '0',
  sub_status: 'NON_SPECIFIC',
});

const frame = (pv: number, sp: number, co: number): StatusData => ({
  pv: sig(pv),
  sp: sig(sp),
  co: sig(co),
  bkcal_in: sig(0),
  bkcal_out: sig(0),
  mode: 'AUTO',
  kp: 1,
  ti: 1,
  td: 0,
  integral_val: 0,
  timestamp: '2026-01-01T00:00:00Z',
});

describe('valueAt', () => {
  it('extracts pv/sp/co from a status frame', () => {
    const f = frame(10, 20, 30);
    expect(valueAt(f, 'pv')).toBe(10);
    expect(valueAt(f, 'sp')).toBe(20);
    expect(valueAt(f, 'co')).toBe(30);
  });
});

describe('selectSeries', () => {
  it('produces uPlot AlignedData: x first, one row per selected signal', () => {
    const buffer = new Map([
      [1, { t: [0, 1, 2], pv: [10, 11, 12], sp: [20, 20, 20], co: [50, 51, 52] }],
      [2, { t: [0, 1, 2], pv: [5, 6, 7], sp: [8, 8, 8], co: [40, 40, 40] }],
    ]);
    const out = selectSeries(buffer, [
      { loopId: 1, variable: 'pv' },
      { loopId: 2, variable: 'co' },
    ]);
    expect(out.data[0]).toEqual([0, 1, 2]); // shared x axis
    expect(out.data[1]).toEqual([10, 11, 12]); // loop 1 pv
    expect(out.data[2]).toEqual([40, 40, 40]); // loop 2 co
    expect(out.keys).toHaveLength(2);
  });

  it('returns just the x row when nothing is selected', () => {
    const buffer = new Map([[1, { t: [0, 1], pv: [1, 2], sp: [3, 4], co: [5, 6] }]]);
    const out = selectSeries(buffer, []);
    expect(out.data).toEqual([[0, 1]]);
    expect(out.keys).toEqual([]);
  });

  it('aligns differing-length buffers to the newest common window (no misalignment)', () => {
    // Loops selected at different times diverge in length. uPlot indexes every
    // series by position against data[0], so all rows MUST share one length.
    const buffer = new Map([
      [1, { t: [0, 1, 2], pv: [10, 11, 12], sp: [20, 20, 20], co: [50, 51, 52] }],
      [2, { t: [1, 2], pv: [5, 6], sp: [8, 8], co: [40, 41] }],
    ]);
    const out = selectSeries(buffer, [
      { loopId: 1, variable: 'pv' },
      { loopId: 2, variable: 'co' },
    ]);
    // Every row (x + each series) reconciled to the min length (2), newest-aligned.
    const lengths = out.data.map((row) => row.length);
    expect(lengths).toEqual([2, 2, 2]);
    expect(out.data[0]).toEqual([1, 2]); // newest x (oldest sample dropped)
    expect(out.data[1]).toEqual([11, 12]); // loop 1 pv newest 2
    expect(out.data[2]).toEqual([40, 41]); // loop 2 co (already len 2)
    expect(out.keys).toHaveLength(2);
  });
});
