import type { ControllerResponse } from '@/api/types';
import type { FFSignal, RealtimeEnvelope, StatusData } from '@/lib/envelope';

/**
 * Wire-shaped fixtures. `ControllerResponse` has ~40 schema-defaulted fields,
 * so tests build from this base instead of restating the DTO each time.
 */
const BASE_CONTROLLER: ControllerResponse = {
  ai_config: {
    dead_time_l: 1,
    engine: 'NONE',
    limit_max: 100,
    limit_min: 0.1,
    objective: 'DISTURBANCE_REJECTION',
    rl_fallback_kd: 0.2,
    rl_fallback_kp: 0.6,
    rl_learning_rate: 0.0003,
    rl_train_interval: 32,
  },
  arw_hi_lim: 100,
  arw_lo_lim: 0,
  co: 0,
  control_opts: {
    direct_acting: false,
    no_out_limits_in_manual: false,
    obey_sp_limits_if_cas: false,
    sp_pv_track_in_lo_or_iman: false,
    sp_pv_track_in_man: false,
    sp_pv_track_in_rout: false,
    sp_track_retained_target: false,
    track_enable: false,
    track_in_manual: false,
    use_pv_for_bkcal_out: false,
  },
  description: '',
  execution_mode: 'SUPERVISORY',
  ff_enable: false,
  ff_gain: 1,
  id: 1,
  integral_type: 'TIME_TI',
  io_opts: {
    fault_state_to_value: false,
    increase_to_close: false,
    low_cutoff: false,
    sp_pv_track_in_lo_or_iman: false,
    sp_pv_track_in_man: false,
    target_to_man_if_fault: false,
  },
  low_cut: 0,
  max_tuning_change_pct: 10,
  mode: 'AUTO',
  mode_normal: 'AUTO',
  name: 'FIC-101',
  optimization_enabled: true,
  out_hi_lim: 100,
  out_lo_lim: 0,
  out_scale: { eu_max: 100, eu_min: 0, unit: '%' },
  permitted_modes: ['MAN', 'AUTO'],
  pid_params: { alpha: 0.125, deadband: 0, gain: 1, rate: 0, reset: 10 },
  pid_structure: 'ISA',
  process_speed: 'MEDIUM',
  pv: 0,
  pv_ftime: 0,
  pv_scale: { eu_max: 100, eu_min: 0, unit: '%' },
  scan_rate_s: 1,
  shed_opt: 'MAN',
  shed_time_s: 10,
  sp: 0,
  sp_ftime: 0,
  sp_hi_lim: 100,
  sp_lo_lim: 0,
  sp_rate_dn: 0,
  sp_rate_up: 0,
  tag_bindings: {
    mode_int_map: {},
    node_id_bkcal_in: '',
    node_id_bkcal_out: '',
    node_id_co: '',
    node_id_integral: '',
    node_id_kp: '',
    node_id_mode_actual: '',
    node_id_mode_target: '',
    node_id_pv: '',
    node_id_sp: '',
    node_id_td: '',
    node_id_ti: '',
  },
  tss_s: 60,
  tuning_write_mode: 'approval_required',
};

export function makeController(overrides: Partial<ControllerResponse> = {}): ControllerResponse {
  return { ...BASE_CONTROLLER, ...overrides };
}

export function ff(value: number, severity = 'GOOD'): FFSignal {
  return { value, severity, limit_bits: 'NONE', sub_status: 'NON_SPECIFIC' };
}

export function makeStatus(overrides: Partial<StatusData> = {}): StatusData {
  return {
    controller_id: 1,
    pv: ff(50),
    sp: ff(55),
    co: ff(42),
    bkcal_in: ff(0),
    bkcal_out: ff(0),
    mode: 'AUTO',
    kp: 1,
    ti: 10,
    td: 0,
    integral_val: 0,
    timestamp: '2026-07-26T00:00:00.000Z',
    ...overrides,
  };
}

export function statusEnvelope(
  loopId: number,
  seq: number,
  data: Partial<StatusData> = {},
): RealtimeEnvelope<StatusData> & { type: 'status' } {
  return {
    type: 'status',
    loop_id: loopId,
    seq,
    ts: seq,
    data: makeStatus({ controller_id: loopId, ...data }),
  };
}
