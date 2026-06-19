import type { AlarmPriority, AlarmStatus } from './types';

const RANK: Record<AlarmPriority, number> = {
  CRITICAL: 0,
  WARNING: 1,
  ADVISORY: 2,
  LOG: 3,
};

export type SeverityGlyph = 'octagon' | 'triangle' | 'diamond' | 'dot';

const GLYPH: Record<AlarmPriority, SeverityGlyph> = {
  CRITICAL: 'octagon',
  WARNING: 'triangle',
  ADVISORY: 'diamond',
  LOG: 'dot',
};

/** Lower number = higher severity (CRITICAL=0). Used for sort + counters. */
export function priorityRank(p: AlarmPriority): number {
  return RANK[p];
}

/** ISA-101 §8.2: severity is also a SHAPE, never color alone. */
export function severityIcon(p: AlarmPriority): SeverityGlyph {
  return GLYPH[p];
}

/** Stable CSS class token → resolves to --alarm-* / --alarm-*-bg in themes.css. */
export function severityClass(p: AlarmPriority): string {
  return `sev-${p.toLowerCase()}`;
}

/** Unacked rows blink (icon/counter opacity); ACKNOWLEDGED rows are stable (§6.4). */
export function isUnacked(status: AlarmStatus): boolean {
  return status === 'UNACKNOWLEDGED' || status === 'CLEARED_UNACK';
}
