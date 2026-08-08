import type { ControllerResponse } from '@/api/types';
import { Badge } from '@/components/Badge';
import { activeAiStrategy } from '@/features/dashboard/LoopCard';
import { CHIP, EXEC_MODE_TITLE, MODE_CHIP, MODE_CHIP_FALLBACK, UNKNOWN_MODE_TITLE } from '@/features/dashboard/modeChip';
import type { ExecutionMode } from '@/features/loop-config/types';
import type { StatusData } from '@/lib/envelope';
import { formatNumber, formatPercent } from '@/lib/format';
import { cn } from '@/lib/utils';
import type { LoopStatsRow } from './useLoopStats';

/**
 * One loop's full performance snapshot (§6.8 Stats screen) — every indicator
 * `StatsResponse` carries, not the 8-column subset the multitrend `StatsPanel`
 * shows. Badge row reuses the exact dashboard `LoopCard` chips so a loop mode
 * reads identically everywhere in the app.
 */

const METRIC_DECIMALS = 2;
const INTEGER_DECIMALS = 0;

export interface Metric {
  label: string;
  title: string;
  value(row: LoopStatsRow): string;
}

export interface MetricGroup {
  title: string;
  metrics: readonly Metric[];
}

export const METRIC_GROUPS: readonly MetricGroup[] = [
  {
    title: 'Integrais de erro',
    metrics: [
      { label: 'IAE', title: 'Integral do erro absoluto', value: (r) => formatNumber(r.iae, METRIC_DECIMALS) },
      { label: 'ISE', title: 'Integral do erro quadrático', value: (r) => formatNumber(r.ise, METRIC_DECIMALS) },
      {
        label: 'ITAE',
        title: 'Integral do erro absoluto ponderada no tempo',
        value: (r) => formatNumber(r.itae, METRIC_DECIMALS),
      },
      { label: 'MSE', title: 'Erro quadrático médio', value: (r) => formatNumber(r.mse, METRIC_DECIMALS) },
      {
        label: 'MAE',
        title: 'Erro médio absoluto',
        value: (r) => formatNumber(r.mean_abs_error, METRIC_DECIMALS),
      },
    ],
  },
  {
    title: 'Variabilidade',
    metrics: [
      { label: 'σ', title: 'Desvio padrão do erro', value: (r) => formatNumber(r.std_dev, METRIC_DECIMALS) },
      {
        label: 'TV',
        title: 'Variação total do sinal de controle',
        value: (r) => formatNumber(r.total_variation, METRIC_DECIMALS),
      },
      {
        label: 'TV/amostra',
        title: 'Variação total por amostra',
        value: (r) => formatNumber(r.tv_per_sample, METRIC_DECIMALS),
      },
      {
        label: '2σ/SP',
        title: 'Variabilidade relativa ao setpoint',
        value: (r) => formatPercent(r.variability_sp),
      },
      {
        label: '2σ/Range',
        title: 'Variabilidade relativa à faixa',
        value: (r) => formatPercent(r.variability_range),
      },
      {
        label: 'Pico-pico erro',
        title: 'Amplitude pico a pico do erro na janela',
        value: (r) => formatNumber(r.pk_pk_error, METRIC_DECIMALS),
      },
      {
        label: 'Pico-pico erro (recente)',
        title: 'Amplitude pico a pico do erro na janela recente',
        value: (r) => formatNumber(r.recent_pk_pk_error, METRIC_DECIMALS),
      },
    ],
  },
  {
    title: 'Oscilação',
    metrics: [
      {
        label: 'Osc',
        title: 'Indicador de oscilação do processo (0–1)',
        value: (r) => formatNumber(r.osc, METRIC_DECIMALS),
      },
      {
        label: 'Período osc.',
        title: 'Período de oscilação medido, em segundos (0 = não mensurável)',
        value: (r) => formatNumber(r.osc_period_s, METRIC_DECIMALS),
      },
      {
        label: 'Amostras osc.',
        title: 'Amostras válidas para as métricas de oscilação (0 = não mensurado)',
        value: (r) => formatNumber(r.osc_sample_count, INTEGER_DECIMALS),
      },
      {
        label: 'Reversões',
        title: 'Número de reversões do erro na janela',
        value: (r) => formatNumber(r.reversals, INTEGER_DECIMALS),
      },
      {
        label: 'Reversões (recente)',
        title: 'Reversões do erro na janela recente',
        value: (r) => formatNumber(r.recent_reversals, INTEGER_DECIMALS),
      },
      {
        label: 'Cruzamentos por zero',
        title: 'Cruzamentos por zero do erro na janela',
        value: (r) => formatNumber(r.zero_crossings, INTEGER_DECIMALS),
      },
    ],
  },
  {
    title: 'Excitação',
    metrics: [
      {
        label: 'Pico-pico SP',
        title: 'Amplitude pico a pico do setpoint na janela, em unidades de engenharia',
        value: (r) => formatNumber(r.sp_pk_pk, METRIC_DECIMALS),
      },
      {
        label: 'Overshoot',
        title: 'Maior sobressinal em degrau de SP, como fração do degrau',
        value: (r) => formatPercent(r.overshoot),
      },
      {
        label: 'Amostras',
        title: 'Número de amostras na janela',
        value: (r) => formatNumber(r.sample_count, INTEGER_DECIMALS),
      },
    ],
  },
];

