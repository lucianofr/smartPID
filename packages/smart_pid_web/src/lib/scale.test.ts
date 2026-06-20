import { describe, it, expect } from 'vitest';
import { valueToFraction } from './scale';

const scale = { euMin: 0, euMax: 200, unit: '°C' };

describe('valueToFraction', () => {
  it('maps mid-span to 0.5', () => {
    expect(valueToFraction(100, scale)).toBeCloseTo(0.5, 5);
  });
  it('maps min to 0 and max to 1', () => {
    expect(valueToFraction(0, scale)).toBe(0);
    expect(valueToFraction(200, scale)).toBe(1);
  });
  it('clamps below min and above max', () => {
    expect(valueToFraction(-50, scale)).toBe(0);
    expect(valueToFraction(250, scale)).toBe(1);
  });
  it('monotonic: higher PV -> higher fraction', () => {
    expect(valueToFraction(150, scale)).toBeGreaterThan(valueToFraction(50, scale));
  });
  it('handles a non-zero min span (e.g. 4-20 range)', () => {
    expect(valueToFraction(12, { euMin: 4, euMax: 20, unit: 'mA' })).toBeCloseTo(0.5, 5);
  });
  it('degenerate span returns 0 (no div-by-zero)', () => {
    expect(valueToFraction(5, { euMin: 10, euMax: 10, unit: '' })).toBe(0);
  });
});
