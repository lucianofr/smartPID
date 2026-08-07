/**
 * WS envelope — pure module, no React, no DOM (spec §7).
 *
 * Mirrors the backend bridge field-for-field:
 *   realtime.py:109    envelope shape {type, loop_id, seq, ts, data}
 *   realtime.py:82-89  topic → type taxonomy (has_loop_id per prefix)
 *   realtime.py:154    seq: monotonic per-bridge counter (shared by all sockets)
 *   realtime.py:156    ts: server time.time() → epoch SECONDS
 */

export type RealtimeType = 'status' | 'action' | 'ai' | 'alarm' | 'system' | 'stats';

export const REALTIME_TYPES: readonly RealtimeType[] = [
  'status',
  'action',
  'ai',
  'alarm',
  'system',
  'stats',
];

export interface RealtimeEnvelope<T = unknown> {
  type: RealtimeType;
  /** Parsed from the numeric topic suffix; null for EVENT.SYSTEM (realtime.py:99). */
  loop_id: number | null;
  /** Per-bridge monotonic counter (realtime.py:154); restarts when the daemon restarts. */
  seq: number;
  /** Epoch seconds, server-stamped (realtime.py:156). */
  ts: number;
  data: T;
}

/** Fieldbus signal dict — pid_worker.py:88-95 (_serialize_ff_signal). */
export interface FFSignal {
  value: number;
  severity: string;
  limit_bits: string;
  sub_status: string;
}

/**
 * STATUS.{id} — two producers, one shape plus two monitor-only fields:
 *   execute: pid_worker.py:438-455 (timestamp ISO-8601 string; kp/ti/td always numbers)
 *   monitor: monitor_worker.py:109-138 (timestamp may be float epoch seconds via
 *            time.time() fallback; adds error + saturated; kp/ti/td via .get() → null)
 */
export interface StatusData {
  controller_id: number;
  pv: FFSignal;
  sp: FFSignal;
  co: FFSignal;
  bkcal_in: FFSignal;
  bkcal_out: FFSignal;
  mode: string;
  kp: number | null;
  ti: number | null;
  td: number | null;
  integral_val: number;
  timestamp: string | number;
  /** monitor mode only: pv - sp (monitor_worker.py:116,132). */
  error?: number;
  /** monitor mode only: CO limit_bits HIGH_LIMITED/LOW_LIMITED (monitor_worker.py:118-121,133). */
  saturated?: boolean;
}

/** ACTION.CTRL.{id} — pid_worker.py:421-430. */
export interface ActionData {
  controller_id: number;
  co: FFSignal;
  bkcal_out: FFSignal;
  integral_val: number;
  delta_cv: number;
  timestamp: string;
}

/** ACTION.AI.{id} — ai_worker.py:295-305. */
export interface AiData {
  controller_id: number;
  gamma: number;
  new_ki: number;
  engine: string;
  objective: string;
  integral_type: string;
  execution_mode: string;
  reasoning: string;
  timestamp: string;
}

/** Wire transition values — alarm_engine.py:207,240. */
export type AlarmTransition = 'TRIGGERED' | 'CLEARED';

/** EVENT.ALARM.{id} — alarm_worker.py:169-179. Carries NO row id: alarms are keyed
 *  client-side by (controller_id, alarm_type); REST remains the source of row state. */
export interface AlarmEventData {
  controller_id: number;
  controller_name: string;
  controller_description: string;
  alarm_type: string;
  priority: string;
  transition: AlarmTransition;
  value: number;
  limit: number;
  timestamp: string;
}

/** EVENT.SYSTEM — system_event_worker.py:31-39. */
export interface SystemEventData {
  source: string;
  severity: string;
  message: string;
  timestamp: string;
}

/** STATS.{id} — stats_worker.py:106-138 (get_current_stats). The wire payload
 *  has NO controller_id (loop identity travels in envelope.loop_id); the REST
 *  StatsResponse does. */
