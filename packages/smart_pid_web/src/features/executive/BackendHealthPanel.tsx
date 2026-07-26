import { Badge } from '@/components/Badge';
import { ErrorState } from '@/components/MissingState';
import { formatNumber, formatTimestamp } from '@/lib/format';
import type { SystemEventData } from '@/lib/envelope';
import { cn } from '@/lib/utils';
import { HEALTH_LABEL, type BackendHealthState, type ExecutiveLoop, type OpcState } from './types';

/**
 * Backend health (§13 phase 9).
 *
 * Two halves: the process counters `GET /system/status` publishes, and the
 * per-loop reachability an operator would otherwise have to infer from the
 * Loops page. Grey is the normal state everywhere — only an abnormal reading
 * (bus down, OPC not ONLINE, a non-INFO system event, a faulted block) takes
 * the alarm token, and every promotion is mirrored on a data attribute so the
 * signal never lives in colour alone.
 *
 * CPU and memory are optional on purpose: routers/system.py publishes neither
 * today and EVENT.SYSTEM carries no counters, so they read '—' rather than a
 * fabricated 0.
 */

/**
 * Uptime in the two largest units that still carry information — 3661 s is
 * "1 h 1 min", not "1:01:01". Seconds stop mattering after the first minute.
 */
export function formatUptime(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds) || seconds < 0) {
    return '—';
  }
  const total = Math.floor(seconds);
  const days = Math.floor(total / 86_400);
  const hours = Math.floor((total % 86_400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  if (days > 0) return `${days} d ${hours} h`;
  if (hours > 0) return `${hours} h ${minutes} min`;
  return `${minutes} min`;
}

/** One label/value line. Values arrive pre-formatted; the row never formats. */
function HealthRow({
  label,
  value,
  abnormal,
  testId,
}: {
  label: string;
  value: string;
  abnormal?: boolean;
  testId?: string;
}) {
  return (
    <div
      data-testid={testId}
      data-abnormal={abnormal === undefined ? undefined : String(abnormal)}
      className="flex items-baseline justify-between gap-3 border-b border-rule px-2 py-1.5"
    >
      <span className="text-2xs uppercase tracking-wider text-text-soft">{label}</span>
      <span className={cn('numeric text-sm', abnormal === true ? 'text-alarm-warn' : 'text-text')}>
        {value}
      </span>
    </div>
  );
}

export interface BackendHealthPanelProps {
  state: BackendHealthState;
  opc?: OpcState;
  loops?: readonly ExecutiveLoop[];
  /** Latest EVENT.SYSTEM frame, or null before one arrives. */
  event?: SystemEventData | null;
  isError?: boolean;
  onRetry?(): void;
}

export function BackendHealthPanel({
  state,
  opc,
  loops = [],
  event = null,
  isError = false,
  onRetry,
}: BackendHealthPanelProps) {
  if (isError) {
    return <ErrorState message="Não foi possível ler a saúde do backend." onRetry={onRetry} />;
  }

  const busDown = state.bus_active === false;
  const opcDown = opc !== undefined && opc !== 'ONLINE';
  // The worker types severity freely (system_event_worker.py); INFO is the only
  // string it emits for a normal event, so anything else is worth a look.
  const eventAbnormal = event !== null && event.severity !== 'INFO';

  return (
    <section
      aria-label="Saúde do backend"
      data-testid="backend-health"
      className="flex min-w-0 flex-col gap-3 border border-rule bg-surface-sunk p-3"
    >
      <h2 className="text-2xs uppercase tracking-wider text-text-soft">Saúde do backend</h2>

      <div className="flex flex-col">
        <HealthRow label="CPU" value={percentOrDash(state.cpu_percent)} testId="health-cpu" />
        <HealthRow label="Memória" value={percentOrDash(state.memory_percent)} testId="health-memory" />
        <HealthRow label="Tempo ativo" value={formatUptime(state.uptime_s)} testId="health-uptime" />
        <HealthRow
          label="Controladores ativos"
          value={formatNumber(state.active_controllers, 0)}
          testId="health-controllers"
        />
        <HealthRow
          label="Barramento"
          value={state.bus_active === undefined ? '—' : state.bus_active ? 'Ativo' : 'Inativo'}
          abnormal={busDown}
          testId="health-bus"
        />
        <HealthRow label="OPC-UA" value={opc ?? '—'} abnormal={opcDown} testId="health-opc" />
        <HealthRow label="Versão da API" value={state.api_version ?? '—'} testId="health-api" />
      </div>

      {event === null ? null : (
        <p
          data-testid="health-event"
          data-abnormal={String(eventAbnormal)}
          className={cn('text-2xs', eventAbnormal ? 'text-alarm-warn' : 'text-text-soft')}
        >
          <span className="numeric">{formatTimestamp(event.timestamp)}</span> · {event.source} ·{' '}
          {event.message}
        </p>
      )}

      {loops.length === 0 ? null : (
        <div className="flex flex-col">
          {loops.map((loop) => (
            <div
              key={loop.loopId}
              data-testid={`health-${loop.name}`}
              data-health={loop.health}
              className="flex items-baseline gap-3 border-b border-rule px-2 py-1.5 text-xs"
            >
              <span className="numeric min-w-0 flex-1 truncate text-text">{loop.name}</span>
              <span className="numeric text-text-soft">{loop.mode}</span>
              <span
                data-testid={`health-${loop.name}-state`}
                className={loop.health === 'error' ? 'text-alarm-crit' : 'text-text-soft'}
              >
                {HEALTH_LABEL[loop.health]}
              </span>
              <Badge
                data-testid={`health-${loop.name}-opc`}
                tone={opcDown ? 'warn' : 'neutral'}
                className="numeric"
              >
                {opc ?? '—'}
              </Badge>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

/** `/system/status` reports percentages as 0-100 numbers, not ratios. */
function percentOrDash(value: number | null | undefined): string {
  const num = formatNumber(value, 1);
  return num === '—' ? num : `${num}%`;
}
