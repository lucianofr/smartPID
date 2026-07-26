import { api } from '@/api/client';
import { endpoints } from '@/api/endpoints';
import type { AiStatus, CommandResponse, ControllerMode, ControllerResponse } from '@/api/types';

/**
 * Loop command + controller CRUD surface. The four writes phase 4 already
 * published (`setMode`, `setSetpoint`, `setOutput`, `applyTuning`) are reused
 * from `endpoints` rather than restated — one definition of each request body,
 * and one seam the dashboard tests already spy on.
 */

export type { CommandResponse };

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

export type AiAction = 'start' | 'stop' | 'pause';

export const setSetpoint = (controllerId: number, value: number) =>
  endpoints.setSetpoint(controllerId, value);

export const setMode = (controllerId: number, mode: ControllerMode) =>
  endpoints.setMode(controllerId, mode);

export const setOutput = (controllerId: number, value: number) =>
  endpoints.setOutput(controllerId, value);

export const applyTuning = (controllerId: number) => endpoints.applyTuning(controllerId);

export const setOptimization = (controllerId: number, enabled: boolean) =>
  api.post<CommandResponse>('/commands/optimization', { controller_id: controllerId, enabled });

export const writeTuning = (controllerId: number, kp: number, ti: number, td: number) =>
  api.post<CommandResponse>('/commands/tuning', { controller_id: controllerId, kp, ti, td });

/** 404 = no pending recommendation. An expected state, never retried. */
export const getTuningRecommendation = (controllerId: number) =>
  api.get<TuningRecommendation>(`/commands/tuning-recommendations/${controllerId}`);

export const getAiStatus = (controllerId: number): Promise<AiStatus> =>
  endpoints.aiStatus(controllerId);

export const sendAiAction = (controllerId: number, action: AiAction) =>
  api.post<Record<string, unknown>>(`/controllers/${controllerId}/ai/${action}`);

export const updateController = (controllerId: number, patch: Record<string, unknown>) =>
  api.put<ControllerResponse>(`/controllers/${controllerId}`, patch);

export const createController = (body: Record<string, unknown>) =>
  api.post<ControllerResponse>('/controllers', body);

export const deleteController = (controllerId: number) =>
  api.delete<Record<string, unknown>>(`/controllers/${controllerId}`);
