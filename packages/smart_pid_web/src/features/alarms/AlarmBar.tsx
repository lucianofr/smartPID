import { useMemo } from 'react';
import { useActiveAlarms, useAckAllAlarms, useAlarmRealtimeSync } from './useAlarms';
import { severityIcon, isUnacked } from './severity';
import type { ActiveAlarm, AlarmPriority } from './types';
import './AlarmBar.css';

const BUCKETS: { priority: AlarmPriority; label: string; testid: string }[] = [
  { priority: 'CRITICAL', label: 'CRIT', testid: 'count-critical' },
  { priority: 'WARNING', label: 'WARN', testid: 'count-warning' },
  { priority: 'ADVISORY', label: 'DIAG', testid: 'count-advisory' },
];

export function AlarmBar(): JSX.Element {
  useAlarmRealtimeSync();
  const { data } = useActiveAlarms();
  const ackAll = useAckAllAlarms();
  const rows = useMemo<ActiveAlarm[]>(() => data ?? [], [data]);

  const buckets = useMemo(
    () => BUCKETS.map((b) => {
      const inBucket = rows.filter((a) => a.priority === b.priority);
      return { ...b, count: inBucket.length, unacked: inBucket.some((a) => isUnacked(a.status)) };
    }),
    [rows],
  );

  const last = useMemo(
    () => [...rows].sort((a, b) => b.timestamp.localeCompare(a.timestamp))[0],
    [rows],
  );

  return (
    <footer className="alarm-bar" aria-label="Alarm summary">
      <div className="alarm-bar__counts">
        {buckets.map((b) => (
          <span
            key={b.priority}
            data-testid={b.testid}
            className={`alarm-bar__bucket sev-${b.priority.toLowerCase()} ${b.unacked ? 'is-unacked' : ''}`}
          >
            <span className={`sev-icon sev-icon--${severityIcon(b.priority)}`} aria-hidden="true" />
            <span className="alarm-bar__n">{b.count}</span> {b.label}
          </span>
        ))}
      </div>
      <span className="alarm-bar__last">
        {last ? `${last.controller_name}: ${last.alarm_type} ${last.status}` : 'No active alarms'}
      </span>
      <button type="button" className="alarm-bar__ack-all" disabled={ackAll.isPending}
        onClick={() => ackAll.mutate()}>ACK ALL</button>
    </footer>
  );
}
