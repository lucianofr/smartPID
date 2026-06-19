import { describe, it, expect } from 'vitest';
import { validatePidParams, validateLimits, validateSetpoint, hasErrors } from '../validation';

describe('validatePidParams', () => {
  it('accepts physically valid params', () => {
    const e = validatePidParams({ gain: 1.2, reset: 10, rate: 0.5, alpha: 0.125, deadband: 0 });
    expect(hasErrors(e)).toBe(false);
  });
  it('rejects non-positive reset (Ti must be > 0)', () => {
    const e = validatePidParams({ gain: 1, reset: 0, rate: 0, alpha: 0.125, deadband: 0 });
    expect(e.reset).toMatch(/greater than 0/i);
  });
  it('rejects negative gain magnitude rule and NaN', () => {
    const e = validatePidParams({ gain: Number.NaN, reset: 10, rate: -1, alpha: 2, deadband: -1 });
    expect(e.gain).toBeDefined();
    expect(e.rate).toMatch(/0 or greater/i);
    expect(e.alpha).toMatch(/between 0 and 1/i);
    expect(e.deadband).toBeDefined();
  });
});

describe('validateLimits', () => {
  it('rejects out_lo >= out_hi', () => {
    const e = validateLimits({ out_hi_lim: 10, out_lo_lim: 20, arw_hi_lim: 100, arw_lo_lim: 0, pv_ftime: 0, sp_ftime: 0, sp_rate_up: 0, sp_rate_dn: 0 });
    expect(e.out_lo_lim).toMatch(/below/i);
  });
  it('rejects negative filter times', () => {
    const e = validateLimits({ out_hi_lim: 100, out_lo_lim: 0, arw_hi_lim: 100, arw_lo_lim: 0, pv_ftime: -1, sp_ftime: 0, sp_rate_up: 0, sp_rate_dn: 0 });
    expect(e.pv_ftime).toBeDefined();
  });
});

describe('validateSetpoint', () => {
  it('rejects NaN', () => { expect(validateSetpoint(Number.NaN)).toBeDefined(); });
  it('accepts finite', () => { expect(validateSetpoint(42)).toBeUndefined(); });
});