export interface StatsData {
  iae: number;
  itae: number;
  ise: number;
  mse: number;
  std_dev: number;
  total_variation: number;
  variability_sp: number;
  variability_range: number;
  mean_abs_error: number;
  pk_pk_error: number;
  reversals: number;
  zero_crossings: number;
  recent_pk_pk_error: number;
  recent_reversals: number;
  tv_per_sample: number;
  osc: number;
  sample_count: number;
  /** Samples the oscillation metrics were allowed to see (non-settling).
   *  0 means "unmeasured", not "steady": pk-pk, reversals and zero-crossings
   *  are structural zeros when the settling mask covers the whole window. */
  osc_sample_count: number;
  /** Peak-to-peak setpoint travel over the window, engineering units — the
   *  scale the oscillation amplitude has to be judged against. */
  sp_pk_pk: number;
  /** Worst SP-step overshoot in the window, as a fraction of the step. */
  overshoot: number;
}

export type AnyEnvelope =
  | (RealtimeEnvelope<StatusData> & { type: 'status' })
  | (RealtimeEnvelope<ActionData> & { type: 'action' })
  | (RealtimeEnvelope<AiData> & { type: 'ai' })
  | (RealtimeEnvelope<AlarmEventData> & { type: 'alarm' })
  | (RealtimeEnvelope<SystemEventData> & { type: 'system' })
  | (RealtimeEnvelope<StatsData> & { type: 'stats' });

/** First server frame after a successful handshake (realtime.py:225). Not an envelope. */
export function isAuthOk(v: unknown): boolean {
  return typeof v === 'object' && v !== null && (v as { type?: unknown }).type === 'auth_ok';
}

/** Structural guard for the envelope shell. Payloads are typed, not runtime-checked:
 *  the producers above are the contract, and unknown extra keys must pass through. */
export function validateEnvelope(v: unknown): v is AnyEnvelope {
  if (typeof v !== 'object' || v === null) return false;
  const e = v as Record<string, unknown>;
  return (
    typeof e.type === 'string' &&
    (REALTIME_TYPES as readonly string[]).includes(e.type) &&
    (e.loop_id === null || typeof e.loop_id === 'number') &&
    typeof e.seq === 'number' &&
    typeof e.ts === 'number' &&
    'data' in e
  );
}

export function parseEnvelope(raw: string): AnyEnvelope | null {
  let v: unknown;
  try {
    v = JSON.parse(raw);
  } catch {
    return null;
  }
  return validateEnvelope(v) ? v : null;
}

/**
 * StatusData.timestamp normaliser: ISO-8601 string (execute mode) or float epoch
 * seconds (monitor mode) → epoch seconds; null when unparseable. Callers decide
 * the fallback (the window buffer rejects non-monotonic time anyway).
 */
export function statusTimestampToEpoch(ts: string | number): number | null {
  if (typeof ts === 'number') return Number.isFinite(ts) ? ts : null;
  const ms = Date.parse(ts);
  return Number.isNaN(ms) ? null : ms / 1000;
}

export interface SeqObservation {
  gap: boolean;
  expected: number | null;
  received: number;
}

export interface SeqTracker {
  /** Feed every validated envelope. gap=true ⇒ messages were lost (jump OR daemon-restart regression). */
  observe(env: Pick<RealtimeEnvelope, 'type' | 'seq' | 'ts'>): SeqObservation;
  /** Server ts of the last envelope seen per topic class — feeds the §7 resync
   *  "alarm history since last_seen_ts" window. */
  lastSeenTs(type: RealtimeType): number | null;
  /** Call on every (re)connect: the seq baseline is meaningless across
   *  connections (frames were missed), but last_seen_ts survives — the resync
   *  window must span the disconnect. */
  reset(): void;
}

export function createSeqTracker(): SeqTracker {
  let lastSeq: number | null = null;
  const lastTs = new Map<RealtimeType, number>();
  return {
    observe(env) {
      const expected = lastSeq === null ? null : lastSeq + 1;
      const gap = lastSeq !== null && env.seq !== lastSeq + 1;
      lastSeq = env.seq;
      lastTs.set(env.type, env.ts);
      return { gap, expected, received: env.seq };
    },
    lastSeenTs(type) {
      return lastTs.get(type) ?? null;
    },
    reset() {
      lastSeq = null;
    },
  };
}