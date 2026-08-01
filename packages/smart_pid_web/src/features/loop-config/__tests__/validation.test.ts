import { describe, expect, it } from 'vitest';
import {
  hasErrors,
  validateAiConfig,
  validateLimits,
  validateOutput,
  validatePidParams,
  validateSetpoint,
  validateTuning,
} from '../validation';

describe('validateSetpoint', () => {
  it('rejects a value outside the engineering range', () => {
    expect(validateSetpoint(-1, { min: 0, max: 100 })).toBe('Setpoint deve estar entre 0 e 100');
    expect(validateSetpoint(300, { min: 0, max: 200 })).toBe('Setpoint deve estar entre 0 e 200');
  });

  it('accepts the inclusive bounds and anything between them', () => {
    expect(validateSetpoint(0, { min: 0, max: 100 })).toBeUndefined();
    expect(validateSetpoint(100, { min: 0, max: 100 })).toBeUndefined();
    expect(validateSetpoint(55.5, { min: 0, max: 100 })).toBeUndefined();
  });

  it('only checks finiteness when no range is supplied', () => {
    expect(validateSetpoint(9999)).toBeUndefined();
    expect(validateSetpoint(Number.NaN)).toBe('Setpoint deve ser um número');
  });
});

describe('validateOutput', () => {
  it('holds CO to the 0-100 % valve span', () => {
    expect(validateOutput(101)).toBe('Saída deve estar entre 0 e 100');
    expect(validateOutput(-0.5)).toBe('Saída deve estar entre 0 e 100');
    expect(validateOutput(0)).toBeUndefined();
    expect(validateOutput(100)).toBeUndefined();
  });

  it('rejects a non-numeric entry', () => {
    expect(validateOutput(Number.NaN)).toBe('Saída deve ser um número');
  });
});

describe('validateTuning', () => {
  it('reports every offending gain at once', () => {
    expect(validateTuning({ kp: 0, ti: 0, td: -1 })).toEqual({
      kp: 'Kp deve ser maior que 0',
      ti: 'Ti deve ser maior que 0',
      td: 'Td não pode ser negativo',
    });
  });

  it('accepts a usable set (Td may be zero — PI is a valid controller)', () => {
    expect(validateTuning({ kp: 1.2, ti: 30, td: 0 })).toEqual({});
  });
});

describe('validatePidParams', () => {
  const ok = { gain: 1.2, reset: 30, rate: 0, alpha: 0.125, deadband: 0 };

  it('accepts the schema defaults', () => {
    expect(validatePidParams(ok)).toEqual({});
  });

  it('keeps alpha inside the 0-1 derivative-filter span', () => {
    expect(validatePidParams({ ...ok, alpha: 1.5 }).alpha).toBe(
      'Filtro derivativo (alpha) deve estar entre 0 e 1',
    );
    expect(validatePidParams({ ...ok, alpha: 1 }).alpha).toBeUndefined();
  });

  it('requires a positive reset and a non-negative rate and deadband', () => {
    const e = validatePidParams({ ...ok, reset: 0, rate: -1, deadband: -2 });
    expect(e.reset).toBe('Reset (Ti) deve ser maior que 0');
    expect(e.rate).toBe('Rate (Td) não pode ser negativo');
    expect(e.deadband).toBe('Banda morta não pode ser negativa');
  });
});

