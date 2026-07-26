import { describe, expect, it } from 'vitest';
import { formatNumber } from './format';

describe('formatNumber (tabular fixed-decimal, §6.2)', () => {
  it('formats with fixed decimals', () => {
    expect(formatNumber(1.234, 2)).toBe('1.23');
    expect(formatNumber(150.25, 1)).toBe('150.3');
    expect(formatNumber(5, 0)).toBe('5');
    expect(formatNumber(-42.1, 1)).toBe('-42.1');
  });

  it('renders the em dash for null/undefined/NaN', () => {
    expect(formatNumber(null, 1)).toBe('—');
    expect(formatNumber(undefined, 1)).toBe('—');
    expect(formatNumber(Number.NaN, 1)).toBe('—');
  });
});