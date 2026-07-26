import { useMemo, useState } from 'react';
import { Button } from '@/components/Button';
import { EmptyState, ErrorState, LoadingState } from '@/components/MissingState';
import { VirtualList } from '@/components/VirtualList';
import { useControllers } from '@/features/dashboard/useControllers';
import { formatNumber, formatTimestamp } from '@/lib/format';
import { cn } from '@/lib/utils';
import { ALARM_SEVERITIES, severity, severityClass, toSeverity } from './severity';
import { ALARM_TYPES, type AlarmSeverity, type AlarmType } from './types';
import { HISTORY_LIMIT, useAlarmHistory, type AlarmHistoryFilter } from './useAlarms';

/**
 * Alarm history (§6.4). `/alarms/history` REQUIRES both bounds, so the range
 * is always explicit; priority and type are NOT query parameters there and are
 * narrowed client-side over the fetched window instead.
 *
 * Filters are staged in a draft and committed by `Aplicar filtros`: a half-typed
 * range must never fire a request, and a failed fetch must not eat the range
 * the operator just chose.
 */

const ROW_HEIGHT = 44;
const GRID = 'grid grid-cols-[7.5rem_7rem_minmax(0,1fr)_9rem_5.5rem_7rem] items-center gap-2 px-3';
const DAY_MS = 24 * 60 * 60 * 1000;

const SELECT_CLASS = cn(
  'min-h-11 rounded-control border border-rule-strong bg-surface-sunk px-2 text-sm text-text',
  'outline-none focus-visible:ring-2 focus-visible:ring-focus-ring',
);

export interface HistoryDraft {
  /** `datetime-local` wall-clock values — converted to ISO at request time. */
  start: string;
  end: string;
  priority: AlarmSeverity | 'ALL';
  type: AlarmType | 'ALL';
  controllerId: number | 'ALL';
}

/** `datetime-local` needs local wall clock; `toISOString` would shift the day. */
function toLocalValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function defaultDraft(): HistoryDraft {
  const now = new Date();
  return {
    start: toLocalValue(new Date(now.getTime() - DAY_MS)),
    end: toLocalValue(now),
    priority: 'ALL',
    type: 'ALL',
    controllerId: 'ALL',
  };
}

function toFilter(draft: HistoryDraft): AlarmHistoryFilter {
  return {
    start: new Date(draft.start).toISOString(),
    end: new Date(draft.end).toISOString(),
    limit: HISTORY_LIMIT,
    priority: draft.priority,
    type: draft.type,
    controllerId: draft.controllerId,
  };
}

function rangeError(draft: HistoryDraft): string | undefined {
  const start = Date.parse(draft.start);
  const end = Date.parse(draft.end);
  if (Number.isNaN(start) || Number.isNaN(end)) return 'Informe o início e o fim do período.';
  if (start >= end) return 'O início deve ser anterior ao fim.';
  return undefined;
}

