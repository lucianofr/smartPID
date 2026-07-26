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
export const INTEGRAL_TYPES: readonly IntegralType[] = ['GAIN_KI', 'TIME_TI'];

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
}

export interface TuningForm {
  kp: number;
  ti: number;
  td: number;
}

export type FieldErrors = Record<string, string | undefined>;

export type { ControllerMode };
