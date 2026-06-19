export type ControllerMode =
  | 'OOS' | 'IMAN' | 'LO' | 'MAN' | 'AUTO' | 'CAS' | 'RCAS' | 'ROUT' | 'BYPASS';
export const CONTROLLER_MODES: ControllerMode[] =
  ['OOS', 'IMAN', 'LO', 'MAN', 'AUTO', 'CAS', 'RCAS', 'ROUT', 'BYPASS'];
export type AiEngine = 'NONE' | 'FUZZY' | 'RL';
export type PidStructure = 'ISA' | 'PARALLEL' | 'SERIES';

export interface PidParamsForm { gain: number; reset: number; rate: number; alpha: number; deadband: number; }
export interface LimitsForm {
  out_hi_lim: number; out_lo_lim: number; arw_hi_lim: number; arw_lo_lim: number;
  pv_ftime: number; sp_ftime: number; sp_rate_up: number; sp_rate_dn: number;
}
export interface AiConfigForm { engine: AiEngine; objective: string; }

export interface FieldErrors { [field: string]: string | undefined; }
