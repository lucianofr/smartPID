import { useMutation, useQueryClient } from '@tanstack/react-query';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import { Button } from '@/components/Button';
import { toast } from '@/components/Toast';
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

/** Color is the unacked channel only (§6.9): a permanently red footer is banned. */
const UNACKED_COLOR: Record<AlarmSeverity, string> = {
  CRITICAL: 'var(--alarm-crit)',
  WARNING: 'var(--alarm-warn)',
  ADVISORY: 'var(--alarm-adv)',
  LOG: 'var(--alarm-log)',
};

const QUIET_COLOR = 'var(--text-soft)';

/**
 * Persistent alarm footer (§6.9). Quiet by default: with nothing
 * unacknowledged every bucket renders in `--text-soft`.
 *
 * Below 768 px the bucket row collapses to a single count chip. `ACK ALL`
 * survives the collapse — the 320 px floor must keep monitoring AND
 * acknowledgement, so the collapsed bar is the chip plus that one control.
 */
export function AlarmFooterBar({ className }: AlarmFooterBarProps) {
  const { buckets, totalUnacked, lastEvent } = useAlarmCounts();
  const queryClient = useQueryClient();

  const ackAll = useMutation({
    mutationFn: () => endpoints.ackAllAlarms(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.alarmsActive });
    },
    onError: () => {
      toast({ title: 'Falha ao reconhecer alarmes', tone: 'crit' });
    },
  });

  return (
    <footer
      aria-label="Alarm summary"
      className={cn(
        'flex shrink-0 items-center gap-3 border-t border-rule bg-surface px-3 py-1.5',
        className,
      )}
    >
      <div data-testid="alarm-buckets" className="flex items-center gap-4 max-md:hidden">
        {ALARM_SEVERITIES.map((severity) => {
          const bucket = buckets[severity];
          const unacked = bucket.unacked > 0;
          return (
            <span
              key={severity}
              data-testid={`count-${severity.toLowerCase()}`}
              className={cn('flex items-baseline gap-1.5 text-xs', unacked && 'is-unacked font-bold')}
              style={{ color: unacked ? UNACKED_COLOR[severity] : QUIET_COLOR }}
            >
              <span className="font-medium uppercase tracking-wider">{BUCKET_LABEL[severity]}</span>
              <span className="numeric text-sm">{bucket.active}</span>
              <span
                data-testid={`unacked-${severity.toLowerCase()}`}
                className="numeric text-2xs"
                title="não reconhecidos"
              >
                {bucket.unacked}
              </span>
            </span>
          );
        })}
      </div>

      <span
        data-testid="alarm-count-chip"
        className="numeric rounded-pill border border-rule px-2 py-0.5 text-xs md:hidden"
        style={{ color: totalUnacked > 0 ? UNACKED_COLOR.CRITICAL : QUIET_COLOR }}
      >
        {totalUnacked}
      </span>

      {lastEvent !== null ? (
        <span className="min-w-0 truncate text-2xs text-text-soft max-md:hidden">
          {formatTimestamp(lastEvent.timestamp)} · {lastEvent.controller_name}{' '}
          {lastEvent.alarm_type} {formatNumber(lastEvent.value, 1)}
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
