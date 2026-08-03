import type { components } from '@/api/generated/openapi';

/**
 * Simulator DTOs, aliased straight off the generated OpenAPI schema — the twin
 * is an internal OPC-UA process model (port 4849, `SPID_SIMULATOR_ENABLED`),
 * and hand-copying its Pydantic shapes is how they silently drift.
 */

export type SimulatorStatusResponse = components['schemas']['SimulatorStatusResponse'];
export type ControllerSimStatus = components['schemas']['ControllerSimStatus'];
export type ProcessPresetName = components['schemas']['ProcessPresetName'];
export type SimulatorPresetRequest = components['schemas']['SimulatorPresetRequest'];
export type SimulatorParametersRequest = components['schemas']['SimulatorParametersRequest'];
export type SimulatorDisturbanceRequest = components['schemas']['SimulatorDisturbanceRequest'];
export type SimulatorPIDModeRequest = components['schemas']['SimulatorPIDModeRequest'];
export type SimulatorPIDSPRequest = components['schemas']['SimulatorPIDSPRequest'];
export type SimulatorPIDParamsRequest = components['schemas']['SimulatorPIDParamsRequest'];
export type AutoSPRequest = components['schemas']['AutoSPRequest'];
export type AutoDisturbanceRequest = components['schemas']['AutoDisturbanceRequest'];

/**
 * `POST /simulator/loops` body. Hand-written on purpose: loop lifecycle is a
 * newer route than the generated schema snapshot. `controller_id: null` asks
 * the server to allocate the next free loop id.
 */
export interface SimulatorLoopCreateRequest {
  controller_id: number | null;
  pv_min: number;
  pv_max: number;
}

/** PV range a freshly created simulator loop starts with. */
export const SIM_LOOP_PV_DEFAULTS = { pv_min: 0, pv_max: 100 } as const;

/** Selectable process models (models/process_preset.py). */
export const PRESET_NAMES = ['FLOW', 'PRESSURE', 'LEVEL', 'TEMPERATURE', 'CUSTOM'] as const;

export type TwinMode = SimulatorPIDModeRequest['mode'];
export type DisturbanceType = SimulatorDisturbanceRequest['type'];

/** `ControllerSimStatus.pid_mode` is an int on the wire: 0 = MAN, 1 = AUTO. */
export const PID_MODE_AUTO = 1;

/** Editable first/second-order-plus-dead-time process model. */
export interface Dynamics {
  gain: number;
  dead_time: number;
  tau1: number;
  tau2: number | null;
}

/** Backend defaults (AutoSPRequest / AutoDisturbanceRequest schema defaults). */
export const AUTO_SP_DEFAULTS = { sp_min_pct: 30, sp_max_pct: 70, period_s: 30 } as const;
export const AUTO_DISTURBANCE_DEFAULTS = { max_amplitude_pct: 10, period_s: 30 } as const;
