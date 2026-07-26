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
  band('sp_lo_lim', 'sp_hi_lim', 'Limite inferior do SP deve ser menor que o superior');

  for (const key of NON_NEGATIVE_LIMIT_FIELDS) {
    const value = limits[key];
    if (!Number.isFinite(value) || value < 0) errors[key] = 'Deve ser 0 ou maior';
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
  return errors;
}

export function hasErrors(errors: FieldErrors): boolean {
  return Object.values(errors).some((message) => message !== undefined);
}
