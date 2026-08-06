import { describe, expect, it } from 'vitest';
import {
  hasErrors,
  validateLimits,
  validateOutput,
  validatePidParams,
  validateSetpoint,
  validateTuning,
} from '@/features/loop-config/validation';

describe('validateSetpoint', () => {
  it('rejects non-finite values and out-of-range setpoints', () => {
    expect(validateSetpoint(50, { min: 0, max: 100 })).toBeUndefined();
    expect(validateSetpoint(101, { min: 0, max: 100 })).toMatch(/entre/);
    expect(validateSetpoint(Number.NaN, { min: 0, max: 100 })).toMatch(/número/);
  });
});

describe('validateOutput', () => {
  it('keeps CO inside the fixed 0..100 valve scale', () => {
    expect(validateOutput(0)).toBeUndefined();
    expect(validateOutput(100)).toBeUndefined();
    expect(validateOutput(-1)).toMatch(/entre/);
    expect(validateOutput(101)).toMatch(/entre/);
    expect(validateOutput(Number.POSITIVE_INFINITY)).toMatch(/número/);
  });
});

describe('validateTuning', () => {
  it('requires strictly positive Kp/Ti; Td = 0 is a valid PI controller', () => {
    expect(validateTuning({ kp: 1, ti: 2, td: 0 })).toEqual({});
    expect(validateTuning({ kp: 0, ti: 2, td: 0 }).kp).toMatch(/maior/);
    expect(validateTuning({ kp: 1, ti: -1, td: 0 }).ti).toMatch(/maior/);
    expect(validateTuning({ kp: 1, ti: 2, td: -1 }).td).toMatch(/negativo/);
  });
});

describe('validatePidParams', () => {
  it('checks gain/reset/rate/alpha/deadband bounds', () => {
    expect(
      validatePidParams({ gain: 1, reset: 1, rate: 0, alpha: 0.5, deadband: 0 }),
    ).toEqual({});
    expect(validatePidParams({ gain: 1, reset: 0, rate: 0, alpha: 0.5, deadband: 0 }).reset).toMatch(/maior/);
    expect(validatePidParams({ gain: 1, reset: 1, rate: 0, alpha: 2, deadband: 0 }).alpha).toMatch(/entre/);
    expect(validatePidParams({ gain: 1, reset: 1, rate: 0, alpha: 0.5, deadband: -1 }).deadband).toMatch(/negativa/);
  });
});

describe('validateLimits', () => {
  it('requires ordered low<high bands and non-negative filter/rate fields', () => {
    const ok = {
      out_lo_lim: 0,
      out_hi_lim: 100,
      arw_lo_lim: 0,
      arw_hi_lim: 100,
      sp_lo_lim: 0,
      sp_hi_lim: 100,
      pv_ftime: 1,
      sp_ftime: 1,
      sp_rate_up: 1,
      sp_rate_dn: 1,
    };
    expect(validateLimits(ok)).toEqual({});
    const inverted = { ...ok, out_lo_lim: 100, out_hi_lim: 0 };
    expect(validateLimits(inverted).out_lo_lim).toMatch(/menor/);
    expect(validateLimits({ ...ok, sp_rate_up: -1 }).sp_rate_up).toMatch(/0 ou maior/);
  });
});

describe('hasErrors', () => {
  it('is true when any field carries a message', () => {
    expect(hasErrors({})).toBe(false);
    expect(hasErrors({ kp: undefined, ti: 'Ti deve ser maior que 0' })).toBe(true);
  });
});
