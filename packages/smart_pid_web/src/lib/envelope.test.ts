import { describe, expect, it } from 'vitest';
import {
  createSeqTracker,
  isAuthOk,
  parseEnvelope,
  statusTimestampToEpoch,
  validateEnvelope,
} from './envelope';

const statusEnvelope = {
  type: 'status',
  loop_id: 12,
  seq: 7,
  ts: 1718743200.5,
  data: { pv: { value: 150.2 } },
};

describe('validateEnvelope', () => {
  it('accepts a well-formed status envelope', () => {
    expect(validateEnvelope(statusEnvelope)).toBe(true);
  });

  it('accepts loop_id null (EVENT.SYSTEM has no loop)', () => {
    expect(
      validateEnvelope({ type: 'system', loop_id: null, seq: 1, ts: 0, data: {} }),
    ).toBe(true);
  });

  it('rejects the auth_ok handshake frame (not an envelope)', () => {
    expect(validateEnvelope({ type: 'auth_ok' })).toBe(false);
  });

  it('rejects unknown types', () => {
    expect(
      validateEnvelope({ type: 'telemetry', loop_id: 1, seq: 1, ts: 0, data: {} }),
    ).toBe(false);
  });

  it('rejects missing seq / non-numeric ts / absent data', () => {
    expect(validateEnvelope({ type: 'status', loop_id: 1, ts: 0, data: {} })).toBe(false);
    expect(
      validateEnvelope({ type: 'status', loop_id: 1, seq: 1, ts: 'x', data: {} }),
    ).toBe(false);
    expect(validateEnvelope({ type: 'status', loop_id: 1, seq: 1, ts: 0 })).toBe(false);
  });

  it('rejects primitives and null', () => {
    expect(validateEnvelope(null)).toBe(false);
    expect(validateEnvelope('status')).toBe(false);
  });
});

describe('parseEnvelope', () => {
  it('parses valid JSON envelopes', () => {
    const env = parseEnvelope(JSON.stringify(statusEnvelope));
    expect(env).not.toBeNull();
    expect(env?.type).toBe('status');
    expect(env?.loop_id).toBe(12);
    expect(env?.seq).toBe(7);
  });

  it('returns null for invalid JSON and for non-envelopes', () => {
    expect(parseEnvelope('{oops')).toBeNull();
    expect(parseEnvelope(JSON.stringify({ type: 'auth_ok' }))).toBeNull();
  });
});

describe('isAuthOk', () => {
  it('recognises the handshake ack frame', () => {
    expect(isAuthOk({ type: 'auth_ok' })).toBe(true);
    expect(isAuthOk(statusEnvelope)).toBe(false);
    expect(isAuthOk(null)).toBe(false);
  });
});

describe('statusTimestampToEpoch', () => {
  it('passes through finite epoch-second numbers (monitor mode)', () => {
    expect(statusTimestampToEpoch(1718743200.5)).toBe(1718743200.5);
  });

  it('parses ISO-8601 strings to epoch seconds (execute mode)', () => {
    expect(statusTimestampToEpoch('2024-06-18T20:40:00.000Z')).toBe(1718743200);
  });

  it('returns null for garbage', () => {
    expect(statusTimestampToEpoch('not-a-date')).toBeNull();
    expect(statusTimestampToEpoch(Number.NaN)).toBeNull();
  });
});

describe('createSeqTracker', () => {
  const env = (seq: number, type: 'status' | 'alarm' = 'status', ts = seq * 10) =>
    ({ type, loop_id: 1, seq, ts, data: {} }) as const;

  it('reports no gap on the first observation', () => {
    const t = createSeqTracker();
    expect(t.observe(env(41))).toEqual({ gap: false, expected: null, received: 41 });
  });

  it('reports no gap for consecutive seq', () => {
    const t = createSeqTracker();
    t.observe(env(1));
    expect(t.observe(env(2)).gap).toBe(false);
  });

  it('reports a gap when seq jumps forward', () => {
    const t = createSeqTracker();
    t.observe(env(1));
    expect(t.observe(env(3))).toEqual({ gap: true, expected: 2, received: 3 });
  });

  it('reports a gap when seq regresses (daemon restart resets the bridge counter)', () => {
    const t = createSeqTracker();
    t.observe(env(100));
    expect(t.observe(env(1)).gap).toBe(true);
  });

  it('tracks last_seen_ts per topic class', () => {
    const t = createSeqTracker();
    t.observe(env(1, 'status', 10));
    t.observe(env(2, 'alarm', 20));
    t.observe(env(3, 'status', 30));
    expect(t.lastSeenTs('status')).toBe(30);
    expect(t.lastSeenTs('alarm')).toBe(20);
    expect(t.lastSeenTs('ai')).toBeNull();
  });

  it('reset() clears the seq baseline but KEEPS last_seen_ts (resync needs it)', () => {
    const t = createSeqTracker();
    t.observe(env(5, 'alarm', 55));
    t.reset();
    expect(t.lastSeenTs('alarm')).toBe(55);
    expect(t.observe(env(999)).gap).toBe(false); // fresh baseline after reconnect
  });
});