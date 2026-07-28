import { describe, expect, it } from 'vitest';
import { createWindowBuffer } from './windowBuffer';

const WIDE = { maxSeconds: Number.POSITIVE_INFINITY, maxPoints: Number.POSITIVE_INFINITY };

describe('createWindowBuffer', () => {
  it('stores pushed samples and reports length', () => {
    const b = createWindowBuffer(3, WIDE);
    expect(b.push(1, [10, 20, 30])).toBe(true);
    expect(b.push(2, [11, 21, 31])).toBe(true);
    expect(b.length()).toBe(2);
    expect(b.view(100).data).toEqual([
      [1, 2],
      [10, 11],
      [20, 21],
      [30, 31],
    ]);
  });

  it('rejects non-monotonic and non-finite timestamps (uPlot x must ascend)', () => {
    const b = createWindowBuffer(1, WIDE);
    b.push(5, [1]);
    expect(b.push(5, [2])).toBe(false);
    expect(b.push(4, [3])).toBe(false);
    expect(b.push(Number.NaN, [4])).toBe(false);
    expect(b.length()).toBe(1);
  });

  it('throws on wrong series arity', () => {
    const b = createWindowBuffer(2, WIDE);
    expect(() => b.push(1, [1])).toThrow(RangeError);
  });

  it('trims by time window, dropping from the left', () => {
    const b = createWindowBuffer(1, { maxSeconds: 10, maxPoints: Number.POSITIVE_INFINITY });
    b.push(0, [0]);
    b.push(5, [5]);
    b.push(20, [20]); // cutoff = 20 - 10 = 10 → drops t=0 and t=5
    expect(b.view(100).data[0]).toEqual([20]);
  });

  it('enforces the hard point cap after the time window', () => {
    const b = createWindowBuffer(1, { maxSeconds: Number.POSITIVE_INFINITY, maxPoints: 3 });
    for (let t = 1; t <= 5; t += 1) b.push(t, [t]);
    expect(b.view(100).data[0]).toEqual([3, 4, 5]);
  });

  it('latest() returns the undecimated newest sample — the §6.7 pen tip', () => {
    const b = createWindowBuffer(1, WIDE);
    // 400 samples into 100 px: min/max decimation keeps bucket extremes only.
    for (let i = 0; i < 400; i += 1) b.push(i, [Math.sin(i / 7) * 100]);
    // Final sample is mid-range: a min/max pick would typically drop it.
    b.push(400, [0.123]);
    const view = b.view(100);
    expect(view.decimated).toBe(true);
    expect(b.latest()).toEqual({ t: 400, values: [0.123] });
  });

  it('decimation preserves bucket extremes (transients survive)', () => {
    const b = createWindowBuffer(1, WIDE);
    for (let i = 0; i < 1000; i += 1) b.push(i, [i === 500 ? 9999 : 0]);
    const view = b.view(50);
    expect(view.decimated).toBe(true);
    expect(view.data[0].length).toBeLessThanOrEqual(100); // ≤ 2 per pixel column
    expect(view.data[1]).toContain(9999); // the spike survives
    const xs = view.data[0];
    for (let i = 1; i < xs.length; i += 1) expect(xs[i]).toBeGreaterThanOrEqual(xs[i - 1]);
  });

  it('view() below the pixel threshold is a verbatim, defensive copy', () => {
    const b = createWindowBuffer(1, WIDE);
    b.push(1, [10]);
    const view = b.view(100);
    expect(view.decimated).toBe(false);
    view.data[0].push(999); // mutating the view must not corrupt the buffer
    expect(b.view(100).data[0]).toEqual([1]);
  });

  it('clear() empties the buffer', () => {
    const b = createWindowBuffer(2, WIDE);
    b.push(1, [1, 2]);
    b.clear();
    expect(b.length()).toBe(0);
    expect(b.latest()).toBeNull();
  });
});