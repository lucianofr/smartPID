import { describe, expect, it } from 'vitest';
import {
  createSeqTracker,
  isAuthOk,
  parseEnvelope,
  statusTimestampToEpoch,
  validateEnvelope,
} from '@/lib/envelope';

const valid = {
  type: 'status',
  loop_id: 3,
  seq: 1,
  ts: 1754500000,
  data: { controller_id: 3 },
};

describe('parseEnvelope', () => {
  it('parses a valid envelope and rejects garbage JSON or wrong shapes', () => {
    expect(parseEnvelope(JSON.stringify(valid))).toEqual(valid);
    expect(parseEnvelope('not json')).toBeNull();
    expect(parseEnvelope(JSON.stringify({ ...valid, type: 'bogus' }))).toBeNull();
    expect(parseEnvelope(JSON.stringify({ ...valid, seq: '1' }))).toBeNull();
    expect(parseEnvelope(JSON.stringify({ ...valid, data: undefined }))).toBeNull();
  });

  it('accepts a null loop_id for system events', () => {
    expect(validateEnvelope({ ...valid, type: 'system', loop_id: null })).toBe(true);
  });
});

describe('isAuthOk', () => {
  it('recognises the auth_ok handshake frame only', () => {
    expect(isAuthOk({ type: 'auth_ok' })).toBe(true);
    expect(isAuthOk(valid)).toBe(false);
    expect(isAuthOk(null)).toBe(false);
  });
});

describe('statusTimestampToEpoch', () => {
  it('normalises ISO strings and epoch seconds, null on garbage', () => {
    expect(statusTimestampToEpoch(1754500000)).toBe(1754500000);
    expect(statusTimestampToEpoch(new Date(1754500000 * 1000).toISOString())).toBe(1754500000);
    expect(statusTimestampToEpoch('garbage')).toBeNull();
    expect(statusTimestampToEpoch(Number.NaN)).toBeNull();
  });
});

describe('createSeqTracker', () => {
  it('flags gaps, seeds the baseline on first frame and resets across connections', () => {
    const tracker = createSeqTracker();
    expect(tracker.observe({ type: 'status', seq: 5, ts: 1 })).toEqual({
      gap: false,
      expected: null,
      received: 5,
    });
    expect(tracker.observe({ type: 'status', seq: 6, ts: 2 }).gap).toBe(false);
    expect(tracker.observe({ type: 'status', seq: 8, ts: 3 })).toEqual({
      gap: true,
      expected: 7,
      received: 8,
    });
    expect(tracker.lastSeenTs('status')).toBe(3);
    expect(tracker.lastSeenTs('alarm')).toBeNull();
    tracker.reset();
    expect(tracker.observe({ type: 'status', seq: 100, ts: 4 }).gap).toBe(false);
  });
});
