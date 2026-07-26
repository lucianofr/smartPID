import { api } from './client';
import type {
  AiStatus,
  AlarmRow,
  ControllerResponse,
  MeResponse,
  OpcuaStatus,
  SimulatorStatus,
  TokenResponse,
} from './types';

export interface AlarmHistoryParams {
  /** ISO-8601 — backend parses with datetime.fromisoformat (alarms.py:46). */
  start: string;
  /** ISO-8601 — REQUIRED by the backend alongside start (alarms.py:38-39). */
  end: string;
  /** Backend default is 100 (alarms.py:41) — resync passes an explicit high cap. */
  limit?: number;
  offset?: number;
}

export const endpoints = {
  login: (username: string, password: string) =>
    api.post<TokenResponse>('/auth/login', { username, password }),

  me: () => api.get<MeResponse>('/auth/me'),

  controllers: () => api.get<ControllerResponse[]>('/controllers'),

  activeAlarms: () => api.get<AlarmRow[]>('/alarms/active'),

  alarmHistory: (params: AlarmHistoryParams) => {
    const q = new URLSearchParams({ start: params.start, end: params.end });
    if (params.limit !== undefined) q.set('limit', String(params.limit));
    if (params.offset !== undefined) q.set('offset', String(params.offset));
    return api.get<AlarmRow[]>(`/alarms/history?${q.toString()}`);
  },

  aiStatus: (controllerId: number) =>
    api.get<AiStatus>(`/controllers/${controllerId}/ai/status`),

  opcuaStatus: () => api.get<OpcuaStatus>('/opcua/status'),

  simulatorStatus: () => api.get<SimulatorStatus>('/simulator/status'),
};