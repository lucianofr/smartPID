import { describe, expect, it } from 'vitest';
import {
  formatNumber,
  formatPercent,
  formatTimestamp,
  formatWithUnit,
} from './format';

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

describe('formatWithUnit (phase-3 consolidation)', () => {
  it('appends the unit after a space', () => {
    expect(formatWithUnit(150.25, '°C', 1)).toBe('150.3 °C');
  });
  it('omits the unit for absent values', () => {
    expect(formatWithUnit(null, '°C', 1)).toBe('—');
    expect(formatWithUnit(undefined, 'bar', 2)).toBe('—');
    expect(formatWithUnit(Number.NaN, 'bar', 2)).toBe('—');
  });
  it('non-finite values render as absent (absorbs multitrend formatMetric policy)', () => {
    expect(formatWithUnit(Number.POSITIVE_INFINITY, '%', 1)).toBe('—');
  });
  it('empty unit yields the bare number', () => {
    expect(formatWithUnit(42, '', 0)).toBe('42');
  });
});

describe('formatPercent (absorbs multitrend formatVariabilityPct)', () => {
  it('renders a ratio as percent with one decimal by default', () => {
    expect(formatPercent(0.1234)).toBe('12.3%');
  });
  it('honours the decimals parameter', () => {
    expect(formatPercent(0.5, 0)).toBe('50%');
  });
  it('absent and non-finite ratios render as absent', () => {
    expect(formatPercent(null)).toBe('—');
    expect(formatPercent(undefined)).toBe('—');
    expect(formatPercent(Number.NaN)).toBe('—');
    expect(formatPercent(Number.POSITIVE_INFINITY)).toBe('—');
  });
});

describe('formatTimestamp', () => {
  const pad = (n: number) => String(n).padStart(2, '0');
  const hms = (d: Date) => `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;

  it('formats epoch seconds (envelope ts / monitor timestamps) as local HH:MM:SS', () => {
    const epoch = 1718743200.5;
    expect(formatTimestamp(epoch)).toBe(hms(new Date(epoch * 1000)));
  });
  it('formats ISO-8601 strings (worker timestamps) as local HH:MM:SS', () => {
    const iso = '2024-06-18T20:40:05.000Z';
    expect(formatTimestamp(iso)).toBe(hms(new Date(iso)));
  });
  it('invalid input renders as absent', () => {
    expect(formatTimestamp('not-a-date')).toBe('—');
    expect(formatTimestamp(null)).toBe('—');
    expect(formatTimestamp(undefined)).toBe('—');
    expect(formatTimestamp(Number.NaN)).toBe('—');
  });
});