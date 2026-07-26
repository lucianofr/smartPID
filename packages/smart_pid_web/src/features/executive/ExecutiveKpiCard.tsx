import { formatNumber, formatPercent } from '@/lib/format';
import { cn } from '@/lib/utils';
import { variabilityOutOfTarget, VARIABILITY_TARGET, type AggregateKpis } from './types';

/**
 * Buyer-facing KPI card (§6.4/§6.5 tokens — the executive dashboard shares the
 * operational vocabulary, it does not get one of its own).
 *
 * The latitude is TYPOGRAPHY, not colour: a large tabular numeral over a quiet
 * label. Colour never asserts a healthy state — an in-target KPI is the same
 * grey as every other readout, and only an off-target one promotes to the warn
 * token. The promotion is mirrored on `data-out-of-target` so the signal never
 * lives in colour alone.
 */

export interface ExecutiveKpiCardProps {
  label: string;
  /** Already formatted by `@/lib/format` — the card never formats. */
  value: string;
  /** One quiet line under the numeral: the target, the sample size, the unit. */
  hint?: string;
  outOfTarget?: boolean;
  testId?: string;
}

export function ExecutiveKpiCard({ label, value, hint, outOfTarget, testId }: ExecutiveKpiCardProps) {
  return (
    <article
      data-testid={testId}
      data-out-of-target={outOfTarget === undefined ? undefined : String(outOfTarget)}
      className="flex min-w-0 flex-col gap-1 border border-rule bg-surface-sunk px-4 py-3"
    >
      <span className="text-2xs font-medium uppercase tracking-wider text-text-soft">{label}</span>
      <span
        className={cn(
          'numeric text-2xl font-medium leading-none',
          outOfTarget === true ? 'text-alarm-warn' : 'text-text',
        )}
      >
        {value}
      </span>
      {hint === undefined ? null : (
        <span className={cn('text-2xs', outOfTarget === true ? 'text-alarm-warn' : 'text-text-soft')}>
          {hint}
        </span>
      )}
    </article>
  );
}

export interface ExecutiveKpiBandProps {
  kpis: AggregateKpis;
}

/**
 * The four KPIs the executive dashboard answers with. Labels and test ids live
 * here, once — the page only supplies the aggregate.
 */
export function ExecutiveKpiBand({ kpis }: ExecutiveKpiBandProps) {
  const varOff = variabilityOutOfTarget(kpis.averageVariabilityRange);
  const target = formatPercent(VARIABILITY_TARGET, 0);

  return (
    <section
      aria-label="Indicadores da planta"
      data-testid="executive-kpis"
      className="grid gap-2 [grid-template-columns:repeat(auto-fit,minmax(11rem,1fr))]"
    >
      <ExecutiveKpiCard
        testId="kpi-auto"
        label="Malhas em AUTO"
        value={formatPercent(kpis.autoPercent / 100)}
        hint={`${kpis.loopCount} malhas monitoradas`}
      />
      <ExecutiveKpiCard
        testId="kpi-ai"
        label="Cobertura da IA"
        value={formatPercent(kpis.aiCoveragePercent / 100)}
        hint="Otimização ligada com motor definido"
      />
      <ExecutiveKpiCard
        testId="kpi-iae"
        label="IAE médio"
        value={formatNumber(kpis.averageIae, 2)}
        hint="Integral do erro absoluto"
      />
      <ExecutiveKpiCard
        testId="kpi-variability"
        label="Variabilidade 2σ/RANGE"
        value={formatPercent(kpis.averageVariabilityRange)}
        outOfTarget={varOff}
        hint={varOff ? `Acima do alvo de ${target}` : `Alvo ${target}`}
      />
    </section>
  );
}
