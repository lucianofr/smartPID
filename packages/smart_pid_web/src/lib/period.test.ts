import { describe, it, expect } from 'vitest';
import { periodRange, PERIOD_OPTIONS } from './period';

describe('periodRange', () => {
  const now = new Date('2026-06-18T12:00:00.000Z');

  it('1h window ends at now and starts exactly one hour earlier (ISO-8601)', () => {
    const r = periodRange('1h', now);
    expect(r.endIso).toBe('2026-06-18T12:00:00.000Z');
    expect(r.startIso).toBe('2026-06-18T11:00:00.000Z');
    expect(r.key).toBe('1h');
  });

  it('7d window spans 604800 seconds', () => {
    const r = periodRange('7d', now);
    const span = (Date.parse(r.endIso) - Date.parse(r.startIso)) / 1000;
    expect(span).toBe(7 * 24 * 3600);
  });

  it('exposes a labelled option per PeriodKey with no duplicates', () => {
    const keys = PERIOD_OPTIONS.map((o) => o.key);
    expect(new Set(keys).size).toBe(keys.length);
    expect(keys).toEqual(['15m', '1h', '8h', '24h', '7d']);
  });
});
