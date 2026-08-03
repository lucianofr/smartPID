import type { ControllerMode } from '@/api/types';

/**
 * Loop-configuration vocabulary. Every literal list mirrors a
 * `smart_pid_domain.enums` StrEnum 1:1 — the backend rejects anything else, so
 * a drifted list here would only produce a 422 the operator cannot fix.
 */

export const CONTROLLER_MODES: readonly ControllerMode[] = [
  'OOS',
  'IMAN',
  'LO',
  'MAN',
  'AUTO',
  'CAS',
  'RCAS',
  'ROUT',
  'BYPASS',
];

export type AiEngine = 'NONE' | 'FUZZY' | 'RL';
export const AI_ENGINES: readonly AiEngine[] = ['NONE', 'FUZZY', 'RL'];

export type ControlObjective = 'SP_TRACKING' | 'DISTURBANCE_REJECTION' | 'SURGE_LEVEL';
export const OBJECTIVES: readonly ControlObjective[] = [
  'SP_TRACKING',
  'DISTURBANCE_REJECTION',
  'SURGE_LEVEL',
];

export type ProcessSpeed = 'ULTRA_FAST' | 'FAST' | 'MEDIUM' | 'SLOW';
export const PROCESS_SPEEDS: readonly ProcessSpeed[] = ['ULTRA_FAST', 'FAST', 'MEDIUM', 'SLOW'];

export type ExecutionMode = 'SUPERVISORY' | 'DDC';
export const EXECUTION_MODES: readonly ExecutionMode[] = ['SUPERVISORY', 'DDC'];

export type PidStructure = 'ISA' | 'PARALLEL' | 'SERIES';
export const PID_STRUCTURES: readonly PidStructure[] = ['ISA', 'PARALLEL', 'SERIES'];

export type IntegralType = 'GAIN_KI' | 'TIME_TI';
/**
 * How the loop parametrises the integral term. The label is what the operator
 * picks; the value is the `IntegralType` StrEnum member the backend accepts.
 */
export const INTEGRAL_TYPE_OPTIONS: readonly { value: IntegralType; label: string }[] = [
  { value: 'TIME_TI', label: 'Tempo Integral (Ti)' },
  { value: 'GAIN_KI', label: 'Ganho Integral (Ki)' },
];

/** `shed_opt` — the mode the loop falls back to when the IO link sheds. */
export const SHED_OPTIONS: readonly ControllerMode[] = ['MAN', 'AUTO', 'IMAN', 'LO'];

/** Inclusive engineering bounds used by the setpoint check. */
export interface Range {
  min: number;
  max: number;
}

export interface PidParamsForm {
  gain: number;
  reset: number;
  rate: number;
  alpha: number;
  deadband: number;
}

export interface LimitsForm {
  out_hi_lim: number;
  out_lo_lim: number;
  arw_hi_lim: number;
  arw_lo_lim: number;
  sp_hi_lim: number;
  sp_lo_lim: number;
  pv_ftime: number;
  sp_ftime: number;
  sp_rate_up: number;
  sp_rate_dn: number;
}

/** Only the guardrail slice the AI panel edits; the RL knobs stay server-side. */
export interface AiConfigForm {
  engine: AiEngine;
  dead_time_l: number;
  limit_min: number;
  limit_max: number;
  /**
   * Surge Level band. Only meaningful when `objective` is SURGE_LEVEL, and
   * optional so callers that only touch the guardrails stay untouched.
   * `null` on a bound means "let the engine use its 20-80 % default".
   */
  objective?: ControlObjective;
  sl_band_lo_pct?: number | null;
  sl_band_hi_pct?: number | null;
  sl_error_small_pct?: number;
  sl_co_ramp_max_pct_min?: number;
}

export interface TuningForm {
  kp: number;
  ti: number;
  td: number;
}

export type FieldErrors = Record<string, string | undefined>;

export type { ControllerMode };
