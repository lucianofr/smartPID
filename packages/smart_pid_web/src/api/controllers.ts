import type {
  AiConfigForm,
  LimitsForm,
  PidParamsForm,
  PidStructure,
} from '../features/loop-config/types';

// Subset of the backend ControllerResponse consumed by the dashboard. The list query
// (GET /api/controllers) already returns the full response, so the card display fields,
// the per-loop controls, and the LoopConfigDialog `initial` are all derived from one fetch.
export interface ControllerResponse {
  id: number;
  name: string;
  description: string;
  pv_decimals: number;
  pv_unit: string;
  pid_params: PidParamsForm;
  pid_structure: PidStructure;
  ai_config: AiConfigForm;
  optimization_enabled: boolean;
  out_hi_lim: number;
  out_lo_lim: number;
  arw_hi_lim: number;
  arw_lo_lim: number;
  pv_ftime: number;
  sp_ftime: number;
  sp_rate_up: number;
  sp_rate_dn: number;
}

export function toLimitsForm(c: ControllerResponse): LimitsForm {
  return {
    out_hi_lim: c.out_hi_lim,
    out_lo_lim: c.out_lo_lim,
    arw_hi_lim: c.arw_hi_lim,
    arw_lo_lim: c.arw_lo_lim,
    pv_ftime: c.pv_ftime,
    sp_ftime: c.sp_ftime,
    sp_rate_up: c.sp_rate_up,
    sp_rate_dn: c.sp_rate_dn,
  };
}
