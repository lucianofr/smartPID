import { describe, expect, it } from 'vitest';
import { clampToScale, ticks, valueToFraction, valueToPercent } from '@/lib/scale';

const scale = { euMin: 0, euMax: 100, unit: '%' };

describe('valueToFraction', () => {
  it('clamps to 0..1 and returns 0 on a degenerate span', () => {
    expect(valueToFraction(50, scale)).toBe(0.5);
    expect(valueToFraction(-10, scale)).toBe(0);
    expect(valueToFraction(150, scale)).toBe(1);
    expect(valueToFraction(50, { euMin: 50, euMax: 50, unit: '%' })).toBe(0);
  });
});

describe('ticks', () => {
  it('generates count evenly spaced values inclusive of both bounds', () => {
    const out = ticks(scale, 5);
    expect(out).toHaveLength(5);
    expect(out[0]).toBe(0);
    expect(out[4]).toBe(100);
    expect(out[2]).toBe(50);
  });

  it('floors count to >= 2 and handles degenerate spans', () => {
    expect(ticks(scale, 1)).toHaveLength(2);
    expect(ticks({ euMin: 5, euMax: 5, unit: '' }, 5)).toEqual([5, 5]);
  });
});

describe('valueToPercent / clampToScale', () => {
  it('converts fraction to percent and clamps raw EU values', () => {
    expect(valueToPercent(75, scale)).toBe(75);
    expect(clampToScale(-5, scale)).toBe(0);
    expect(clampToScale(120, scale)).toBe(100);
    expect(clampToScale(42, scale)).toBe(42);
  });
});
