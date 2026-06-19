import { describe, it, expect } from 'vitest';
import { priorityRank, severityIcon, severityClass, isUnacked } from '../severity';

describe('severity helpers', () => {
  it('ranks CRITICAL before WARNING before ADVISORY before LOG', () => {
    expect(priorityRank('CRITICAL')).toBeLessThan(priorityRank('WARNING'));
    expect(priorityRank('WARNING')).toBeLessThan(priorityRank('ADVISORY'));
    expect(priorityRank('ADVISORY')).toBeLessThan(priorityRank('LOG'));
  });

  it('maps each priority to a distinct geometric glyph (ISA-101: shape not just color)', () => {
    const glyphs = new Set([
      severityIcon('CRITICAL'),
      severityIcon('WARNING'),
      severityIcon('ADVISORY'),
    ]);
    expect(glyphs.size).toBe(3); // octagon / triangle / diamond
    expect(severityIcon('CRITICAL')).toBe('octagon');
    expect(severityIcon('WARNING')).toBe('triangle');
    expect(severityIcon('ADVISORY')).toBe('diamond');
  });

  it('maps priority to a stable CSS class token', () => {
    expect(severityClass('CRITICAL')).toBe('sev-critical');
    expect(severityClass('WARNING')).toBe('sev-warning');
    expect(severityClass('ADVISORY')).toBe('sev-advisory');
    expect(severityClass('LOG')).toBe('sev-log');
  });

  it('treats UNACKNOWLEDGED and CLEARED_UNACK as unacked (blink); ACKNOWLEDGED as stable', () => {
    expect(isUnacked('UNACKNOWLEDGED')).toBe(true);
    expect(isUnacked('CLEARED_UNACK')).toBe(true);
    expect(isUnacked('ACKNOWLEDGED')).toBe(false);
  });
});
