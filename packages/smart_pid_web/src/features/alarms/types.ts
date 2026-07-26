import type { components } from '@/api/generated/openapi';
import type { AlarmRow, AlarmRowStatus } from '@/api/types';

/**
 * Alarm domain vocabulary. Everything the backend already publishes a schema
 * for is DERIVED from the generated OpenAPI types — a backend enum change must
 * break the build here, not drift silently.
 */

/** `AlarmPriority` (smart_pid_domain/enums.py) — the four §6.4 severities. */
export type AlarmSeverity = components['schemas']['AlarmPriority'];

/** `AlarmType` — the six configurable limit kinds. */
export type AlarmType = components['schemas']['AlarmType'];

/** One configurable threshold row (`GET/PUT /controllers/{id}/alarm-config`). */
export type AlarmThreshold = components['schemas']['AlarmThreshold'];
export type AlarmConfigResponse = components['schemas']['AlarmConfigResponse'];
export type AlarmConfigUpdate = components['schemas']['AlarmConfigUpdate'];

/** Row-level ack/clear state (alarm_repo.py CASE) — see lib/alarmMachine.ts. */
export type AlarmStatus = AlarmRowStatus;

/** One row of `GET /alarms/active` or `GET /alarms/history`. */
export type ActiveAlarm = AlarmRow;

/** Limit kinds in operator order — LOLO at the bottom, HIHI at the top. */
export const ALARM_TYPES = ['HIHI', 'HI', 'LO', 'LOLO', 'DV_HI', 'DV_LO'] as const;

/** The four analog limits, ordered high→low; deviation limits are unordered. */
export const ORDERED_LIMIT_TYPES = ['HIHI', 'HI', 'LO', 'LOLO'] as const;