export function AlarmHistory() {
  const [draft, setDraft] = useState<HistoryDraft>(defaultDraft);
  const [applied, setApplied] = useState<HistoryDraft>(draft);
  const controllers = useControllers();

  const filter = useMemo(() => toFilter(applied), [applied]);
  const query = useAlarmHistory(filter);
  const invalidRange = rangeError(draft);

  const patch = (next: Partial<HistoryDraft>): void =>
    setDraft((current) => ({ ...current, ...next }));

  const rows = query.data ?? [];

  return (
    <section aria-label="Histórico de alarmes" className="flex min-h-0 flex-1 flex-col">
      <form
        aria-label="Filtros do histórico"
        className="flex flex-wrap items-end gap-3 border-b border-rule px-3 py-2"
        onSubmit={(e) => {
          e.preventDefault();
          setApplied(draft);
        }}
      >
        <label className="flex flex-col gap-1 text-2xs text-text-soft">
          Início
          <input
            type="datetime-local"
            className={SELECT_CLASS}
            value={draft.start}
            onChange={(e) => patch({ start: e.target.value })}
          />
        </label>
        <label className="flex flex-col gap-1 text-2xs text-text-soft">
          Fim
          <input
            type="datetime-local"
            className={SELECT_CLASS}
            value={draft.end}
            onChange={(e) => patch({ end: e.target.value })}
          />
        </label>
        <label className="flex flex-col gap-1 text-2xs text-text-soft">
          Prioridade
          <select
            className={SELECT_CLASS}
            value={draft.priority}
            onChange={(e) => patch({ priority: e.target.value as AlarmSeverity | 'ALL' })}
          >
            <option value="ALL">Todas</option>
            {ALARM_SEVERITIES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-2xs text-text-soft">
          Tipo
          <select
            className={SELECT_CLASS}
            value={draft.type}
            onChange={(e) => patch({ type: e.target.value as AlarmType | 'ALL' })}
          >
            <option value="ALL">Todos</option>
            {ALARM_TYPES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-2xs text-text-soft">
          Malha
          <select
            className={SELECT_CLASS}
            value={String(draft.controllerId)}
            onChange={(e) =>
              patch({ controllerId: e.target.value === 'ALL' ? 'ALL' : Number(e.target.value) })
            }
          >
            <option value="ALL">Todas</option>
            {(controllers.data ?? []).map((controller) => (
              <option key={controller.id} value={controller.id}>
                {controller.name}
              </option>
            ))}
          </select>
        </label>
        <Button type="submit" size="sm" variant="primary" disabled={invalidRange !== undefined}>
          Aplicar filtros
        </Button>
        {invalidRange !== undefined ? (
          <p role="alert" className="text-2xs font-medium text-alarm-crit">
            {invalidRange}
          </p>
        ) : null}
      </form>

      <div
        className={cn(GRID, 'shrink-0 border-b border-rule py-1 text-2xs uppercase text-text-soft')}
      >
        <span>Prioridade</span>
        <span>Malha</span>
        <span>Evento</span>
        <span>Estado</span>
        <span>Horário</span>
        <span>Reconhecido</span>
      </div>

      {query.isPending ? (
        <LoadingState label="Carregando histórico…" />
      ) : query.isError ? (
        <ErrorState
          message="Não foi possível carregar o histórico."
          onRetry={() => void query.refetch()}
        />
      ) : rows.length === 0 ? (
        <EmptyState
          message="Nenhum alarme no período."
          hint="Amplie o intervalo ou remova os filtros."
        />
      ) : (
        <div className="min-h-0 flex-1">
          <VirtualList
            items={rows}
            height="100%"
            estimateSize={ROW_HEIGHT}
            getKey={(row) => row.id}
            aria-label="Lista do histórico de alarmes"
            renderItem={(row) => {
              const sev = severity(toSeverity(row.priority));
              return (
                <div
                  data-testid={`history-row-${row.id}`}
                  className={cn(
                    GRID,
                    'h-full border-b border-rule text-sm',
                    severityClass(toSeverity(row.priority)),
                  )}
                >
                  <span className="inline-flex items-center gap-1.5 text-2xs font-medium tracking-wider">
                    <span className={`sev-icon sev-icon--${sev.glyph}`} aria-hidden="true" />
                    {sev.label}
                  </span>
                  <span className="truncate font-medium text-text">
                    {row.controller_name ?? '—'}
                  </span>
                  <span className="truncate text-text">
                    <span className="font-medium">{row.alarm_type}</span>{' '}
                    <span className="numeric">{formatNumber(row.value, 2)}</span>{' '}
                    <span className="text-text-soft">
                      (lim <span className="numeric">{formatNumber(row.limit, 2)}</span>)
                    </span>
                  </span>
                  <span className="text-2xs text-text-soft">{row.status}</span>
                  <span className="numeric text-2xs text-text-soft">
                    {formatTimestamp(row.timestamp)}
                  </span>
                  <span className="truncate text-2xs text-text-soft">
                    {row.ack_by_user ?? '—'}
                  </span>
                </div>
              );
            }}
          />
        </div>
      )}
    </section>
  );
}
