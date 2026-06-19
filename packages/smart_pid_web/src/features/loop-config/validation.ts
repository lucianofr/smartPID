import type { PidParamsForm, LimitsForm, FieldErrors } from './types';

const finite = (n: number) => Number.isFinite(n);

export function validatePidParams(p: PidParamsForm): FieldErrors {
  const e: FieldErrors = {};
  if (!finite(p.gain)) e.gain = 'Gain (Kp) must be a number';
  if (!finite(p.reset) || p.reset <= 0) e.reset = 'Reset (Ti) must be greater than 0';
  if (!finite(p.rate) || p.rate < 0) e.rate = 'Rate (Td) must be 0 or greater';
  if (!finite(p.alpha) || p.alpha < 0 || p.alpha > 1) e.alpha = 'Derivative filter (alpha) must be between 0 and 1';
  if (!finite(p.deadband) || p.deadband < 0) e.deadband = 'Deadband must be 0 or greater';
  return e;
}

export function validateLimits(l: LimitsForm): FieldErrors {
  const e: FieldErrors = {};
  if (!finite(l.out_hi_lim)) e.out_hi_lim = 'Output high limit must be a number';
  if (!finite(l.out_lo_lim)) e.out_lo_lim = 'Output low limit must be a number';
  if (finite(l.out_hi_lim) && finite(l.out_lo_lim) && l.out_lo_lim >= l.out_hi_lim)
    e.out_lo_lim = 'Output low limit must be below the high limit';
  if (finite(l.arw_hi_lim) && finite(l.arw_lo_lim) && l.arw_lo_lim >= l.arw_hi_lim)
    e.arw_lo_lim = 'ARW low limit must be below the ARW high limit';
  for (const k of ['pv_ftime', 'sp_ftime', 'sp_rate_up', 'sp_rate_dn'] as const) {
    const v = l[k];
    if (!finite(v) || v < 0) e[k] = 'Must be 0 or greater';
  }
  return e;
}

export function validateSetpoint(v: number): string | undefined {
  return Number.isFinite(v) ? undefined : 'Setpoint must be a number';
}
export function validateOutput(v: number): string | undefined {
  if (!Number.isFinite(v)) return 'Output must be a number';
  if (v < 0 || v > 100) return 'Output must be between 0 and 100 %';
  return undefined;
}
export function hasErrors(e: FieldErrors): boolean {
  return Object.values(e).some((m) => m !== undefined);
}
