import { useMemo, useState } from 'react';
import type { ExportRequest } from '@/api/types';
import { Button } from '@/components/Button';
import { EmptyState } from '@/components/MissingState';
import { AlarmFooterBar } from '@/features/dashboard/AlarmFooterBar';
import { ExportButton } from '@/features/multitrend/ExportButton';
import { HistoryQuery } from '@/features/multitrend/HistoryQuery';
import { MultiTrendChart } from '@/features/multitrend/MultiTrendChart';
import { SeriesSelector } from '@/features/multitrend/SeriesSelector';
import { StatsPanel } from '@/features/multitrend/StatsPanel';
import { createTimeSync } from '@/features/multitrend/timeSync';
import { exportRange, useHistory, type HistoryWindow } from '@/features/multitrend/useHistory';
import { useMultiTrendModel } from '@/features/multitrend/useMultiTrendModel';
import { useStats, type UseStatsResult } from '@/features/multitrend/useStats';

/**
 * Multi-trend workspace (§6.8).
 *
 * Up to four loops occupy a 2×2 grid of charts that share one x-range: pan or
 * zoom any occupied cell and the siblings follow, which is the whole point of
 * looking at four loops at once. The loop roster comes from
 * `GET /controllers/stats` — a loop with no stats worker has nothing to trend
 * and nothing to score.
 */

/**
 * Roster the model may safely reconcile a persisted layout against (§9.2).
 *
 * `null` while pending OR errored: a fetch error must never read as "every
 * loop is gone" — that would permanently wipe an operator's saved trend
 * layout for a transient backend hiccup, not an actual roster change. Only a
 * genuinely resolved, successful roster reconciles.
 */
export function reconcilableRoster(
  stats: Pick<UseStatsResult, 'isPending' | 'isError' | 'loops'>,
): readonly number[] | null {
  return stats.isPending || stats.isError ? null : stats.loops;
}

export function MultiTrendPage() {
  const stats = useStats();
  const model = useMultiTrendModel(reconcilableRoster(stats));
  /** One shared x-range for every occupied cell, for the page's lifetime. */
  const sync = useMemo(() => createTimeSync(), []);
  const [loaded, setLoaded] = useState<HistoryWindow | null>(null);
  const history = useHistory(loaded);

  const occupiedLoops = model.slots.flatMap((s) =>
    s.controllerId === null ? [] : [s.controllerId],
  );
  const focusLoop = model.selection[0]?.loopId ?? stats.loops[0] ?? null;
  const exportRequest: ExportRequest | null =
    focusLoop === null
      ? null
      : { controller_id: focusLoop, ...exportRange(loaded), format: 'csv' };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="grid min-h-0 flex-1 gap-3 overflow-auto p-3 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <section aria-label="Tendências" className="flex min-w-0 flex-col gap-2">
          <div className="flex items-center justify-between gap-2">
            <h1 className="text-sm font-medium text-text">Tendências</h1>
            <Button size="sm" onClick={() => model.setPaused(!model.paused)}>
              {model.paused ? 'Retomar' : 'Pausar'}
            </Button>
          </div>

          <div
            data-testid="multitrend-chart"
            className="grid min-h-60 grid-cols-1 gap-2 xl:grid-cols-2"
          >
            {occupiedLoops.length === 0 ? (
              <EmptyState
                message="Nenhuma série selecionada."
                hint="Marque PV, SP ou CO de até quatro malhas para começar."
              />
            ) : (
              model.slots.map((slot, index) =>
                slot.controllerId === null ? null : (
                  <MultiTrendChart
                    key={slot.controllerId}
                    id={`slot-${index}`}
                    testId={`multitrend-slot-${index}`}
                    ariaLabel={`Tendência Loop ${slot.controllerId}`}
                    series={model.slotSeries[index]}
                    sync={sync}
                    onPxWidth={model.setPxWidth}
                  />
                ),
              )
            )}
          </div>

          <StatsPanel
            rows={stats.rows}
            isPending={stats.isPending}
            isError={stats.isError}
            onRetry={stats.refetch}
          />
        </section>

        <aside aria-label="Controles de tendência" className="flex min-w-0 flex-col gap-3">
          <SeriesSelector
            loops={stats.loops}
            isSelected={model.isSelected}
            isFull={model.isFull}
            occupiedLoops={occupiedLoops}
            onToggle={model.toggleSignal}
          />
          <HistoryQuery
            controllerId={focusLoop}
            frames={history.data?.frames ?? []}
            count={history.data?.count ?? 0}
            isPending={history.isPending}
            isError={history.isError}
            hasQueried={loaded !== null}
            onLoad={setLoaded}
          />
          <ExportButton request={exportRequest} />
        </aside>
      </div>
      <AlarmFooterBar />
    </div>
  );
}