describe('validateLimits', () => {
  const ok = {
    out_hi_lim: 100,
    out_lo_lim: 0,
    arw_hi_lim: 100,
    arw_lo_lim: 0,
    sp_hi_lim: 100,
    sp_lo_lim: 0,
    pv_ftime: 0,
    sp_ftime: 0,
    sp_rate_up: 0,
    sp_rate_dn: 0,
  };

  it('accepts the schema defaults', () => {
    expect(validateLimits(ok)).toEqual({});
  });

  it('requires every low limit to sit below its high limit', () => {
    expect(validateLimits({ ...ok, out_lo_lim: 100 }).out_lo_lim).toBe(
      'Limite inferior da saída deve ser menor que o superior',
    );
    expect(validateLimits({ ...ok, arw_lo_lim: 120 }).arw_lo_lim).toBe(
      'Limite inferior de ARW deve ser menor que o superior',
    );
    expect(validateLimits({ ...ok, sp_lo_lim: 100 }).sp_lo_lim).toBe(
      'Limite inferior do SP deve ser menor que o superior',
    );
  });

  it('rejects negative filter times and SP rate limits', () => {
    const e = validateLimits({ ...ok, pv_ftime: -1, sp_rate_up: -2 });
    expect(e.pv_ftime).toBe('Deve ser 0 ou maior');
    expect(e.sp_rate_up).toBe('Deve ser 0 ou maior');
  });
});

describe('validateAiConfig', () => {
  const ok = { engine: 'FUZZY' as const, dead_time_l: 5, limit_min: 0.5, limit_max: 2 };

  it('skips every guardrail check when the engine is off', () => {
    expect(validateAiConfig({ ...ok, engine: 'NONE', dead_time_l: -9, limit_min: 9, limit_max: 1 })).toEqual(
      {},
    );
  });

  it('requires an ordered guardrail band and a non-negative dead time', () => {
    expect(validateAiConfig(ok)).toEqual({});
    expect(validateAiConfig({ ...ok, limit_min: 2, limit_max: 2 }).limit_min).toBe(
      'Limite mínimo deve ser menor que o máximo',
    );
    expect(validateAiConfig({ ...ok, dead_time_l: -1 }).dead_time_l).toBe(
      'Tempo morto L não pode ser negativo',
    );
  });

  it('ignores the surge band unless the objective is SURGE_LEVEL', () => {
    const inverted = { ...ok, sl_band_lo_pct: 80, sl_band_hi_pct: 20 };
    expect(validateAiConfig({ ...inverted, objective: 'SP_TRACKING' })).toEqual({});
    expect(
      validateAiConfig({ ...inverted, objective: 'SURGE_LEVEL' }).sl_band_lo_pct,
    ).toBe('Limite inferior deve ser menor que o superior');
  });

  it('accepts an unset surge band — the engine defaults to 20-80', () => {
    expect(
      validateAiConfig({
        ...ok,
        objective: 'SURGE_LEVEL',
        sl_band_lo_pct: null,
        sl_band_hi_pct: null,
        sl_error_small_pct: 5,
        sl_co_ramp_max_pct_min: 10,
      }),
    ).toEqual({});
  });

  it('rejects a surge band outside 0-100 % of span', () => {
    const surge = { ...ok, objective: 'SURGE_LEVEL' as const };
    expect(validateAiConfig({ ...surge, sl_band_hi_pct: 140 }).sl_band_hi_pct).toBe(
      'Deve estar entre 0 e 100',
    );
    expect(validateAiConfig({ ...surge, sl_band_lo_pct: -5 }).sl_band_lo_pct).toBe(
      'Deve estar entre 0 e 100',
    );
  });

  it('rejects a zero small-error threshold and a negative CO ramp', () => {
    const surge = { ...ok, objective: 'SURGE_LEVEL' as const };
    expect(validateAiConfig({ ...surge, sl_error_small_pct: 0 }).sl_error_small_pct).toBe(
      'Deve ser maior que 0',
    );
    expect(
      validateAiConfig({ ...surge, sl_co_ramp_max_pct_min: -1 }).sl_co_ramp_max_pct_min,
    ).toBe('Deve ser 0 ou maior');
  });

  it('accepts 0 as "CO ramp gate disabled"', () => {
    expect(
      validateAiConfig({ ...ok, objective: 'SURGE_LEVEL', sl_co_ramp_max_pct_min: 0 }),
    ).toEqual({});
  });
});

describe('hasErrors', () => {
  it('ignores undefined slots', () => {
    expect(hasErrors({})).toBe(false);
    expect(hasErrors({ kp: undefined })).toBe(false);
    expect(hasErrors({ kp: 'Kp deve ser maior que 0' })).toBe(true);
  });
});
