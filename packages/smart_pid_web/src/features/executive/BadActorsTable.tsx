import { Link, useNavigate } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from '@/components/MissingState';
import { formatNumber, formatPercent } from '@/lib/format';
import { cn } from '@/lib/utils';
import { HEALTH_LABEL, variabilityOutOfTarget, type ExecutiveLoop } from './types';

/**
 * Worst offenders, already ranked by `rankBadActors` (descending IAE, then
 * variability). One row per loop, metrics as columns, so the same metric reads
 * down a column instead of being hunted per card — same contract as the
 * operational StatsPanel.
 *
 * A row is a shortcut into the operational dashboard: the tag is a real link
 * to `/?loop=<id>`, and the whole row forwards a bare click to it. The row
 * handler bails out when the link already handled the event, so a click on the
 * tag navigates exactly once.
 */

const CELL = 'border-b border-rule px-2 py-1.5 text-right';

export interface BadActorsTableProps {
  loops: readonly ExecutiveLoop[];
  isPending?: boolean;
  isError?: boolean;
  onRetry?(): void;
}

export function BadActorsTable({ loops, isPending = false, isError = false, onRetry }: BadActorsTableProps) {
  const navigate = useNavigate();

  if (isError) {
    return <ErrorState message="Não foi possível ranquear as malhas." onRetry={onRetry} />;
  }
  if (isPending) {
    return <LoadingState label="Ranqueando malhas…" bars={3} />;
  }
  if (loops.length === 0) {
    return (
      <EmptyState
        message="Nenhuma malha pontuada."
        hint="O ranking usa IAE e variabilidade; nenhuma malha reportou os dois."
      />
    );
  }

  return (
    <div className="min-w-0 overflow-x-auto border border-rule bg-surface-sunk">
      <table className="w-full border-collapse text-xs">
        <caption className="px-2 py-1.5 text-left text-2xs uppercase tracking-wider text-text-soft">
          Piores malhas
        </caption>
        <thead className="text-text-soft">
          <tr>
            <th scope="col" className="border-b border-rule px-2 py-1.5 text-left">
              Malha
            </th>
            <th scope="col" title="Integral do erro absoluto" className={CELL}>
              IAE
            </th>
            <th scope="col" title="Variabilidade relativa à faixa" className={CELL}>
              2σ/Range
            </th>
            <th scope="col" title="Variação total do sinal de controle" className={CELL}>
              TV
            </th>
            <th scope="col" className={CELL}>
              Estado
            </th>
          </tr>
        </thead>
        <tbody className="text-text">
          {loops.map((loop) => {
            const to = `/?loop=${loop.loopId}`;
            const off = variabilityOutOfTarget(loop.variabilityRange);
            return (
              <tr
                key={loop.loopId}
                data-testid={`bad-actor-${loop.loopId}`}
                className="cursor-pointer hover:bg-selection"
                onClick={(e) => {
                  if (e.defaultPrevented) return;
                  void navigate(to);
                }}
              >
                <th scope="row" className="border-b border-rule px-2 py-1.5 text-left font-normal">
                  <Link
                    to={to}
                    className="numeric rounded-control outline-none hover:text-accent focus-visible:ring-2 focus-visible:ring-focus-ring"
                  >
                    {loop.name}
                  </Link>
                </th>
                <td className={cn('numeric', CELL)}>{formatNumber(loop.iae, 2)}</td>
                <td
                  data-out-of-target={String(off)}
                  className={cn('numeric', CELL, off && 'text-alarm-warn')}
                >
                  {formatPercent(loop.variabilityRange)}
                </td>
                <td className={cn('numeric', CELL)}>{formatNumber(loop.tv, 2)}</td>
                <td className={cn(CELL, loop.health === 'error' && 'text-alarm-crit')}>
                  {HEALTH_LABEL[loop.health]}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
