import { describe, expect, it } from 'vitest';
import {
  fromActiveRow,
  isActive,
  isUnacked,
  transition,
  type AlarmPointState,
} from './alarmMachine';

describe('transition — full 12-cell table', () => {
  const cases: Array<[AlarmPointState, 'TRIGGERED' | 'CLEARED' | 'ACK', AlarmPointState]> = [
    ['NORMAL', 'TRIGGERED', 'UNACKNOWLEDGED'],
    ['NORMAL', 'CLEARED', 'NORMAL'],
    ['NORMAL', 'ACK', 'NORMAL'],
    ['UNACKNOWLEDGED', 'TRIGGERED', 'UNACKNOWLEDGED'],
    ['UNACKNOWLEDGED', 'CLEARED', 'CLEARED_UNACK'],
    ['UNACKNOWLEDGED', 'ACK', 'ACKNOWLEDGED'],
    ['ACKNOWLEDGED', 'TRIGGERED', 'UNACKNOWLEDGED'],
    ['ACKNOWLEDGED', 'CLEARED', 'NORMAL'],
    ['ACKNOWLEDGED', 'ACK', 'ACKNOWLEDGED'],
    ['CLEARED_UNACK', 'TRIGGERED', 'UNACKNOWLEDGED'],
    ['CLEARED_UNACK', 'CLEARED', 'CLEARED_UNACK'],
    ['CLEARED_UNACK', 'ACK', 'NORMAL'],
  ];
  it.each(cases)('%s + %s -> %s', (from, kind, to) => {
    expect(transition(from, { kind })).toBe(to);
  });
});

describe('fromActiveRow — mirrors alarm_repo.py:129-132 CASE', () => {
  it('acknowledged & cleared → NORMAL (row leaves the active set)', () => {
    expect(fromActiveRow({ acknowledged: 1, cleared_at: '2026-07-26T00:00:00Z' })).toBe('NORMAL');
  });
  it('acknowledged & not cleared → ACKNOWLEDGED', () => {
    expect(fromActiveRow({ acknowledged: 1, cleared_at: null })).toBe('ACKNOWLEDGED');
  });
  it('unacknowledged & cleared → CLEARED_UNACK', () => {
    expect(fromActiveRow({ acknowledged: 0, cleared_at: '2026-07-26T00:00:00Z' })).toBe('CLEARED_UNACK');
  });
  it('unacknowledged & not cleared → UNACKNOWLEDGED', () => {
    expect(fromActiveRow({ acknowledged: 0, cleared_at: null })).toBe('UNACKNOWLEDGED');
  });
});

describe('predicates', () => {
  it('isUnacked: UNACKNOWLEDGED and CLEARED_UNACK only', () => {
    expect(isUnacked('UNACKNOWLEDGED')).toBe(true);
    expect(isUnacked('CLEARED_UNACK')).toBe(true);
    expect(isUnacked('ACKNOWLEDGED')).toBe(false);
    expect(isUnacked('NORMAL')).toBe(false);
  });
  it('isActive: UNACKNOWLEDGED and ACKNOWLEDGED only', () => {
    expect(isActive('UNACKNOWLEDGED')).toBe(true);
    expect(isActive('ACKNOWLEDGED')).toBe(true);
    expect(isActive('CLEARED_UNACK')).toBe(false);
    expect(isActive('NORMAL')).toBe(false);
  });
});