import { describe, expect, it } from 'vitest';
import { fromActiveRow, isActive, isUnacked, transition } from '@/lib/alarmMachine';

describe('alarmMachine transition table', () => {
  it('covers every state/event pair', () => {
    const expected = {
      NORMAL: { TRIGGERED: 'UNACKNOWLEDGED', CLEARED: 'NORMAL', ACK: 'NORMAL' },
      UNACKNOWLEDGED: { TRIGGERED: 'UNACKNOWLEDGED', CLEARED: 'CLEARED_UNACK', ACK: 'ACKNOWLEDGED' },
      ACKNOWLEDGED: { TRIGGERED: 'UNACKNOWLEDGED', CLEARED: 'NORMAL', ACK: 'ACKNOWLEDGED' },
      CLEARED_UNACK: { TRIGGERED: 'UNACKNOWLEDGED', CLEARED: 'CLEARED_UNACK', ACK: 'NORMAL' },
    };
    for (const [state, events] of Object.entries(expected)) {
      for (const [kind, next] of Object.entries(events)) {
        expect(transition(state, { kind })).toBe(next);
      }
    }
  });

  it('a re-trigger on an acknowledged point demands a new ack (gap healing)', () => {
    expect(transition('ACKNOWLEDGED', { kind: 'TRIGGERED' })).toBe('UNACKNOWLEDGED');
  });
});

describe('fromActiveRow', () => {
  it('derives state from the REST row flags', () => {
    expect(fromActiveRow({ acknowledged: 0, cleared_at: null })).toBe('UNACKNOWLEDGED');
    expect(fromActiveRow({ acknowledged: 0, cleared_at: '2026-08-06T12:00:00Z' })).toBe('CLEARED_UNACK');
    expect(fromActiveRow({ acknowledged: 1, cleared_at: null })).toBe('ACKNOWLEDGED');
    expect(fromActiveRow({ acknowledged: 1, cleared_at: '2026-08-06T12:00:00Z' })).toBe('NORMAL');
  });
});

describe('isUnacked / isActive', () => {
  it('unacked drives the non-color channel; active means the condition persists', () => {
    expect(isUnacked('UNACKNOWLEDGED')).toBe(true);
    expect(isUnacked('CLEARED_UNACK')).toBe(true);
    expect(isUnacked('ACKNOWLEDGED')).toBe(false);
    expect(isActive('ACKNOWLEDGED')).toBe(true);
    expect(isActive('CLEARED_UNACK')).toBe(false);
    expect(isActive('NORMAL')).toBe(false);
  });
});
