import { api } from './client';
import type {
  AccessLogRow,
  ActiveSessionRow,
  AiHistoryResponse,
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
  LogLevelName,
  LogLevelsResponse,
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
import type { ContractThemeId } from '../theme/contract';

export interface AlarmHistoryParams {
  /** ISO-8601 — backend parses with datetime.fromisoformat
   *  (alarms.py get_alarm_history). */
  start: string;
  /** ISO-8601 — REQUIRED by the backend alongside start
   *  (alarms.py get_alarm_history). */
  end: string;
  /** Backend default is 100 (alarms.py get_alarm_history) — resync passes an
   *  explicit high cap. */
  limit?: number;
  offset?: number;
  /** Narrow to one loop (alarms.py get_alarm_history) — omitted means every
   *  controller. */
  controllerId?: number;
}

export interface HistoryParams {
  /** ISO-8601; optional on this route (history.py) unlike /alarms/history. */
  start?: string;
  end?: string;
  limit?: number;
}

export interface AiTuningHistoryParams {
  /** ISO-8601 — both bounds are REQUIRED by the route
   *  (alarms.py get_ai_log_history). */
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

  /**
   * The loop's own tuning log. Seeds the faceplate optimizer log so a freshly
   * opened loop shows the engine's last decisions instead of `Sem eventos de
   * IA.` until the next cycle — ACTION.AI fires once per AI period (minutes),
   * so a live-only log is blank for most of the time an operator looks at it.
   */
  aiHistory: (controllerId: number) =>
    api.get<AiHistoryResponse>(`/controllers/${controllerId}/ai/history`),

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

  /**
   * The in-memory 1-hour ring behind every trend chart (GET /trend/{id}). Same
   * `HistoryResponse` shape as `history`, but backed by the live ring instead
   * of the SQLite historian: a chart seeds its window from here on mount and
   * then appends realtime frames, so a reload no longer blanks the trace for
   * up to an hour while the window refills from scratch.
   */
  trend: (controllerId: number, seconds = 3600) =>
    api.get<HistoryResponse>(`/trend/${controllerId}?seconds=${seconds}`),

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

  /**
   * The active project — the only route under `/project` that is not
   * admin-only, so the header may name the plant for every session.
   */
  projectCurrent: () => api.get<ProjectMeta>('/project/current'),

  createProject: (name: string) => api.post<ProjectMeta>('/project/new', { name }),

  openProject: (name: string) => api.post<ProjectMeta>('/project/open', { name }),

  /**
   * Multipart upload, streamed to disk server-side — the ceiling is
   * `max_upload_bytes` (2 GiB default, sized to clear what `downloadProject`
   * emits for a plant with history). 413 above it, 507 when the server volume
   * is too full, 400 when the archive is not a valid `.spid`.
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

  /**
   * Per-user theme preference (204, no body). Best-effort from the caller's
   * side: the in-session theme never waits on, nor reverts with, this write.
   */
  setUserTheme: (theme: ContractThemeId) => api.put<void>('/users/me/theme', { theme }),

  // ---- live sessions + sign-in history (routers/auth.py, admin-only) ----

  /** Who is connected right now, and from which source IP. */
  activeSessions: () => api.get<ActiveSessionRow[]>('/auth/sessions'),

  /** Sign-in / sign-out history of every account, newest first (cap 500). */
  accessLog: (limit = 50) => api.get<AccessLogRow[]>(`/auth/access-log?limit=${limit}`),

  /**
   * Ends the session LISTING, not the token: the JWT stays valid until it
   * expires, exactly as before this route existed. Fire-and-forget — the
   * client-side sign-out must never wait on, nor be blocked by, the server.
   */
  logout: () => api.post<void>('/auth/logout'),

  // ---- admin-controlled daemon log levels (routers/system.py, require_admin) ----

  /** `levels` is what the daemon currently emits; `available` is every selectable name. */
  getLogLevels: () => api.get<LogLevelsResponse>('/system/log-levels'),

  /** 204 on success; an empty list silences everything the daemon itself allows silencing. */
  setLogLevels: (levels: LogLevelName[]) => api.put<void>('/system/log-levels', { levels }),

  // ---- phase 9 · executive dashboard ----

  /** Backend health snapshot. Unauthenticated by design (routers/system.py). */
  systemStatus: () => api.get<SystemStatusResponse>('/system/status'),

  /** AI tuning log over a window — the only before/after evidence the backend keeps. */
  aiTuningHistory: (params: AiTuningHistoryParams) => {
    const q = new URLSearchParams({ start: params.start, end: params.end });
    if (params.controllerId !== undefined) q.set('controller_id', String(params.controllerId));
    return api.get<AiTuningLogRow[]>(`/alarms/ai-history?${q.toString()}`);
  },

  // ---- alarm & event history · system event log (Log_System_Events) ----

  /**
   * Companion of `alarmHistory`: alarms and system/optimizer events live in
   * two separate tables, so the history panel merges both over one window.
   */
  systemEvents: (params: SystemEventParams) => {
    const q = new URLSearchParams({ start: params.start, end: params.end });
    if (params.source !== undefined) q.set('source', params.source);
    if (params.severity !== undefined) q.set('severity', params.severity);
    if (params.limit !== undefined) q.set('limit', String(params.limit));
    if (params.offset !== undefined) q.set('offset', String(params.offset));
    return api.get<SystemEventRow[]>(`/system-events?${q.toString()}`);
  },
};

/** One row of `GET /system-events` (routers/system_events.py). */
export interface SystemEventRow {
  id: number;
  timestamp: string;
  /** Emitter tag, e.g. `AI` for optimizer suggestions. */
  source: string;
  /** Free-form wire severity — normalise with `toSeverity` before rendering. */
  severity: string;
  message: string;
}

export interface SystemEventParams {
  /** ISO-8601 — both bounds are REQUIRED, same as `/alarms/history`. */
  start: string;
  end: string;
  source?: string;
  severity?: string;
  limit?: number;
  offset?: number;
}