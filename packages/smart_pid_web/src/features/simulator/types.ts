// Hand-typed DTOs mirroring the backend simulator Pydantic models
// (smart_pid_domain/dtos/simulator.py, models/process_preset.py, dtos/commands.py).
// String-literal unions are used for enums; field names/types copied verbatim.

export type ProcessPresetName = 'FLOW' | 'PRESSURE' | 'LEVEL' | 'TEMPERATURE' | 'CUSTOM';
export const PRESET_NAMES: ProcessPresetName[] = ['FLOW', 'PRESSURE', 'LEVEL', 'TEMPERATURE', 'CUSTOM'];

export type TwinMode = 'MAN' | 'AUTO';
export type DisturbanceType = 'step' | 'noise';

export interface SimulatorPresetRequest {
  controller_id: number;
  preset: ProcessPresetName;
}

export interface SimulatorParametersRequest {
  controller_id: number;
  gain: number;
  tau1: number;
  tau2?: number | null;
  dead_time: number;
}

export interface SimulatorDisturbanceRequest {
  controller_id: number;
  type: DisturbanceType;
  amplitude: number;
}

export interface AutoSPRequest {
  enabled: boolean;
  sp_min_pct: number;
  sp_max_pct: number;
}

export interface AutoDisturbanceRequest {
  enabled: boolean;
  max_amplitude_pct: number;
}

export interface SimulatorPIDModeRequest {
  controller_id: number;
  mode: TwinMode;
}

export interface SimulatorPIDSPRequest {
  controller_id: number;
  sp: number;
}

export interface ControllerSimStatus {
  preset: string;
  gain: number;
  tau1: number;
  tau2: number | null;
  dead_time: number;
  step_active: boolean;
  step_amplitude: number;
  noise_active: boolean;
  noise_amplitude: number;
  pid_enabled: boolean;
  pid_kp: number;
  pid_ti: number;
  pid_td: number;
  pid_mode: number; // 0=MAN, 1=AUTO
  pid_cv: number;
  auto_sp: AutoSPRequest | null;
  auto_disturbance: AutoDisturbanceRequest | null;
  pv: number;
  sp: number;
  co: number;
  error: number;
  process_input: number;
  process_output: number;
  disturbance_output: number;
}

export interface SimulatorStatusResponse {
  enabled: boolean;
  running: boolean;
  controllers: Record<number, ControllerSimStatus>;
}

export interface CommandResponse {
  ok: boolean;
  controller_id?: number | null;
  detail?: string | null;
  enabled?: boolean | null;
}
