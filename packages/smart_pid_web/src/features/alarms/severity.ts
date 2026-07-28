import type { AlarmSeverity, AlarmStatus } from './types';

/**
 * The four-severity presentation language (§6.4).
 *
 * Severity travels on THREE channels — text (`label`), shape (`glyph`) and
 * color (`token`). Color alone is banned, so nothing here may be consumed
 * without also rendering the label or the glyph.
 *
 * `token` names a themes.css contract variable; callers hand it to CSS via
 * `severityVar()` or `severityClass()` and never inline a literal color.
 */

export type SeverityGlyph = 'octagon' | 'triangle' | 'diamond' | 'dot';

export interface SeverityPresentation {
  label: AlarmSeverity;
  glyph: SeverityGlyph;
  token: string;
}

/** Wire order — also the sort order (most severe first). */
export const ALARM_SEVERITIES = ['CRITICAL', 'WARNING', 'ADVISORY', 'LOG'] as const;

export const SEVERITY_PRESENTATION: Record<AlarmSeverity, SeverityPresentation> = {
  CRITICAL: { label: 'CRITICAL', glyph: 'octagon', token: '--alarm-crit' },
  WARNING: { label: 'WARNING', glyph: 'triangle', token: '--alarm-warn' },
  ADVISORY: { label: 'ADVISORY', glyph: 'diamond', token: '--alarm-adv' },
  LOG: { label: 'LOG', glyph: 'dot', token: '--alarm-log' },
};

export function severity(value: AlarmSeverity): SeverityPresentation {
  return SEVERITY_PRESENTATION[value];
}

/** Lower rank = more severe. Drives flood sorting and bucket order. */
export function priorityRank(value: AlarmSeverity): number {
  return ALARM_SEVERITIES.indexOf(value);
}

/** An unknown wire priority must still be VISIBLE; LOG is the non-escalating bucket. */
export function toSeverity(priority: string): AlarmSeverity {
  const upper = priority.toUpperCase();
  return (ALARM_SEVERITIES as readonly string[]).includes(upper)
    ? (upper as AlarmSeverity)
    : 'LOG';
}

/** Stable class hook — `sev-critical` … resolves the glyph + stripe in index.css. */
export function severityClass(value: AlarmSeverity): string {
  return `sev-${value.toLowerCase()}`;
}

/** `var(--alarm-crit)` for the one inline channel (footer bucket color). */
export function severityVar(value: AlarmSeverity): string {
  return `var(${severity(value).token})`;
}

/** Unacked drives the non-color channel (weight + glyph + blink, §6.4). */
export function isUnackedStatus(status: AlarmStatus): boolean {
  return status === 'UNACKNOWLEDGED' || status === 'CLEARED_UNACK';
}
