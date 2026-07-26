import { describe, expect, it } from 'vitest';
import { decimateHistory } from './decimate';

function ramp(n: number): { t: number[]; pv: number[] } {
  const t: number[] = [];
  const pv: number[] = [];
  for (let i = 0; i < n; i += 1) {
    t.push(i);
    pv.push(i % 7);
  }
  return { t, pv };
}

describe('decimateHistory', () => {
  it('passes a series shorter than the pixel width straight through', () => {
    const [t, pv] = decimateHistory([1, 2, 3], [[10, 20, 30]], 100);
    expect(t).toEqual([1, 2, 3]);
    expect(pv).toEqual([10, 20, 30]);
  });

  it('caps the output at two samples per pixel column plus the pinned endpoints', () => {
    const { t, pv } = ramp(5000);
    const [outT] = decimateHistory(t, [pv], 200);
    expect(outT.length).toBeLessThanOrEqual(200 * 2 + 2);
    expect(outT.length).toBeGreaterThan(200);
  });

  it('keeps the exact first and latest samples', () => {
    const { t, pv } = ramp(5000);
    // Endpoints are what an operator reads off the window edges, and min/max
    // bucketing has no reason to land on them.
    const [outT, outPv] = decimateHistory(t, [pv], 60);
    expect(outT[0]).toBe(t[0]);
    expect(outPv[0]).toBe(pv[0]);
    expect(outT[outT.length - 1]).toBe(t[t.length - 1]);
    expect(outPv[outPv.length - 1]).toBe(pv[pv.length - 1]);
  });

  it('preserves a one-sample transient', () => {
    const { t, pv } = ramp(4000);
    pv[1234] = 999;
    const [, outPv] = decimateHistory(t, [pv], 100);
    expect(outPv).toContain(999);
  });

  it('emits a monotonically ascending time column from unsorted input', () => {
    const { t, pv } = ramp(3000);
    const order = t.map((_, i) => i).reverse();
    const [outT] = decimateHistory(
      order.map((i) => t[i]),
      [order.map((i) => pv[i])],
      50,
    );
    expect(outT).toHaveLength(new Set(outT).size);
    for (let i = 1; i < outT.length; i += 1) expect(outT[i]).toBeGreaterThan(outT[i - 1]);
  });

  it('decimates every row against the same time column', () => {
    const { t, pv } = ramp(2000);
    const sp = pv.map((v) => v + 100);
    const [outT, outPv, outSp] = decimateHistory(t, [pv, sp], 80);
    expect(outPv).toHaveLength(outT.length);
    expect(outSp).toHaveLength(outT.length);
  });
});
