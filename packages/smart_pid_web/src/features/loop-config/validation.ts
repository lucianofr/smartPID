import type {
  AiConfigForm,
  FieldErrors,
  LimitsForm,
  PidParamsForm,
  Range,
  TuningForm,
} from './types';

/**
 * Client-side command and configuration checks (§11). These exist to keep a
 * doomed write off the wire and to put the message next to the field; the
 * backend re-validates everything and stays the authority.
 */

/** CO is always a valve percentage — the scale is fixed, never per-loop. */
const CO_MIN = 0;
const CO_MAX = 100;

export function validateSetpoint(value: number, range?: Range): string | undefined {
  if (!Number.isFinite(value)) return 'Setpoint deve ser um número';
  if (range === undefined) return undefined;
  if (value < range.min || value > range.max) {
    return `Setpoint deve estar entre ${range.min} e ${range.max}`;
  }
  return undefined;
}

export function validateOutput(value: number): string | undefined {
  if (!Number.isFinite(value)) return 'Saída deve ser um número';
  if (value < CO_MIN || value > CO_MAX) return `Saída deve estar entre ${CO_MIN} e ${CO_MAX}`;
  return undefined;
}

/** Td = 0 is a PI controller, not an error; Kp and Ti must be strictly positive. */
export function validateTuning(tuning: TuningForm): FieldErrors {
  const errors: FieldErrors = {};
  if (!Number.isFinite(tuning.kp) || tuning.kp <= 0) errors.kp = 'Kp deve ser maior que 0';
  if (!Number.isFinite(tuning.ti) || tuning.ti <= 0) errors.ti = 'Ti deve ser maior que 0';
  if (!Number.isFinite(tuning.td) || tuning.td < 0) errors.td = 'Td não pode ser negativo';
  return errors;
}

export function validatePidParams(pid: PidParamsForm): FieldErrors {
  const errors: FieldErrors = {};
  if (!Number.isFinite(pid.gain)) errors.gain = 'Ganho (Kp) deve ser um número';
  if (!Number.isFinite(pid.reset) || pid.reset <= 0) errors.reset = 'Reset (Ti) deve ser maior que 0';
  if (!Number.isFinite(pid.rate) || pid.rate < 0) errors.rate = 'Rate (Td) não pode ser negativo';
  if (!Number.isFinite(pid.alpha) || pid.alpha < 0 || pid.alpha > 1) {
    errors.alpha = 'Filtro derivativo (alpha) deve estar entre 0 e 1';
  }
  if (!Number.isFinite(pid.deadband) || pid.deadband < 0) errors.deadband = 'Banda morta não pode ser negativa';
  return errors;
}

const NON_NEGATIVE_LIMIT_FIELDS = ['pv_ftime', 'sp_ftime', 'sp_rate_up', 'sp_rate_dn'] as const;

/** Ordered low<high bands, then the non-negative filter/rate group. */
export function validateLimits(limits: LimitsForm): FieldErrors {
  const errors: FieldErrors = {};
  const band = (
    lo: keyof LimitsForm,
    hi: keyof LimitsForm,
    message: string,
  ): void => {
    if (!Number.isFinite(limits[lo])) errors[lo] = 'Deve ser um número';
    if (!Number.isFinite(limits[hi])) errors[hi] = 'Deve ser um número';
    if (Number.isFinite(limits[lo]) && Number.isFinite(limits[hi]) && limits[lo] >= limits[hi]) errors[lo] = message;
  };

  band('out_lo_lim', 'out_hi_lim', 'Limite inferior da saída deve ser menor que o superior');
  band('arw_lo_lim', 'arw_hi_lim', 'Limite inferior de ARW deve ser menor que o superior');

  for (const key of NON_NEGATIVE_LIMIT_FIELDS) {
    const value = limits[key];
    if (!Number.isFinite(value) || value < 0) errors[key] = 'Deve ser 0 ou maior';
  }
  return errors;
}

/**
 * Engineering ranges shown on the Limites tab. Unlike `validateLimits` these
 * apply in every execution mode: the PV/CO scales and the SP band are display
 * and operator-entry contracts, not DDC algorithm parameters.
 */
