import { EmptyState, ErrorState, LoadingState } from '@/components/MissingState';
import { formatNumber, formatPercent } from '@/lib/format';
import { cn } from '@/lib/utils';
import type { AiRoi } from './types';

/**
 * AI return on investment (§13 phase 9).
 *
 * The only before/after evidence the backend keeps is the AI tuning log: each
 * row carries the objective metric measured at that tuning. `aiRoi` turns that
 * into a first-versus-last comparison per loop; when the window cannot support
 * one it hands back null, and this panel says so instead of rendering zeros.
 * A regression is shown as a negative gain — never hidden, never re-signed.
 */

export interface AiRoiPanelProps {
  roi: AiRoi | null;
  /** Tunings in the window, including the ones too sparse to be scored. */
  tuningEvents: number;
  periodLabel: string;
  isPending?: boolean;
  isError?: boolean;
  onRetry?(): void;
}

export function AiRoiPanel({
  roi,
  tuningEvents,
  periodLabel,
  isPending = false,
  isError = false,
  onRetry,
}: AiRoiPanelProps) {
  if (isError) {
    return <ErrorState message="Não foi possível ler o histórico de sintonia." onRetry={onRetry} />;
  }

  const worse = roi !== null && roi.improvement < 0;

  return (
    <section
      aria-label="Retorno da IA"
      data-testid="ai-roi"
      className="flex min-w-0 flex-col gap-3 border border-rule bg-surface-sunk p-3"
    >
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-2xs uppercase tracking-wider text-text-soft">Retorno da IA</h2>
        <span className="text-2xs text-text-soft">{periodLabel}</span>
      </div>

      {isPending ? <LoadingState label="Carregando histórico de sintonia…" bars={2} /> : null}

      {!isPending && roi === null ? (
        <EmptyState
          message="Dados insuficientes para comparar antes e depois."
          hint="A comparação exige ao menos duas sintonias pontuadas na mesma malha dentro do período."
        />
      ) : null}

      {!isPending && roi !== null ? (
        <dl className="grid grid-cols-3 gap-2">
          <div className="flex flex-col gap-0.5">
            <dt className="text-2xs uppercase tracking-wider text-text-soft">Métrica antes</dt>
            <dd data-testid="roi-before" className="numeric text-xl text-text">
              {formatNumber(roi.metricBefore, 2)}
            </dd>
          </div>
          <div className="flex flex-col gap-0.5">
            <dt className="text-2xs uppercase tracking-wider text-text-soft">Métrica depois</dt>
            <dd data-testid="roi-after" className="numeric text-xl text-text">
              {formatNumber(roi.metricAfter, 2)}
            </dd>
          </div>
          <div className="flex flex-col gap-0.5">
            <dt className="text-2xs uppercase tracking-wider text-text-soft">Ganho</dt>
            <dd
              data-testid="roi-improvement"
              data-out-of-target={String(worse)}
              className={cn('numeric text-xl', worse ? 'text-alarm-warn' : 'text-text')}
            >
              {formatPercent(roi.improvement)}
            </dd>
          </div>
          <div className="col-span-3 text-2xs text-text-soft">
            <span className="numeric">{roi.loopsCompared}</span> malhas comparadas
          </div>
        </dl>
      ) : null}

      <p className="text-2xs text-text-soft">
        <span data-testid="roi-events" className="numeric">
          {tuningEvents}
        </span>{' '}
        sintonias no período
      </p>
    </section>
  );
}
