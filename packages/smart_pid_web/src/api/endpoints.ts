import { api } from './client';
import type {
  AiStatus,
  AlarmConfigResponse,
  AlarmRow,
  AlarmThreshold,
  CommandResponse,
  ControllerMode,
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
  /** Narrow to one loop (alarms.py:40) — omitted means every controller. */
  controllerId?: number;
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
    if (params.controllerId !== undefined) q.set('controller_id', String(params.controllerId));
    return api.get<AlarmRow[]>(`/alarms/history?${q.toString()}`);
  },

  /** Single-row acknowledgement — the row stays active, ack ≠ clear (§7). */
  ackAlarm: (alarmId: number) => api.post<Record<string, unknown>>(`/alarms/${alarmId}/ack`),

  alarmConfig: (controllerId: number) =>
    api.get<AlarmConfigResponse>(`/controllers/${controllerId}/alarm-config`),

  /** PUT REPLACES the whole threshold array — always send every row. */
  updateAlarmConfig: (controllerId: number, thresholds: readonly AlarmThreshold[]) =>
    api.put<AlarmConfigResponse>(`/controllers/${controllerId}/alarm-config`, { thresholds }),

  aiStatus: (controllerId: number) =>
    api.get<AiStatus>(`/controllers/${controllerId}/ai/status`),

  opcuaStatus: () => api.get<OpcuaStatus>('/opcua/status'),

  simulatorStatus: () => api.get<SimulatorStatus>('/simulator/status'),

  /** Bulk acknowledgement behind the footer's `ACK ALL` (§6.9). */
  ackAllAlarms: () => api.post<Record<string, unknown>>('/alarms/ack-all'),

  setMode: (controllerId: number, mode: ControllerMode) =>
    api.post<CommandResponse>('/commands/mode', { controller_id: controllerId, mode }),

  setSetpoint: (controllerId: number, value: number) =>
    api.post<CommandResponse>('/commands/setpoint', { controller_id: controllerId, value }),

  setOutput: (controllerId: number, value: number) =>
    api.post<CommandResponse>('/commands/output', { controller_id: controllerId, value }),

  applyTuning: (controllerId: number) =>
    api.post<CommandResponse>(`/commands/apply-tuning/${controllerId}`),
};