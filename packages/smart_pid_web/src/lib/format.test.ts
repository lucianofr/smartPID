import { describe, expect, it } from 'vitest';
import { formatNumber } from './format';

describe('formatNumber', () => {
  it('renders fixed decimals', () => {
    expect(formatNumber(150.234, 1)).toBe('150.2');
  });
  it('renders dash for null/NaN', () => {
    expect(formatNumber(null, 1)).toBe('—');
    expect(formatNumber(Number.NaN, 1)).toBe('—');
  });
  it('does not visually skip digits (always fixed)', () => {
    expect(formatNumber(5, 2)).toBe('5.00');
  });
});
