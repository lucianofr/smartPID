import { describe, it, expect } from 'vitest';
import { signalId, parseSignalId, seriesColor, DEFAULT_WINDOW } from './signals';

describe('signalId', () => {
  it('round-trips loop + variable', () => {
    const id = signalId({ loopId: 3, variable: 'pv' });
    expect(id).toBe('3:pv');
    expect(parseSignalId(id)).toEqual({ loopId: 3, variable: 'pv' });
  });
});

describe('seriesColor', () => {
  it('uses the PV/SP/CO token var, tonally varied per loop', () => {
    const a = seriesColor({ loopId: 1, variable: 'pv' });
    const b = seriesColor({ loopId: 2, variable: 'pv' });
    // same variable → same token base, different loop → different lightness modifier
    expect(a.tokenVar).toBe('--trend-pv');
    expect(b.tokenVar).toBe('--trend-pv');
    expect(a.lightnessPct).not.toBe(b.lightnessPct);
  });

  it('maps each variable to its theme token', () => {
    expect(seriesColor({ loopId: 1, variable: 'sp' }).tokenVar).toBe('--trend-sp');
    expect(seriesColor({ loopId: 1, variable: 'co' }).tokenVar).toBe('--trend-co');
  });
});

describe('DEFAULT_WINDOW', () => {
  it('is 600 points / 60 seconds per design-system §7.2', () => {
    expect(DEFAULT_WINDOW).toEqual({ maxPoints: 600, maxSeconds: 60 });
  });
});
