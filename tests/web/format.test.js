import { describe, expect, it } from 'vitest';
import {
  formatDateTime,
  formatNumber,
  formatPercent,
  formatTimestamp,
  formatWithUnit,
} from '@/lib/format';

describe('formatNumber', () => {
  it('renders fixed decimals and em dash for absent or NaN values', () => {
    expect(formatNumber(150.25, 1)).toBe('150.3');
    expect(formatNumber(null, 2)).toBe('—');
    expect(formatNumber(undefined, 2)).toBe('—');
    expect(formatNumber(Number.NaN, 2)).toBe('—');
  });
});

describe('formatWithUnit', () => {
  it('appends the unit suffix only for present finite values', () => {
    expect(formatWithUnit(150.3, '°C', 1)).toBe('150.3 °C');
    expect(formatWithUnit(null, '°C', 1)).toBe('—');
    expect(formatWithUnit(Number.POSITIVE_INFINITY, '°C', 1)).toBe('—');
    expect(formatWithUnit(5, '', 0)).toBe('5');
  });
});

describe('formatPercent', () => {
  it('maps ratio to percent string, em dash on absence', () => {
    expect(formatPercent(0.1234)).toBe('12.3%');
    expect(formatPercent(1)).toBe('100.0%');
    expect(formatPercent(null)).toBe('—');
    expect(formatPercent(Number.NaN)).toBe('—');
  });
});

describe('formatTimestamp', () => {
  it('accepts epoch seconds and ISO strings, em dash on garbage', () => {
    const d = new Date('2026-08-06T14:32:07Z');
    expect(formatTimestamp(d.getTime() / 1000)).toBe(
      formatTimestamp(d.toISOString()),
    );
    expect(formatTimestamp('not-a-date')).toBe('—');
    expect(formatTimestamp(null)).toBe('—');
  });
});

describe('formatDateTime', () => {
  it('includes the date prefix and reuses HH:MM:SS', () => {
    const d = new Date(2026, 7, 6, 14, 32, 7); // local
    const out = formatDateTime(d.getTime() / 1000);
    expect(out).toContain('14:32:07');
    expect(out).toContain(`${String(d.getDate()).padStart(2, '0')}/08/2026`);
  });
});
