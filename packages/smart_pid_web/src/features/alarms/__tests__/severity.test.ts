import { describe, expect, it } from 'vitest';
import {
  ALARM_SEVERITIES,
  SEVERITY_PRESENTATION,
  isUnackedStatus,
  priorityRank,
  severity,
  severityClass,
  severityVar,
  toSeverity,
} from '../severity';

describe('severity presentation map', () => {
  it('maps every severity to its label, glyph and contract token', () => {
    expect(severity('CRITICAL')).toEqual({
      label: 'CRITICAL',
      glyph: 'octagon',
      token: '--alarm-crit',
    });
    expect(severity('WARNING')).toEqual({
      label: 'WARNING',
      glyph: 'triangle',
      token: '--alarm-warn',
    });
    expect(severity('ADVISORY')).toEqual({
      label: 'ADVISORY',
      glyph: 'diamond',
      token: '--alarm-adv',
    });
    expect(severity('LOG')).toEqual({ label: 'LOG', glyph: 'dot', token: '--alarm-log' });
  });

  it('covers the four wire severities and nothing else', () => {
    expect(ALARM_SEVERITIES).toEqual(['CRITICAL', 'WARNING', 'ADVISORY', 'LOG']);
    expect(Object.keys(SEVERITY_PRESENTATION)).toEqual([...ALARM_SEVERITIES]);
  });

  it('gives every severity a distinct shape — severity is never color-only', () => {
    const glyphs = ALARM_SEVERITIES.map((s) => severity(s).glyph);
    expect(new Set(glyphs).size).toBe(glyphs.length);
  });
});

describe('priorityRank', () => {
  it('ranks CRITICAL first and LOG last', () => {
    expect(ALARM_SEVERITIES.map(priorityRank)).toEqual([0, 1, 2, 3]);
  });

  it('sorts a mixed flood most-severe first', () => {
    const mixed = ['LOG', 'CRITICAL', 'ADVISORY', 'WARNING'] as const;
    expect([...mixed].sort((a, b) => priorityRank(a) - priorityRank(b))).toEqual([
      'CRITICAL',
      'WARNING',
      'ADVISORY',
      'LOG',
    ]);
  });
});

describe('toSeverity', () => {
  it('accepts the wire values case-insensitively', () => {
    expect(toSeverity('critical')).toBe('CRITICAL');
    expect(toSeverity('WARNING')).toBe('WARNING');
  });

  it('degrades an unknown priority to LOG instead of dropping the alarm', () => {
    expect(toSeverity('WHATEVER')).toBe('LOG');
    expect(toSeverity('')).toBe('LOG');
  });
});

describe('presentation helpers', () => {
  it('derives the CSS class and the var() reference from the same token', () => {
    expect(severityClass('CRITICAL')).toBe('sev-critical');
    expect(severityVar('WARNING')).toBe('var(--alarm-warn)');
  });

  it('treats both unacknowledged row states as demanding acknowledgement', () => {
    expect(isUnackedStatus('UNACKNOWLEDGED')).toBe(true);
    expect(isUnackedStatus('CLEARED_UNACK')).toBe(true);
    expect(isUnackedStatus('ACKNOWLEDGED')).toBe(false);
  });
});
