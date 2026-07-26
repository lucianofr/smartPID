import { api } from './client';
import type {
  AiStatus,
  AiTuningLogRow,
  AlarmConfigResponse,
  AlarmRow,
  AlarmThreshold,
  CommandResponse,
  ControllerMode,
  ControllerResponse,
  ExportJob,
  ExportRequest,
  HistoryResponse,
  MeResponse,
  OpcuaBrowseResponse,
  OpcuaSearchResponse,
  OpcuaStatus,
  ProjectListResponse,
  ProjectMeta,
  SimulatorStatus,
  StatsResponse,
  SystemStatusResponse,
  TokenResponse,
  UserCreateBody,
  UserRow,
  UserUpdateBody,
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

export interface HistoryParams {
  /** ISO-8601; optional on this route (history.py) unlike /alarms/history. */
  start?: string;
  end?: string;
  limit?: number;
}

export interface AiTuningHistoryParams {
  /** ISO-8601 — both bounds are REQUIRED by the route (alarms.py:62-63). */
  start: string;
  end: string;
  /** Narrow to one loop; omitted means every controller. */
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

  /**
   * Admin-only by backend design (phase-0 RBAC classification). A `user`
   * session is refused here on every realtime resync, which is normal — so the
   * global "Sem permissão" toast is suppressed. Callers still receive the 403.
   */
  simulatorStatus: () =>
    api.get<SimulatorStatus>('/simulator/status', { silentForbidden: true }),

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

  /** Telemetry replay for one loop — frames ascend by timestamp. */
  history: (controllerId: number, params: HistoryParams = {}) => {
    const q = new URLSearchParams();
    if (params.start !== undefined) q.set('start', params.start);
    if (params.end !== undefined) q.set('end', params.end);
    if (params.limit !== undefined) q.set('limit', String(params.limit));
    const query = q.toString();
    return api.get<HistoryResponse>(`/history/${controllerId}${query ? `?${query}` : ''}`);
  },

  /** Every loop that has a stats worker — the multitrend loop roster. */
  allStats: () => api.get<StatsResponse[]>('/controllers/stats'),

  loopStats: (controllerId: number) =>
    api.get<StatsResponse>(`/controllers/${controllerId}/stats`),

  /** 201 + a job; the file is produced asynchronously (poll `exportStatus`). */
  createExport: (request: ExportRequest) => api.post<ExportJob>('/export', request),

  exportStatus: (exportId: string) => api.get<ExportJob>(`/export/${exportId}`),

  /** Bearer travels in a header, so the download cannot be a plain <a href>. */
  downloadExport: (exportId: string) => api.download(`/export/${exportId}/download`),

  // ---- phase 10 · OPC-UA connection (everything below /status is admin-only) ----

  /** 422 when the endpoint does not start with `opc.tcp://` (routers/opcua.py). */
  saveOpcuaEndpoint: (endpoint: string) => api.put<OpcuaStatus>('/opcua/endpoint', { endpoint }),

  /** Body is optional; omitting it reconnects the stored endpoint. */
  opcuaConnect: (endpoint?: string) =>
    api.post<OpcuaStatus>('/opcua/connect', endpoint !== undefined ? { endpoint } : undefined),

  opcuaDisconnect: () => api.post<OpcuaStatus>('/opcua/disconnect'),

  /** `{node_id:path}` — node ids carry `;` and `=`, so they are percent-encoded. */
  opcuaBrowse: (nodeId: string) =>
    api.get<OpcuaBrowseResponse>(`/opcua/browse/${encodeURIComponent(nodeId)}`),

  /** `q` is REQUIRED, 1..200 chars — an empty query is a 422, never a fetch. */
  opcuaSearch: (query: string) =>
    api.get<OpcuaSearchResponse>(`/opcua/search?q=${encodeURIComponent(query)}`),

  // ---- phase 10 · portable `.spid` projects (admin-only) ----

  projectList: () => api.get<ProjectListResponse>('/project/list'),

  createProject: (name: string) => api.post<ProjectMeta>('/project/new', { name }),

  openProject: (name: string) => api.post<ProjectMeta>('/project/open', { name }),

  /**
   * Multipart upload. 413 when it exceeds `max_upload_bytes` (50 MB default),
   * 400 when the archive is not a valid `.spid` — both are user-facing states.
   */
  importProject: (file: File, name?: string) => {
    const form = new FormData();
    form.append('file', file);
    if (name !== undefined && name !== '') form.append('name', name);
    return api.upload<ProjectMeta>('/project/import', form);
  },

  /** The backend WAL-checkpoints before streaming — the client never duplicates that. */
  downloadProject: () => api.download('/project/download'),

  /** 204 on success; 409 when the target is the active project. */
  deleteProject: (name: string) => api.delete<void>(`/project/${encodeURIComponent(name)}`),

  // ---- phase 10 · user management (admin-only, require_admin on every route) ----

  users: () => api.get<UserRow[]>('/users'),

  /** 409 `Username already exists` — the backend catches the IntegrityError. */
  createUser: (body: UserCreateBody) => api.post<UserRow>('/users', body),

  /** 409 when demoting/deactivating the last active admin. */
  updateUser: (userId: number, body: UserUpdateBody) =>
    api.patch<UserRow>(`/users/${userId}`, body),

  /** Soft deactivation — returns the updated row, not 204. */
  deactivateUser: (userId: number) => api.delete<UserRow>(`/users/${userId}`),

  // ---- phase 9 · executive dashboard ----

  /** Backend health snapshot. Unauthenticated by design (routers/system.py). */
  systemStatus: () => api.get<SystemStatusResponse>('/system/status'),

  /** AI tuning log over a window — the only before/after evidence the backend keeps. */
  aiTuningHistory: (params: AiTuningHistoryParams) => {
    const q = new URLSearchParams({ start: params.start, end: params.end });
    if (params.controllerId !== undefined) q.set('controller_id', String(params.controllerId));
    return api.get<AiTuningLogRow[]>(`/alarms/ai-history?${q.toString()}`);
  },
};