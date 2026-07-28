import { useId, useState } from 'react';
import { ErrorState, LoadingState } from '@/components/MissingState';
import { AiRoiPanel } from '@/features/executive/AiRoiPanel';
import { BadActorsTable } from '@/features/executive/BadActorsTable';
import { BackendHealthPanel } from '@/features/executive/BackendHealthPanel';
import { ExecutiveKpiBand } from '@/features/executive/ExecutiveKpiCard';
import {
  PERIOD_OPTIONS,
  useExecutiveData,
  type ExecutivePeriod,
} from '@/features/executive/useExecutiveData';
import { cn } from '@/lib/utils';

/**
 * Executive dashboard (§13 phase 9).
 *
 * Resolved §15 decision: this reuses the operational AppShell. The buyer keeps
 * the same navigation, session and alarm context as the operator, and there is
 * no evidence a second shell would help — so the latitude is spent on LAYOUT
 * (a wide, quiet KPI band over a two-column detail row), never on a second
 * token vocabulary. Every numeral is Geist Mono via `.numeric` (§6.2), and no
 * healthy state is painted green.
 *
 * The page owns no fetching: `useExecutiveData` seeds from REST and overlays
 * the live bus, reusing the roster, stats and status hooks the operational
 * pages already own.
 */

const CONTROL = cn(
  'min-h-11 rounded-control border border-rule-strong bg-surface-sunk px-2 text-sm text-text',
  'outline-none focus-visible:ring-2 focus-visible:ring-focus-ring',
);

export function ExecutiveDashboardPage() {
  const periodId = useId();
  const [period, setPeriod] = useState<ExecutivePeriod>('24h');
  const data = useExecutiveData(period);
  const periodLabel = PERIOD_OPTIONS.find((o) => o.key === period)?.label ?? '';

  return (
    <div
      data-testid="executive-dashboard"
      className="flex min-h-0 flex-1 flex-col gap-3 overflow-auto p-3"
    >
      <header className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="type-display text-lg uppercase tracking-widest text-text">
          Painel executivo
        </h1>
        <label htmlFor={periodId} className="flex flex-col gap-1 text-2xs text-text-soft">
          Período
          <select
            id={periodId}
            value={period}
            onChange={(e) => setPeriod(e.target.value as ExecutivePeriod)}
            className={cn(CONTROL, 'w-44')}
          >
            {PERIOD_OPTIONS.map((option) => (
              <option key={option.key} value={option.key}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </header>

      {data.isError ? (
        <ErrorState
          message="Não foi possível carregar todos os indicadores."
          onRetry={data.refetch}
        />
      ) : null}

      {data.isPending ? (
        <LoadingState label="Carregando indicadores…" bars={4} />
      ) : (
        <ExecutiveKpiBand kpis={data.kpis} />
      )}

      <div className="grid min-w-0 gap-3 lg:grid-cols-[minmax(0,1fr)_24rem]">
        <div className="flex min-w-0 flex-col gap-3">
          <BadActorsTable
            loops={data.badActors}
            isPending={data.isPending}
            isError={data.isError}
            onRetry={data.refetch}
          />
          <AiRoiPanel roi={data.roi} tuningEvents={data.tuningEvents} periodLabel={periodLabel} />
        </div>

        <BackendHealthPanel
          state={data.health}
          opc={data.opc}
          loops={data.loops}
          event={data.lastSystemEvent}
        />
      </div>
    </div>
  );
}
