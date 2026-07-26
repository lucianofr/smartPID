import { useState } from 'react';
import { useCan } from '@/auth/useCan';
import { Button } from '@/components/Button';
import { EmptyState, ErrorState, LoadingState } from '@/components/MissingState';
import { VirtualList } from '@/components/VirtualList';
import { formatNumber, formatTimestamp } from '@/lib/format';
import { cn } from '@/lib/utils';
import { isUnackedStatus, severity, severityClass, toSeverity } from './severity';
import { DEFAULT_ALARM_FILTERS, useAlarms, type AlarmFilters, type AlarmSort } from './useAlarms';
import type { ActiveAlarm, AlarmStatus } from './types';

/**
 * Active alarm panel (§6.4/§7). Flood-safe by construction: the list is
 * windowed, rows are deduped by id, and a live flood reconciles through one
 * coalesced REST refetch instead of one render per frame.
 *
 * Every row states its severity three ways (glyph, label, token color) and its
 * acknowledgement two ways (status text + weight/stripe), so neither survives
 * on color alone.
 */

const ROW_HEIGHT = 48;
const GRID = 'grid grid-cols-[7.5rem_7rem_minmax(0,1fr)_9rem_5.5rem_4rem] items-center gap-2 px-3';

const STATUS_LABEL: Record<AlarmStatus | 'ALL', string> = {
  ALL: 'Todos',
  UNACKNOWLEDGED: 'Não reconhecidos',
  ACKNOWLEDGED: 'Reconhecidos',
  CLEARED_UNACK: 'Normalizados sem reconhecer',
};

const SELECT_CLASS = cn(
  'min-h-11 rounded-control border border-rule-strong bg-surface-sunk px-2 text-sm text-text',
  'outline-none focus-visible:ring-2 focus-visible:ring-focus-ring',
);

export interface AlarmRowLineProps {
  alarm: ActiveAlarm;
  canAck: boolean;
  ackPending: boolean;
  onAck: (id: number) => void;
}

function AlarmRowLine({ alarm, canAck, ackPending, onAck }: AlarmRowLineProps) {
  const sev = severity(toSeverity(alarm.priority));
  const unacked = isUnackedStatus(alarm.status);
  return (
    <div
      data-testid={`alarm-row-${alarm.id}`}
      className={cn(
        GRID,
        'alarm-row h-full border-b border-rule text-sm',
        severityClass(toSeverity(alarm.priority)),
        unacked && 'is-unacked alarm-blink',
      )}
    >
      <span className="inline-flex items-center gap-1.5 text-2xs font-medium tracking-wider">
        <span className={`sev-icon sev-icon--${sev.glyph}`} aria-hidden="true" />
        {sev.label}
      </span>
      <span className="truncate font-medium text-text">{alarm.controller_name ?? '—'}</span>
      <span className="truncate text-text">
        <span className="font-medium">{alarm.alarm_type}</span>{' '}
        <span className="numeric">{formatNumber(alarm.value, 2)}</span>{' '}
        <span className="text-text-soft">
          (lim <span className="numeric">{formatNumber(alarm.limit, 2)}</span>)
        </span>
      </span>
      <span className={cn('alarm-row__state text-2xs', unacked ? 'font-bold' : 'text-text-soft')}>
        {alarm.status}
      </span>
      <span className="numeric text-2xs text-text-soft">{formatTimestamp(alarm.timestamp)}</span>
      <Button
        size="sm"
        variant={unacked ? 'primary' : 'secondary'}
        disabled={!canAck || !unacked || ackPending}
        onClick={() => onAck(alarm.id)}
      >
        ACK
      </Button>
    </div>
  );
}

export function AlarmPanel() {
  const [filters, setFilters] = useState<AlarmFilters>(DEFAULT_ALARM_FILTERS);
  const { rows, loops, unackedCritical, isPending, isError, refetch, ack, ackAll } =
    useAlarms(filters);
  const canAck = useCan('alarms.ack');

  const patch = (next: Partial<AlarmFilters>): void =>
    setFilters((current) => ({ ...current, ...next }));

  return (
    <section aria-label="Alarmes ativos" className="flex min-h-0 flex-1 flex-col">
      <header className="flex flex-wrap items-end gap-3 border-b border-rule px-3 py-2">
        <label className="flex flex-col gap-1 text-2xs text-text-soft">
          Ordenar
          <select
            className={SELECT_CLASS}
            value={filters.sort}
            onChange={(e) => patch({ sort: e.target.value as AlarmSort })}
          >
            <option value="severity">Prioridade</option>
            <option value="time">Horário</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-2xs text-text-soft">
          Estado
          <select
            className={SELECT_CLASS}
            value={filters.status}
            onChange={(e) => patch({ status: e.target.value as AlarmStatus | 'ALL' })}
          >
            {(Object.keys(STATUS_LABEL) as (AlarmStatus | 'ALL')[]).map((value) => (
              <option key={value} value={value}>
                {STATUS_LABEL[value]}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-2xs text-text-soft">
          Malha
          <select
            className={SELECT_CLASS}
            value={String(filters.controllerId)}
            onChange={(e) =>
              patch({ controllerId: e.target.value === 'ALL' ? 'ALL' : Number(e.target.value) })
            }
          >
            <option value="ALL">Todas</option>
            {loops.map((loop) => (
              <option key={loop.id} value={loop.id}>
                {loop.name}
              </option>
            ))}
          </select>
        </label>
        <Button
          size="sm"
          variant={unackedCritical > 0 ? 'primary' : 'secondary'}
          className="ml-auto"
          disabled={!canAck || rows.length === 0 || ackAll.isPending}
          onClick={() => ackAll.mutate()}
        >
          ACK ALL
        </Button>
      </header>

      {/* Assertive because an unacknowledged CRITICAL is exactly the case that
          must interrupt — and it must survive `prefers-reduced-motion`. */}
      <span data-testid="alarm-panel-live" role="status" aria-live="assertive" className="sr-only">
        {unackedCritical > 0 ? `${unackedCritical} alarme(s) crítico(s) sem reconhecer` : ''}
      </span>

      <div
        className={cn(GRID, 'shrink-0 border-b border-rule py-1 text-2xs uppercase text-text-soft')}
      >
        <span>Prioridade</span>
        <span>Malha</span>
        <span>Evento</span>
        <span>Estado</span>
        <span>Horário</span>
        <span className="sr-only">Reconhecer</span>
      </div>

      {isPending ? (
        <LoadingState label="Carregando alarmes…" />
      ) : isError ? (
        <ErrorState message="Não foi possível carregar os alarmes." onRetry={refetch} />
      ) : rows.length === 0 ? (
        <EmptyState message="Nenhum alarme ativo." hint="A planta está dentro dos limites." />
      ) : (
        <div className="min-h-0 flex-1">
          <VirtualList
            items={rows}
            height="100%"
            estimateSize={ROW_HEIGHT}
            getKey={(row) => row.id}
            aria-label="Lista de alarmes ativos"
            renderItem={(row) => (
              <AlarmRowLine
                alarm={row}
                canAck={canAck}
                ackPending={ack.isPending}
                onAck={(id) => ack.mutate(id)}
              />
            )}
          />
        </div>
      )}
    </section>
  );
}
