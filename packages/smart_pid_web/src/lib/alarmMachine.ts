/**
 * Four-state alarm ack/clear machine — pure module (spec §7).
 *
 * Wire events: EVENT.ALARM.{id} carries transition TRIGGERED | CLEARED
 * (alarm_worker.py:175, alarm_engine.py:207,240). ACK is a client action
 * (POST /alarms/{id}/ack). Row-state derivation mirrors the backend CASE in
 * alarm_repo.py:129-132; cleared∧acked rows leave the active set entirely.
 */

export type AlarmPointState =
  | 'NORMAL'
  | 'UNACKNOWLEDGED'
  | 'ACKNOWLEDGED'
  | 'CLEARED_UNACK';

export type AlarmMachineEvent = { kind: 'TRIGGERED' } | { kind: 'CLEARED' } | { kind: 'ACK' };

const TABLE: Record<AlarmPointState, Record<AlarmMachineEvent['kind'], AlarmPointState>> = {
  NORMAL: { TRIGGERED: 'UNACKNOWLEDGED', CLEARED: 'NORMAL', ACK: 'NORMAL' },
  UNACKNOWLEDGED: { TRIGGERED: 'UNACKNOWLEDGED', CLEARED: 'CLEARED_UNACK', ACK: 'ACKNOWLEDGED' },
  // A TRIGGERED on an acked-active point implies a missed CLEARED (gap healing):
  // a new occurrence always demands a new acknowledgement.
  ACKNOWLEDGED: { TRIGGERED: 'UNACKNOWLEDGED', CLEARED: 'NORMAL', ACK: 'ACKNOWLEDGED' },
  // A re-trigger while cleared-unacked is a NEW instance; it stays unacked.
  CLEARED_UNACK: { TRIGGERED: 'UNACKNOWLEDGED', CLEARED: 'CLEARED_UNACK', ACK: 'NORMAL' },
};

export function transition(state: AlarmPointState, event: AlarmMachineEvent): AlarmPointState {
  return TABLE[state][event.kind];
}

/** Derive machine state from a REST row (GET /alarms/active|history). */
export function fromActiveRow(row: {
  acknowledged: 0 | 1;
  cleared_at: string | null;
}): AlarmPointState {
  if (row.acknowledged === 1) return row.cleared_at !== null ? 'NORMAL' : 'ACKNOWLEDGED';
  return row.cleared_at !== null ? 'CLEARED_UNACK' : 'UNACKNOWLEDGED';
}

/** Unacked drives the non-color channel (weight + icon + blink, spec §6.4). */
export function isUnacked(state: AlarmPointState): boolean {
  return state === 'UNACKNOWLEDGED' || state === 'CLEARED_UNACK';
}

/** Active = the condition is still present. */
export function isActive(state: AlarmPointState): boolean {
  return state === 'UNACKNOWLEDGED' || state === 'ACKNOWLEDGED';
}