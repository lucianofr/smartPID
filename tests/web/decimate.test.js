import { describe, expect, it } from 'vitest';
import { decimateHistory } from '@/features/multitrend/decimate';

describe('decimateHistory', () => {
  it('passes through when there are no rows or the pixel budget is not exceeded', () => {
    expect(decimateHistory([1, 2, 3], [], 10)).toEqual([[1, 2, 3]]);
    const out = decimateHistory([1, 2], [[10, 20]], 5);
    expect(out).toEqual([[1, 2], [10, 20]]);
  });

  it('sorts unsorted historian timestamps before decimating', () => {
    const out = decimateHistory([3, 1, 2], [[30, 10, 20]], 2);
    expect(out).toEqual([[1, 2, 3], [10, 20, 30]]);
  });

  it('pins the exact first and last samples at the window edges', () => {
    const t = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9];
    const rows = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]];
    const out = decimateHistory(t, rows, 3);
    expect(out[0][0]).toBe(0);
    expect(out[1][0]).toBe(0);
    expect(out[0][out[0].length - 1]).toBe(9);
    expect(out[1][out[1].length - 1]).toBe(9);
  });

  it('preserves bucket extrema for a spiky signal', () => {
    const t = [0, 1, 2, 3, 4, 5, 6, 7];
    const rows = [[10, 1, 2, 3, 4, 5, 6, 20]]; // spike at both ends
    const out = decimateHistory(t, rows, 2);
    const values = out[1];
    expect(Math.max(...values)).toBe(20);
    expect(Math.min(...values)).toBe(1);
    expect(out[0]).toEqual(out[0].slice().sort((a, b) => a - b)); // ascending x
  });
});
