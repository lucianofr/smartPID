import { describe, expect, it } from 'vitest';
import {
  ALARM_SEVERITIES,
  isUnackedStatus,
  priorityRank,
  severity,
  severityClass,
  severityVar,
  toSeverity,
} from '@/features/alarms/severity';

describe('severity presentation', () => {
  it('maps every severity to label, glyph and token', () => {
    expect(severity('CRITICAL')).toEqual({ label: 'CRITICAL', glyph: 'octagon', token: '--alarm-crit' });
    expect(severity('WARNING').glyph).toBe('triangle');
    expect(severity('ADVISORY').glyph).toBe('diamond');
    expect(severity('LOG').glyph).toBe('dot');
  });

  it('ranks wire order most severe first', () => {
    expect(ALARM_SEVERITIES).toEqual(['CRITICAL', 'WARNING', 'ADVISORY', 'LOG']);
    expect(priorityRank('CRITICAL')).toBeLessThan(priorityRank('LOG'));
  });

  it('unknown wire priorities degrade to LOG but stay visible', () => {
    expect(toSeverity('critical')).toBe('CRITICAL');
    expect(toSeverity('EMERGENCY')).toBe('LOG');
    expect(toSeverity('')).toBe('LOG');
  });
});

describe('class / var helpers', () => {
  it('produce stable class hooks and CSS var references', () => {
    expect(severityClass('CRITICAL')).toBe('sev-critical');
    expect(severityVar('WARNING')).toBe('var(--alarm-warn)');
  });

  it('unacked drives the non-color channel', () => {
    expect(isUnackedStatus('UNACKNOWLEDGED')).toBe(true);
    expect(isUnackedStatus('CLEARED_UNACK')).toBe(true);
    expect(isUnackedStatus('ACKNOWLEDGED')).toBe(false);
  });
});
