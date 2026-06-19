import { describe, it, expect } from 'vitest';
import { applyWindow, minMaxDecimate } from './decimate';
import type { AlignedSeries } from './multiTrendData';

function ramp(n: number): AlignedSeries {
  const x = Array.from({ length: n }, (_, i) => i);
  const y = Array.from({ length: n }, (_, i) => i);
  return { keys: [{ loopId: 1, variable: 'pv' }], data: [x, y] };
}

describe('minMaxDecimate', () => {
  it('caps output to at most 2 points per pixel column', () => {
    const series = ramp(10_000);
    const pxWidth = 300;
    const out = minMaxDecimate(series, pxWidth);
    // min/max → at most 2 samples per column
    expect(out.data[0].length).toBeLessThanOrEqual(pxWidth * 2);
    expect(out.data[0].length).toBeGreaterThan(0);
    // same length across x and every series row
    out.data.forEach((row) => expect(row.length).toBe(out.data[0].length));
  });

  it('does not decimate when points already fit the pixel budget', () => {
    const series = ramp(120);
    const out = minMaxDecimate(series, 300);
    expect(out.data[0].length).toBe(120);
  });

  it('preserves transient peaks (min and max of a spike survive)', () => {
    const x = [0, 1, 2, 3, 4, 5, 6, 7];
    const y = [0, 0, 0, 99, 0, -99, 0, 0]; // one positive and one negative spike
    const series: AlignedSeries = { keys: [{ loopId: 1, variable: 'pv' }], data: [x, y] };
    const out = minMaxDecimate(series, 2); // force aggressive decimation
    const ys = out.data[1];
    expect(Math.max(...ys)).toBe(99);
    expect(Math.min(...ys)).toBe(-99);
  });
});

describe('applyWindow', () => {
  it('drops the left so at most maxPoints remain', () => {
    const out = applyWindow(ramp(5000), { maxPoints: 600, maxSeconds: 1e9 });
    expect(out.data[0].length).toBeLessThanOrEqual(600);
    // newest sample retained
    expect(out.data[0].at(-1)).toBe(4999);
  });

  it('drops samples older than maxSeconds relative to the newest', () => {
    const x = [0, 10, 20, 30, 40, 50];
    const y = [1, 2, 3, 4, 5, 6];
    const out = applyWindow(
      { keys: [{ loopId: 1, variable: 'pv' }], data: [x, y] },
      { maxPoints: 1e9, maxSeconds: 25 },
    );
    // newest=50, keep t >= 25 → [30,40,50]
    expect(out.data[0]).toEqual([30, 40, 50]);
    expect(out.data[1]).toEqual([4, 5, 6]);
  });
});
