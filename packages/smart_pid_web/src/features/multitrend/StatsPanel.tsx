import { EmptyState, ErrorState, LoadingState } from '@/components/MissingState';
import { formatNumber, formatPercent } from '@/lib/format';
import type { StatsRow } from './useStats';

/**
 * Loop performance metrics (§6.8) — one row per loop, metrics as columns, so
 * an operator compares the SAME metric down a column instead of hunting it in
 * per-loop cards.
 *
 * `src/lib/format` is the only formatter here: the deleted client's private
 * `multitrend/format.ts` (formatMetric / formatVariabilityPct) was folded into
 * `formatNumber` / `formatPercent` in phase 3 and must not come back.
 */

const METRIC_DECIMALS = 2;

interface Metric {
  label: string;
  value(row: StatsRow): string;
  title: string;
}

const METRICS: readonly Metric[] = [
  { label: 'IAE', title: 'Integral do erro absoluto', value: (r) => formatNumber(r.iae, METRIC_DECIMALS) },
  { label: 'ISE', title: 'Integral do erro quadrático', value: (r) => formatNumber(r.ise, METRIC_DECIMALS) },
  { label: 'ITAE', title: 'Integral do erro absoluto ponderada no tempo', value: (r) => formatNumber(r.itae, METRIC_DECIMALS) },
  { label: 'MSE', title: 'Erro quadrático médio', value: (r) => formatNumber(r.mse, METRIC_DECIMALS) },
  { label: 'σ', title: 'Desvio padrão do erro', value: (r) => formatNumber(r.sigma, METRIC_DECIMALS) },
  { label: '2σ/SP', title: 'Variabilidade relativa ao setpoint', value: (r) => formatPercent(r.varSp) },
  { label: '2σ/Range', title: 'Variabilidade relativa à faixa', value: (r) => formatPercent(r.varRange) },
  { label: 'TV', title: 'Variação total do sinal de controle', value: (r) => formatNumber(r.tv, METRIC_DECIMALS) },
];

const CELL = 'border-b border-rule px-2 py-1.5 text-right';

export interface StatsPanelProps {
  rows: readonly StatsRow[];
  isPending?: boolean;
  isError?: boolean;
  onRetry?(): void;
}

export function StatsPanel({ rows, isPending = false, isError = false, onRetry }: StatsPanelProps) {
  if (isError) {
    return (
      <ErrorState message="Não foi possível carregar as estatísticas." onRetry={onRetry} />
    );
  }
  if (isPending) {
    return <LoadingState label="Carregando estatísticas…" bars={3} />;
  }
  if (rows.length === 0) {
    return (
      <EmptyState
        message="Sem estatísticas disponíveis."
        hint="As métricas aparecem quando um worker de estatísticas está ativo."
      />
    );
  }

  return (
    <div className="min-w-0 overflow-x-auto border border-rule bg-surface-sunk">
      <table className="w-full border-collapse text-xs">
        <caption className="px-2 py-1.5 text-left text-2xs uppercase tracking-wider text-text-soft">
          Estatísticas
        </caption>
        <thead className="text-text-soft">
          <tr>
            <th scope="col" className="border-b border-rule px-2 py-1.5 text-left">
              Malha
            </th>
            {METRICS.map((metric) => (
              <th key={metric.label} scope="col" title={metric.title} className={CELL}>
                {metric.label}
              </th>
            ))}
            <th scope="col" className={CELL}>
              Amostras
            </th>
          </tr>
        </thead>
        <tbody className="text-text">
          {rows.map((row) => (
            <tr key={row.loopId}>
              <th scope="row" className="numeric border-b border-rule px-2 py-1.5 text-left font-normal">
                Loop {row.loopId}
              </th>
              {METRICS.map((metric) => (
                <td key={metric.label} className={`numeric ${CELL}`}>
                  {metric.value(row)}
                </td>
              ))}
              <td className={`numeric ${CELL}`}>{row.sampleCount}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