export interface EngineeringLimitsForm {
  pv_eu_min: number;
  pv_eu_max: number;
  co_eu_min: number;
  co_eu_max: number;
  sp_lo_lim: number;
  sp_hi_lim: number;
}

export function validateEngineeringLimits(form: EngineeringLimitsForm): FieldErrors {
  const errors: FieldErrors = {};
  const band = (
    lo: keyof EngineeringLimitsForm,
    hi: keyof EngineeringLimitsForm,
    message: string,
  ): void => {
    if (!Number.isFinite(form[lo])) errors[lo] = 'Deve ser um número';
    if (!Number.isFinite(form[hi])) errors[hi] = 'Deve ser um número';
    if (Number.isFinite(form[lo]) && Number.isFinite(form[hi]) && form[lo] >= form[hi]) {
      errors[lo] = message;
    }
  };

  band('pv_eu_min', 'pv_eu_max', 'Limite inferior da PV deve ser menor que o superior');
  band('co_eu_min', 'co_eu_max', 'Limite inferior do CO deve ser menor que o superior');
  band('sp_lo_lim', 'sp_hi_lim', 'Limite inferior do SP deve ser menor que o superior');

  return errors;
}

/**
 * Surge Level only. The band is what keeps the tank inside its safe window,
 * so an inverted or out-of-range band must never reach the engine — it would
 * silently fall back to 20-80 and quietly tune against a different band than
 * the one on screen.
 */
function validateSurgeLevel(ai: AiConfigForm): FieldErrors {
  const errors: FieldErrors = {};
  const bounds = [
    ['sl_band_lo_pct', ai.sl_band_lo_pct],
    ['sl_band_hi_pct', ai.sl_band_hi_pct],
  ] as const;
  for (const [key, value] of bounds) {
    if (value === null || value === undefined) continue;
    if (!Number.isFinite(value) || value < 0 || value > 100) {
      errors[key] = 'Deve estar entre 0 e 100';
    }
  }
  const lo = ai.sl_band_lo_pct;
  const hi = ai.sl_band_hi_pct;
  if (
    typeof lo === 'number' &&
    typeof hi === 'number' &&
    Number.isFinite(lo) &&
    Number.isFinite(hi) &&
    lo >= hi
  ) {
    errors.sl_band_lo_pct = 'Limite inferior deve ser menor que o superior';
  }
  const small = ai.sl_error_small_pct;
  if (small !== undefined && (!Number.isFinite(small) || small <= 0)) {
    errors.sl_error_small_pct = 'Deve ser maior que 0';
  }
  const ramp = ai.sl_co_ramp_max_pct_min;
  if (ramp !== undefined && (!Number.isFinite(ramp) || ramp < 0)) {
    errors.sl_co_ramp_max_pct_min = 'Deve ser 0 ou maior';
  }
  return errors;
}

/** With the engine off the guardrails are inert — do not block a save on them. */
export function validateAiConfig(ai: AiConfigForm): FieldErrors {
  if (ai.engine === 'NONE') return {};
  const errors: FieldErrors = {};
  if (!Number.isFinite(ai.dead_time_l) || ai.dead_time_l < 0) {
    errors.dead_time_l = 'Tempo morto L não pode ser negativo';
  }
  if (!Number.isFinite(ai.limit_min)) errors.limit_min = 'Deve ser um número';
  if (!Number.isFinite(ai.limit_max)) errors.limit_max = 'Deve ser um número';
  if (Number.isFinite(ai.limit_min) && Number.isFinite(ai.limit_max) && ai.limit_min >= ai.limit_max) {
    errors.limit_min = 'Limite mínimo deve ser menor que o máximo';
  }
  if (ai.objective === 'SURGE_LEVEL') {
    Object.assign(errors, validateSurgeLevel(ai));
  }
  return errors;
}

export function hasErrors(errors: FieldErrors): boolean {
  return Object.values(errors).some((message) => message !== undefined);
}
