export type RealtimeType = 'status' | 'action' | 'alarm' | 'ai' | 'stats' | 'system';

export interface RealtimeEnvelope<T = unknown> {
  type: RealtimeType;
  loop_id: number | null; // null for global events (EVENT.SYSTEM)
  seq: number; // per-connection sequence, for gap detection
  ts: number; // epoch seconds, server time (stamped by the WS bridge)
  data: T;
}

// Fieldbus signal: pv/sp/co/bkcal_* arrive as nested dicts on the wire
// (monitor_worker.py / pid_worker.py). The numeric reading is at `.value`.
export interface FFSignal {
  value: number;
  severity: string;
  limit_bits: string;
  sub_status: string;
}

// Live dashboard frame = STATUS.{id} (pid_worker.py:457 / monitor_worker.py:84).
// Wire payload is a msgpack dict; `timestamp` is an ISO-8601 STRING at the publish site.
export interface StatusData {
  pv: FFSignal;
  sp: FFSignal;
  co: FFSignal;
  bkcal_in: FFSignal;
  bkcal_out: FFSignal;
  mode: string; // ControllerMode value
  kp: number;
  ti: number;
  td: number;
  integral_val: number;
  timestamp: string; // ISO 8601 (publish-site format) — NOT epoch
}
// Derived client-side (NOT on the wire): error = sp.value - pv.value. OPC state via REST GET /opcua/status.
export interface ActionData { cv: number; delta: number; } // ACTION.CTRL.{id}
export interface AlarmData { alarm_id: string; severity: string; state: string; } // EVENT.ALARM.*
export interface AiData { gamma: number; ki: number; strategy: string; } // ACTION.AI.{id}
export interface StatsData {
  iae: number; itae: number; ise: number; mse: number;
  sigma: number; tv: number; var_range: number; var_sp: number;
} // STATS.{id}
