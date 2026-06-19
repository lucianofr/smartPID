import { useMemo, useRef, useState } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { useActiveAlarms, useAlarmRealtimeSync, useAckAlarm, useAckAllAlarms } from './useAlarms';
import { priorityRank, severityIcon, severityClass, isUnacked } from './severity';
import type { ActiveAlarm, AlarmStatus } from './types';
import './AlarmPanel.css';

const ROW_HEIGHT = 32;

function formatLocal(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

type SortKey = 'severity' | 'time';

export function AlarmPanel(): JSX.Element {
  useAlarmRealtimeSync();
  const { data, isLoading, isError } = useActiveAlarms();

  // Backend is the source of truth: the mutation hooks fire the ack POST and
  // revalidate the active list via onSettled (never optimistic-mutate state).
  // isPending gates the buttons to prevent double-click duplicate dispatches.
  const ackOne = useAckAlarm();
  const ackAll = useAckAllAlarms();

  const [sortKey, setSortKey] = useState<SortKey>('severity');
  const [stateFilter, setStateFilter] = useState<'ALL' | AlarmStatus>('ALL');
  const [loopFilter, setLoopFilter] = useState<'ALL' | number>('ALL');

  const rows = useMemo(() => {
    // Dedupe by id (flood protection) — last write wins.
    const byId = new Map<number, ActiveAlarm>();
    for (const a of data ?? []) byId.set(a.id, a);
    let list = [...byId.values()];
    if (stateFilter !== 'ALL') list = list.filter((a) => a.status === stateFilter);
    if (loopFilter !== 'ALL') list = list.filter((a) => a.controller_id === loopFilter);
    list.sort((a, b) =>
      sortKey === 'severity'
        ? priorityRank(a.priority) - priorityRank(b.priority) ||
          b.timestamp.localeCompare(a.timestamp)
        : b.timestamp.localeCompare(a.timestamp),
    );
    return list;
  }, [data, stateFilter, loopFilter, sortKey]);

  const loopIds = useMemo(
    () => [...new Set((data ?? []).map((a) => a.controller_id))].sort((a, b) => a - b),
    [data],
  );
  const newCritical = useMemo(
    () => rows.filter((a) => a.priority === 'CRITICAL' && isUnacked(a.status)).length,
    [rows],
  );

  const parentRef = useRef<HTMLDivElement>(null);
  const virt = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 12,
  });

  if (isLoading) return <p className="alarm-panel__status">Loading alarms…</p>;
  if (isError) return <p className="alarm-panel__status" role="alert">Failed to load alarms.</p>;

  return (
    <section className="alarm-panel" aria-label="Active alarms">
      <header className="alarm-panel__toolbar">
        <label>
          Sort
          <select value={sortKey} onChange={(e) => setSortKey(e.target.value as SortKey)}>
            <option value="severity">Severity</option>
            <option value="time">Time</option>
          </select>
        </label>
        <label>
          Filter by state
          <select value={stateFilter} onChange={(e) => setStateFilter(e.target.value as 'ALL' | AlarmStatus)}>
            <option value="ALL">All</option>
            <option value="UNACKNOWLEDGED">Unacknowledged</option>
            <option value="ACKNOWLEDGED">Acknowledged</option>
            <option value="CLEARED_UNACK">Cleared (unacked)</option>
          </select>
        </label>
        <label>
          Filter by loop
          <select
            value={loopFilter}
            onChange={(e) => setLoopFilter(e.target.value === 'ALL' ? 'ALL' : Number(e.target.value))}
          >
            <option value="ALL">All loops</option>
            {loopIds.map((id) => <option key={id} value={id}>{id}</option>)}
          </select>
        </label>
        <button type="button" className="alarm-panel__ack-all"
          onClick={() => ackAll.mutate()} disabled={ackAll.isPending}>ACK ALL</button>
      </header>

      <div className="alarm-panel__live" role="status" aria-live="assertive">
        {newCritical > 0 ? `${newCritical} new critical alarm(s)` : ''}
      </div>

      <div className="alarm-panel__head" role="row">
        <span>Sev</span><span>Tag</span><span>Message</span><span>State</span><span>Time</span><span>Ack</span>
      </div>

      <div ref={parentRef} className="alarm-panel__scroll" data-testid="alarm-scroll">
        <div style={{ height: virt.getTotalSize(), position: 'relative' }}>
          {virt.getVirtualItems().map((vi) => {
            const a = rows[vi.index];
            const unacked = isUnacked(a.status);
            return (
              <div
                key={a.id}
                role="row"
                data-testid={`alarm-row-${a.id}`}
                className={`alarm-row ${severityClass(a.priority)} ${unacked ? 'is-unacked' : ''}`}
                style={{ position: 'absolute', top: 0, left: 0, width: '100%',
                  height: ROW_HEIGHT, transform: `translateY(${vi.start}px)` }}
              >
                <span className="alarm-row__sev">
                  <span className={`sev-icon sev-icon--${severityIcon(a.priority)}`} aria-hidden="true" />
                  {a.priority}
                </span>
                <span className="alarm-row__tag">{a.controller_name}</span>
                <span className="alarm-row__msg">
                  <span className="alarm-row__type">{a.alarm_type}</span> {a.value} (lim {a.limit})
                </span>
                <span className="alarm-row__state">{a.status}</span>
                <span className="alarm-row__time">{formatLocal(a.timestamp)}</span>
                <span className="alarm-row__ack">
                  <button type="button" onClick={() => ackOne.mutate(a.id)}
                    disabled={ackOne.isPending}>Ack</button>
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
