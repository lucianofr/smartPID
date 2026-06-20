import { useMemo } from 'react';
import { useActiveAlarms, useAckAllAlarms, useAlarmRealtimeSync } from './useAlarms';
import { severityIcon, isUnacked } from './severity';
import { useReducedMotion } from './useReducedMotion';
import type { ActiveAlarm, AlarmPriority } from './types';

const BUCKETS: { priority: AlarmPriority; label: string; testid: string }[] = [
  { priority: 'CRITICAL', label: 'CRIT', testid: 'count-critical' },
  { priority: 'WARNING', label: 'WARN', testid: 'count-warning' },
  { priority: 'ADVISORY', label: 'DIAG', testid: 'count-advisory' },
];

export function AlarmBar(): JSX.Element {
  useAlarmRealtimeSync();
  const { data } = useActiveAlarms();
  const ackAll = useAckAllAlarms();
  const reducedMotion = useReducedMotion();
  const rows = useMemo<ActiveAlarm[]>(() => data ?? [], [data]);

  const buckets = useMemo(
    () => BUCKETS.map((b) => {
      const inBucket = rows.filter((a) => a.priority === b.priority);
      const unackedCount = inBucket.filter((a) => isUnacked(a.status)).length;
      return { ...b, count: inBucket.length, unackedCount, unacked: unackedCount > 0 };
    }),
    [rows],
  );

  const last = useMemo(
    () => [...rows].sort((a, b) => b.timestamp.localeCompare(a.timestamp))[0],
    [rows],
  );

  const newCritical = useMemo(
    () => rows.filter((a) => a.priority === 'CRITICAL' && isUnacked(a.status)).length,
    [rows],
  );

  return (
    <footer
      // Responsive (Task 9.2 / §9): the bar is the 36px strip at >=1024; below the 1024 token
      // breakpoint it relaxes to `h-auto`/`min-h-11` so the ACK ALL touch target can reach 44px.
      className="alarm-bar flex h-[var(--alarmbar-h)] items-center gap-4 px-3 border-t border-divider bg-surface-container text-text-secondary max-lg:h-auto max-lg:min-h-11 max-lg:py-1"
      style={{ fontSize: 'var(--text-sm)' }}
      aria-label="Alarm summary"
    >
      <div className="alarm-bar__counts flex gap-3">
        {buckets.map((b) => (
          <span
            key={b.priority}
            data-testid={b.testid}
            className={`alarm-bar__bucket inline-flex items-center gap-1.5 sev-${b.priority.toLowerCase()} ${b.unacked ? 'is-unacked' : ''}`}
          >
            <span className={`sev-icon sev-icon--${severityIcon(b.priority)}`} aria-hidden="true" />
            <span className="alarm-bar__n numeric font-semibold">{b.count}</span> {b.label}
            {/* Reduced-motion path: a persistent badge re-encodes unacked-vs-seen
                without relying on the (suppressed) blink. */}
            {reducedMotion && b.unackedCount > 0 && (
              <span
                data-testid={`unacked-badge-${b.priority.toLowerCase()}`}
                className="alarm-bar__badge numeric ml-1 inline-flex min-w-4 items-center justify-center border border-border-strong px-1 font-bold leading-none"
                style={{ fontSize: 'var(--text-2xs)' }}
                aria-label={`${b.unackedCount} unacknowledged ${b.label}`}
              >
                {b.unackedCount}
              </span>
            )}
          </span>
        ))}
      </div>
      {/* Assertive announcement for new unacked CRITICAL — survives motion off. */}
      <span
        data-testid="alarm-bar-live"
        className="sr-only"
        role="status"
        aria-live="assertive"
      >
        {newCritical > 0 ? `${newCritical} new critical alarm(s)` : ''}
      </span>
      <span className="alarm-bar__last overflow-hidden text-ellipsis whitespace-nowrap text-text-secondary">
        {last ? `${last.controller_name}: ${last.alarm_type} ${last.status}` : 'No active alarms'}
      </span>
      <button
        type="button"
        // Responsive (Task 9.2 / §9): grows to the 44px touch floor below the 1024 breakpoint.
        className="alarm-bar__ack-all ml-auto max-lg:inline-flex max-lg:min-h-11 max-lg:min-w-11 max-lg:items-center max-lg:justify-center max-lg:px-3"
        disabled={ackAll.isPending}
        onClick={() => ackAll.mutate()}
      >
        ACK ALL
      </button>
    </footer>
  );
}
