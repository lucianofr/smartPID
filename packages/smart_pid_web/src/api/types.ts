import type { components } from './generated/openapi';

/** Lowercase roles — spec §9, phase-0 enum migration. */
export type Role = 'admin' | 'user';

/** GET /auth/me response (phase 0: response_model=UserClaims, require_user). */
export type MeResponse = components['schemas']['UserClaims'];

/** POST /auth/login response — unchanged by phase 0: {access_token, token_type}. */
export type TokenResponse = components['schemas']['TokenResponse'];

export type ControllerResponse = components['schemas']['ControllerResponse'];
export type AiStatus = components['schemas']['AIStatusResponse'];
export type AiConfigDto = components['schemas']['AIConfigDTO'];
export type ScaleConfigDto = components['schemas']['ScaleConfigDTO'];
export type TagBindingsDto = components['schemas']['TagBindingsDTO'];
/** commands.py CommandResponse — every write under `/commands/*` returns this. */
export type CommandResponse = components['schemas']['CommandResponse'];
export type OpcuaStatus = components['schemas']['OPCUAStatusResponse'];
export type SimulatorStatus = components['schemas']['SimulatorStatusResponse'];

/** PID block operating modes (ModeCommand payload enum). */
export type ControllerMode = components['schemas']['ControllerMode'];

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