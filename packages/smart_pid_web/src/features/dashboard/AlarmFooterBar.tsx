import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import type { AlarmRow } from '@/api/types';
import { Button } from '@/components/Button';
import { severity, severityVar } from '@/features/alarms/severity';
import { useAckAllAlarms } from '@/features/alarms/useAlarms';
import { useReducedMotion } from '@/features/alarms/useReducedMotion';
import { formatNumber, formatTimestamp } from '@/lib/format';
import { cn } from '@/lib/utils';
import { ALARM_SEVERITIES, useAlarmCounts, type AlarmSeverity } from './useAlarmCounts';

export interface AlarmFooterBarProps {
  className?: string;
}

const BUCKET_LABEL: Record<AlarmSeverity, string> = {
  CRITICAL: 'CRIT',
  WARNING: 'WARN',
  ADVISORY: 'ADV',
  LOG: 'LOG',
};

const QUIET_COLOR = 'var(--text-soft)';

/** "10:00:00 · FIC-101 HIHI 99.0" — one line, whatever the source. */
function lastAlarmText(event: {
  timestamp: string;
  controller_name: string | null;
  alarm_type: string;
  value: number;
}): string {
  const tag = event.controller_name ?? '—';
  return `${formatTimestamp(event.timestamp)} · ${tag} ${event.alarm_type} ${formatNumber(event.value, 1)}`;
}

/**
 * Persistent alarm footer (§6.9). Quiet by default: with nothing
 * unacknowledged every bucket renders in `--text-soft`.
 *
 * Three encodings, so no single channel is load-bearing: the severity SHAPE,
 * the bucket COLOR (unacked only — a permanently red footer is banned) and the
 * unacked WEIGHT. The blink is a fourth, and under `prefers-reduced-motion` it
 * is replaced by a persistent count badge rather than simply dropped.
 *
 * Below 768 px the bucket row collapses to a single count chip. `ACK ALL`
 * survives the collapse — the 320 px floor must keep monitoring AND
 * acknowledgement, so the collapsed bar is the chip plus that one control.
 */
export function AlarmFooterBar({ className }: AlarmFooterBarProps) {
  const { buckets, totalUnacked, lastEvent } = useAlarmCounts();
  // Same canonical key `useAlarmCounts` already observes — deduped, no extra
  // request. The counts hook exposes buckets, not rows, and the footer needs a
  // row to name the last alarm before the first live frame arrives.
  const { data: rows } = useQuery({
    queryKey: queryKeys.alarmsActive,
    queryFn: () => endpoints.activeAlarms(),
  });
  const reducedMotion = useReducedMotion();
  const ackAll = useAckAllAlarms();

  const lastRow = useMemo(
    () =>
      (rows ?? []).reduce<AlarmRow | null>(
        (newest, row) => (newest === null || row.timestamp > newest.timestamp ? row : newest),
        null,
      ),
    [rows],
  );
  const lastText = lastEvent !== null ? lastAlarmText(lastEvent) : lastRow && lastAlarmText(lastRow);
  const unackedCritical = buckets.CRITICAL.unacked;

  return (
    <footer
      aria-label="Alarm summary"
      className={cn(
        'flex shrink-0 items-center gap-3 border-t border-rule bg-surface px-3 py-1.5',
        className,
      )}
    >
      <div data-testid="alarm-buckets" className="flex items-center gap-4 max-md:hidden">
        {ALARM_SEVERITIES.map((value) => {
          const bucket = buckets[value];
          const unacked = bucket.unacked > 0;
          const key = value.toLowerCase();
          return (
            <span
              key={value}
              data-testid={`count-${key}`}
              className={cn(
                'flex items-baseline gap-1.5 text-xs',
                unacked && 'is-unacked font-bold',
                unacked && !reducedMotion && 'alarm-blink',
              )}
              style={{ color: unacked ? severityVar(value) : QUIET_COLOR }}
            >
              <span
                className={`sev-icon sev-icon--${severity(value).glyph} self-center`}
                aria-hidden="true"
              />
              <span className="font-medium uppercase tracking-wider">{BUCKET_LABEL[value]}</span>
              <span className="alarm-count numeric text-sm">{bucket.active}</span>
              <span
                data-testid={`unacked-${key}`}
                className="numeric text-2xs"
                title="não reconhecidos"
              >
                {bucket.unacked}
              </span>
              {reducedMotion && unacked ? (
                <span
                  data-testid={`unacked-badge-${key}`}
                  aria-label={`${bucket.unacked} não reconhecidos em ${BUCKET_LABEL[value]}`}
                  className="numeric ml-1 inline-flex min-w-4 items-center justify-center border border-current px-1 text-2xs font-bold leading-none"
                >
                  {bucket.unacked}
                </span>
              ) : null}
            </span>
          );
        })}
      </div>

      <span
        data-testid="alarm-count-chip"
        className="numeric rounded-pill border border-rule px-2 py-0.5 text-xs md:hidden"
        style={{ color: totalUnacked > 0 ? severityVar('CRITICAL') : QUIET_COLOR }}
      >
        {totalUnacked}
      </span>

      {/* Assertive: an unacknowledged CRITICAL is exactly the case that must
          interrupt, and it is the channel that survives motion being off. */}
      <span data-testid="alarm-bar-live" role="status" aria-live="assertive" className="sr-only">
        {unackedCritical > 0 ? `${unackedCritical} alarme(s) crítico(s) sem reconhecer` : ''}
      </span>

      {lastText !== null ? (
        <span
          data-testid="alarm-last-event"
          className="min-w-0 truncate text-2xs text-text-soft max-md:hidden"
        >
          {lastText}
        </span>
      ) : null}

      <Button
        size="sm"
        variant={totalUnacked > 0 ? 'primary' : 'secondary'}
        className="ml-auto"
        disabled={totalUnacked === 0 || ackAll.isPending}
        onClick={() => ackAll.mutate()}
      >
        ACK ALL
      </Button>
    </footer>
  );
}
