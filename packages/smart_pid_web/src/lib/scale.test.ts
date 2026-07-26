import { describe, expect, it } from 'vitest';
import { ticks, valueToFraction, type Scale } from './scale';

const s: Scale = { euMin: 0, euMax: 200, unit: '°C' };

describe('valueToFraction', () => {
  it('maps and clamps into 0..1', () => {
    expect(valueToFraction(100, s)).toBe(0.5);
    expect(valueToFraction(-50, s)).toBe(0);
    expect(valueToFraction(400, s)).toBe(1);
  });

  it('degenerate span yields 0', () => {
    expect(valueToFraction(10, { euMin: 5, euMax: 5, unit: '' })).toBe(0);
  });
});

describe('ticks', () => {
  it('generates evenly spaced inclusive ticks (default 5)', () => {
    expect(ticks({ euMin: 0, euMax: 100, unit: '%' })).toEqual([0, 25, 50, 75, 100]);
  });

  it('respects count and the minimum of 2', () => {
    expect(ticks(s, 3)).toEqual([0, 100, 200]);
    expect(ticks(s, 1)).toEqual([0, 200]);
  });

  it('degenerate span collapses to [euMin, euMin]', () => {
    expect(ticks({ euMin: 7, euMax: 7, unit: '' })).toEqual([7, 7]);
  });
});