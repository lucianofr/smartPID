import { describe, expect, it } from 'vitest';
import { createWindowBuffer } from '@/lib/windowBuffer';

describe('createWindowBuffer', () => {
  it('rejects non-finite, non-increasing and minStep-close samples', () => {
    const buf = createWindowBuffer(1, { maxSeconds: Infinity, maxPoints: Infinity, minStep: 2 });
    expect(buf.push(0, [0])).toBe(true);
    expect(buf.push(0, [1])).toBe(false); // not strictly increasing
    expect(buf.push(1, [1])).toBe(false); // within minStep of 0
    expect(buf.push(2, [2])).toBe(true);
    expect(buf.push(Number.NaN, [3])).toBe(false);
    expect(buf.push(Number.POSITIVE_INFINITY, [3])).toBe(false);
  });

  it('trims by time window from the left, keeping the newest span', () => {
    const buf = createWindowBuffer(1, { maxSeconds: 10, maxPoints: Infinity });
    for (let t = 0; t <= 20; t += 1) buf.push(t, [t * 10]);
    expect(buf.length()).toBe(11); // t = 10..20
    expect(buf.view(100).data[0][0]).toBe(10);
    expect(buf.view(100).data[1][buf.length() - 1]).toBe(200);
  });

  it('trims by point cap', () => {
    const buf = createWindowBuffer(1, { maxSeconds: Infinity, maxPoints: 5 });
    for (let t = 0; t < 10; t += 1) buf.push(t, [t]);
    expect(buf.length()).toBe(5);
    expect(buf.view(10).data[0]).toEqual([5, 6, 7, 8, 9]);
  });

  it('exposes the undecimated latest sample as the pen tip', () => {
    const buf = createWindowBuffer(2, { maxSeconds: Infinity, maxPoints: Infinity });
    buf.push(1, [10, 20]);
    buf.push(2, [11, 21]);
    expect(buf.latest()).toEqual({ t: 2, values: [11, 21] });
    buf.clear();
    expect(buf.latest()).toBeNull();
    expect(buf.length()).toBe(0);
  });

  it('decimates to min/max per absolute-time bucket, preserving extrema', () => {
    const buf = createWindowBuffer(1, { maxSeconds: 40, maxPoints: Infinity });
    // Sawtooth: peaks at even t, troughs at odd t — both must survive decimation.
    const values = [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1];
    values.forEach((v, t) => buf.push(t, [v]));
    const view = buf.view(5); // 40s / 5px = 8s buckets → 3 buckets for t 0..19
    expect(view.decimated).toBe(true);
    // Bucket boundaries are a grid on absolute time: each bucket emits its own
    // min/max pair at the bucket's first/last sample time.
    expect(view.data[0]).toEqual([0, 7, 8, 15, 16, 19]);
    expect(view.data[1]).toEqual([0, 1, 0, 1, 0, 1]);
  });

  it('keeps a single-sample bucket as one point and returns undecimated copies when within pixel budget', () => {
    const buf = createWindowBuffer(1, { maxSeconds: Infinity, maxPoints: Infinity });
    buf.push(0, [5]);
    const raw = buf.view(10);
    expect(raw.decimated).toBe(false);
    expect(raw.data).toEqual([[0], [5]]);
  });
});
