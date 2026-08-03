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
    // ≤ 2 per pixel column, plus the one extra cell a window of length L can
    // straddle on an absolute-time grid of cell L/pxWidth.
    expect(view.data[0].length).toBeLessThanOrEqual(50 * 2 + 2);
    expect(view.data[1]).toContain(9999); // the spike survives
    const xs = view.data[0];
    for (let i = 1; i < xs.length; i += 1) expect(xs[i]).toBeGreaterThanOrEqual(xs[i - 1]);
  });

  it('decimation adds no direction reversals to a monotonic series', () => {
    // The sawtooth bug: the min/max pair used to be ordered by series 0's
    // direction and stamped with series 0's timing, so every OTHER series had
    // its fine structure inverted wherever it disagreed with series 0 — which
    // for CO, anti-correlated with PV by construction, is most of the trace.
    // Measured on a real 10-min ring: 775 reversals injected into a CO trace
    // that had none, peaks of 29 EU.
    const b = createWindowBuffer(2, WIDE);
    const N = 6000;
    for (let i = 0; i < N; i += 1) {
      // Series 0 rises, series 1 falls: strictly monotonic, opposite senses.
      b.push(i, [i, N - i]);
    }
    const { data, decimated } = b.view(1000);
    expect(decimated).toBe(true);

    const reversals = (a: readonly number[]): number => {
      let count = 0;
      let dir = 0;
      for (let i = 1; i < a.length; i += 1) {
        const d = a[i] - a[i - 1];
        if (d === 0) continue;
        const s = d > 0 ? 1 : -1;
        if (dir !== 0 && s !== dir) count += 1;
        dir = s;
      }
      return count;
    };
    expect(reversals(data[1])).toBe(0);
    expect(reversals(data[2])).toBe(0);
    // Endpoints stay exact: a monotonic bucket's extremes ARE its boundaries.
    expect(data[1][0]).toBe(0);
    expect(data[1][data[1].length - 1]).toBe(N - 1);
    expect(data[2][0]).toBe(N);
    expect(data[2][data[2].length - 1]).toBe(1);
    // x strictly ascending — the pair sits on the bucket's own bounds.
    for (let i = 1; i < data[0].length; i += 1) {
      expect(data[0][i]).toBeGreaterThan(data[0][i - 1]);
    }
  });

  it('leaves already-plotted history immobile as the window slides', () => {
    // The distortion: bucket boundaries were anchored to array indices, so they
    // shifted on every push and every trim. Each column then recomputed its
    // min/max over a different set of samples on every frame, and a point
    // already on screen moved in Y — the chart drew values that were never
    // recorded. Worst case measured on a real 10-min ring: CO 35.5 EU, SP 16.5.
    const HZ = 10;
    const WINDOW = 600;
    const PX = 500;
    const b = createWindowBuffer(1, { maxSeconds: WINDOW, maxPoints: 40_000 });
    // Fast local structure is what re-bucketing scrambles, so use a signal that
    // swings hard between adjacent samples rather than a smooth ramp.
    const signal = (i: number): number => (Math.floor(i / 3) % 2 === 0 ? 0 : 100);
    const t0 = 1_700_000_000;
    let i = 0;
    for (; i < WINDOW * HZ; i += 1) b.push(t0 + i / HZ, [signal(i)]);

    /** What the drawn polyline reads at time `at` — linear between columns. */
    const drawnAt = (data: number[][], at: number): number => {
      const [x, y] = data;
      if (at <= x[0]) return y[0];
      for (let k = 1; k < x.length; k += 1) {
        if (x[k] >= at) {
          const f = (at - x[k - 1]) / (x[k] - x[k - 1] || 1);
          return y[k - 1] + f * (y[k] - y[k - 1]);
        }
      }
      return y[y.length - 1];
    };

    // Probe points spread across the retained history, away from both edges:
    // the newest bucket is still filling and the oldest is being trimmed, so
    // those two are the only ones allowed to change.
    const probes = Array.from({ length: 40 }, (_, k) => t0 + WINDOW * (0.1 + 0.8 * (k / 39)));
    const firstPass = probes.map((at) => drawnAt(b.view(PX).data, at));

    for (let k = 0; k < 20; k += 1, i += 1) {
      b.push(t0 + i / HZ, [signal(i)]);
      const now = b.view(PX).data;
      probes.forEach((at, p) => {
        expect(drawnAt(now, at)).toBe(firstPass[p]);
      });
    }
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