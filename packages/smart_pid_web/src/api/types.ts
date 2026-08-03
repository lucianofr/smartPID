import type { components } from './generated/openapi';

/** Lowercase roles — spec §9, phase-0 enum migration. */
export type Role = 'admin' | 'user';

/**
 * GET /auth/me response (phase 0: response_model=UserClaims, require_user).
 *
 * `theme` is the per-USER palette (PUT /users/me/theme) — localStorage alone is
 * per-browser, so it cannot follow an operator to another station. Declared
 * here as optional so the app compiles against an OpenAPI snapshot taken
 * before the field landed; the server sends `string | null`.
 */
export type MeResponse = components['schemas']['UserClaims'] & {
  theme?: string | null;
};

/** POST /auth/login response — unchanged by phase 0: {access_token, token_type}. */
export type TokenResponse = components['schemas']['TokenResponse'];

export type ControllerResponse = components['schemas']['ControllerResponse'];
export type AiStatus = components['schemas']['AIStatusResponse'];
/** GET /controllers/{id}/ai/history — the loop's own tuning log, newest 50. */
export type AiHistoryResponse = components['schemas']['AIHistoryResponse'];
export type AiTuningLogEntry = components['schemas']['AITuningLogEntry'];
export type AiConfigDto = components['schemas']['AIConfigDTO'];
export type ScaleConfigDto = components['schemas']['ScaleConfigDTO'];
export type TagBindingsDto = components['schemas']['TagBindingsDTO'];
/** commands.py CommandResponse — every write under `/commands/*` returns this. */
export type CommandResponse = components['schemas']['CommandResponse'];
export type OpcuaStatus = components['schemas']['OPCUAStatusResponse'];
export type SimulatorStatus = components['schemas']['SimulatorStatusResponse'];

/** PID block operating modes (ModeCommand payload enum). */
export type ControllerMode = components['schemas']['ControllerMode'];

/** GET /history/{controller_id} — telemetry replay for the trend workspace. */
export type HistoryResponse = components['schemas']['HistoryResponse'];
export type TelemetryFrame = components['schemas']['TelemetryFrameDTO'];

/** GET /controllers/stats and /controllers/{id}/stats — loop performance metrics. */
export type StatsResponse = components['schemas']['StatsResponse'];

/** POST /export, GET /export/{id} — one job per request. */
export type ExportJob = components['schemas']['ExportJob'];
export type ExportFormat = ExportJob['format'];
export type ExportStatus = ExportJob['status'];

/**
 * POST /export body. Permanently SINGULAR `controller_id` (TD-008: there is no
 * bulk export and no `GET /export/list`). `format` is server-defaulted to csv,
 * so it stays optional here even though the codegen marks defaults required.
 */
export type ExportRequest = Omit<components['schemas']['ExportRequest'], 'format'> & {
  format?: ExportFormat;
};

/** Alarm vocabulary + threshold CRUD schemas (routers/controllers.py). */
export type AlarmPriority = components['schemas']['AlarmPriority'];
export type AlarmTypeName = components['schemas']['AlarmType'];
export type AlarmThreshold = components['schemas']['AlarmThreshold'];
export type AlarmConfigResponse = components['schemas']['AlarmConfigResponse'];
export type AlarmConfigUpdate = components['schemas']['AlarmConfigUpdate'];

/** Row status CASE — alarm_repo.py:129-132 / 209-212. */
export type AlarmRowStatus = 'UNACKNOWLEDGED' | 'ACKNOWLEDGED' | 'CLEARED_UNACK';

/**
 * GET /alarms/active and GET /alarms/history return bare `list[dict]`
 * (routers/alarms.py:30,43) — the OpenAPI dump carries no schema for them.
 * Hand-mirrored from the SELECT in alarm_repo.py:114-135 (the LEFT JOIN makes
 * controller_name nullable).
 */
export interface AlarmRow {
  id: number;
  controller_id: number;
  controller_name: string | null;
  alarm_type: string;
  priority: string;
  value: number;
  limit: number;
  timestamp: string;
  cleared_at: string | null;
  acknowledged: 0 | 1;
  ack_by_user: string | null;
  ack_at: string | null;
  status: AlarmRowStatus;
}

/** OPC-UA address-space vocabulary (routers/opcua.py — browse/search are admin-only). */
export type ConnectionState = components['schemas']['ConnectionState'];
export type OpcuaNode = components['schemas']['OPCUANodeInfo'];
export type OpcuaBrowseResponse = components['schemas']['OPCUABrowseResponse'];
export type OpcuaSearchResponse = components['schemas']['OPCUASearchResponse'];

/** Portable `.spid` projects (routers/project.py — everything but /current is admin-only). */
export type ProjectItem = components['schemas']['ProjectListItem'];
export type ProjectListResponse = components['schemas']['ProjectListResponse'];
export type ProjectMeta = components['schemas']['ProjectResponse'];

/** Admin-only user management (routers/users.py). */
export type UserRow = components['schemas']['UserResponse'];
export type UserCreateBody = components['schemas']['UserCreate'];
export type UserUpdateBody = components['schemas']['UserUpdate'];

/** GET /system/status — health check, no auth (routers/system.py). */
export type SystemStatusResponse = components['schemas']['SystemStatusResponse'];

/**
 * GET /alarms/ai-history returns a bare `list[dict]` (routers/alarms.py:56), so
 * the OpenAPI dump carries no schema for it. Hand-mirrored from the SELECT in
 * ai_repo.py:142-150 — note it exposes `controller_name` and NOT the `approved`
 * flag that the per-loop `AITuningLogEntry` schema carries.
 */
export interface AiTuningLogRow {
  id: number;
  controller_id: number;
  controller_name: string | null;
  timestamp: string;
  engine: string;
  ki_before: number | null;
  ki_after: number | null;
  objective: string | null;
  /** Objective metric recorded at that tuning. An error index: lower is better. */
  metric: number | null;
}