export interface LoopStatsCardProps {
  controller: ControllerResponse;
  /** Undefined when the loop has no stats worker — the roster is REST-driven. */
  statsRow: LoopStatsRow | undefined;
  /** Undefined until a live STATUS frame for this loop has arrived. */
  status: StatusData | undefined;
}

export function LoopStatsCard({ controller, statsRow, status }: LoopStatsCardProps) {
  // The live block mode, not `controller.mode` (the configured default) —
  // this screen must never present a stale REST field as the current state.
  const mode = status?.mode ?? 'UNKNOWN';
  const modeChip = MODE_CHIP[mode] ?? MODE_CHIP_FALLBACK;
  const strategy = activeAiStrategy(controller);
  const execMode = (controller.execution_mode as ExecutionMode | undefined) ?? 'SUPERVISORY';

  return (
    <div className="flex flex-col gap-3 rounded-card border border-rule bg-surface p-4 shadow-card">
      <div className="min-w-0">
        <p className="numeric truncate text-md font-bold text-text">{controller.name}</p>
        <p className="truncate text-sm text-text-soft">{controller.description}</p>
      </div>

      <div className="flex flex-wrap gap-1.5">
        <Badge
          tone="neutral"
          style={{ backgroundColor: modeChip.tint }}
          className={cn('numeric', CHIP, modeChip.text)}
          title={mode === 'UNKNOWN' ? UNKNOWN_MODE_TITLE : undefined}
        >
          {mode}
        </Badge>
        {/* The optimizer is the product's reason to exist: it gets a permanent
            slot, and an em dash when the loop opted out — not a missing chip. */}
        <Badge
          tone="neutral"
          title={strategy !== null ? `Otimização por IA: ${strategy}` : 'Sem otimização por IA'}
          className={cn(CHIP, strategy !== null ? 'bg-state-ai-soft text-state-ai' : 'text-text-soft')}
        >
          {strategy ?? '—'}
        </Badge>
        <Badge tone="neutral" title={EXEC_MODE_TITLE[execMode]} className={cn(CHIP, 'text-text-soft')}>
          {execMode}
        </Badge>
      </div>

      {statsRow === undefined ? (
        <p className="text-sm text-text-soft">Sem estatísticas para esta malha.</p>
      ) : (
        <div className="flex flex-col gap-3">
          {METRIC_GROUPS.map((group) => (
            <div key={group.title} className="flex flex-col gap-1">
              <h3 className="text-2xs font-semibold uppercase tracking-wider text-text-soft">
                {group.title}
              </h3>
              <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-sm">
                {group.metrics.map((metric) => (
                  <div key={metric.label} className="flex items-baseline justify-between gap-2" title={metric.title}>
                    <dt className="truncate text-text-soft">{metric.label}</dt>
                    <dd className="numeric text-text">{metric.value(statsRow)}</dd>
                  </div>
                ))}
              </dl>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
