import { apiGet, apiPost, apiPut } from '../../api/client';
import type { ControllerMode } from './types';

export interface CommandResponse {
  ok: boolean;
  controller_id: number | null;
  detail: string | null;
  enabled?: boolean | null;
}

export interface AiStatus {
  controller_id: number;
  engine: string;
  objective: string;
  speed: string;
  current_ki: number;
  last_gamma: number | null;
  enabled: boolean;
}

export interface TuningRecommendation {
  controller_id: number;
  current_kp: number;
  current_ti: number;
  current_td: number;
  recommended_kp: number;
  recommended_ti: number;
  recommended_td: number;
  reason: string;
  timestamp: number;
  status: string;
  source: string | null;
}

export const setSetpoint = (controller_id: number, value: number) =>
  apiPost<CommandResponse>('/commands/setpoint', { controller_id, value });

export const setMode = (controller_id: number, mode: ControllerMode) =>
  apiPost<CommandResponse>('/commands/mode', { controller_id, mode });

export const setOutput = (controller_id: number, value: number) =>
  apiPost<CommandResponse>('/commands/output', { controller_id, value });

export const setOptimization = (controller_id: number, enabled: boolean) =>
  apiPost<CommandResponse>('/commands/optimization', { controller_id, enabled });

export const writeTuning = (controller_id: number, kp: number, ti: number, td: number) =>
  apiPost<CommandResponse>('/commands/tuning', { controller_id, kp, ti, td });

export const getTuningRecommendation = (controller_id: number) =>
  apiGet<TuningRecommendation>(`/commands/tuning-recommendations/${controller_id}`);

export const applyTuning = (controller_id: number) =>
  apiPost<{ ok: boolean; detail?: string }>(`/commands/apply-tuning/${controller_id}`, {});

export const updateController = (controller_id: number, patch: Record<string, unknown>) =>
  apiPut(`/controllers/${controller_id}`, patch);
