import type {
  AlarmConfigResponse,
  AlarmConfigUpdate,
  AlarmPriority,
  AlarmRow,
  AlarmRowStatus,
  AlarmThreshold,
  AlarmTypeName,
} from '@/api/types';

/**
 * Alarm domain vocabulary. Every name here is an alias of the generated
 * OpenAPI type re-exported by `api/types` — one boundary to the backend
 * schema, so an enum change breaks the build instead of drifting silently.
 */

/** `AlarmPriority` (smart_pid_domain/enums.py) — the four §6.4 severities. */
export type AlarmSeverity = AlarmPriority;

/** `AlarmType` — the six configurable limit kinds. */
export type AlarmType = AlarmTypeName;

/** Row-level ack/clear state (alarm_repo.py CASE) — see lib/alarmMachine.ts. */
export type AlarmStatus = AlarmRowStatus;

/** One row of `GET /alarms/active` or `GET /alarms/history`. */
export type ActiveAlarm = AlarmRow;

export type { AlarmConfigResponse, AlarmConfigUpdate, AlarmThreshold };

/** Limit kinds in operator order — HIHI at the top, deviations last. */
export const ALARM_TYPES = ['HIHI', 'HI', 'LO', 'LOLO', 'DV_HI', 'DV_LO'] as const;

/**
 * The four analog limits, ordered high→low. Deviation limits (DV_HI/DV_LO) are
 * relative to setpoint and carry no cross-limit ordering rule.
 */
export const ORDERED_LIMIT_TYPES = ['HIHI', 'HI', 'LO', 'LOLO'] as const;
