import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Button } from '@/components/Button';
import { EmptyState, ErrorState, LoadingState } from '@/components/MissingState';
import { AlarmFooterBar } from '@/features/dashboard/AlarmFooterBar';
import { Faceplate } from '@/features/dashboard/Faceplate';
import { LoopCard } from '@/features/dashboard/LoopCard';
import { TrendPanel } from '@/features/dashboard/TrendPanel';
import { pvScale, useControllers } from '@/features/dashboard/useControllers';
import { useLoopStatuses } from '@/features/dashboard/useLoopStatuses';
import { CardControls } from '@/features/loop-config/CardControls';
import { LoopConfigDialog, NewLoopDialog } from '@/features/loop-config/LoopConfigDialog';
import { SimulationModeBanner } from '@/features/simulator/SimulationModeBanner';
import { useTwinRunning } from '@/features/simulator/useSimulatorStatus';
import { useCan } from '@/auth/useCan';
import { useConnectionStatus } from '@/realtime/useConnectionStatus';
import { cn } from '@/lib/utils';

/**
 * Operational dashboard (§6.9).
 *
 * Layout contract (§4): at ≥1024 the page is two columns — a full-height
 * ~320 px faceplate rail on the left, the non-wrapping card strip and the trend
 * stacked in the right column (trend keeps ≥65% at 1440). Below 1024 the three
 * bands stack in DOM order (cards, trend, faceplate) and the page scrolls. The
 * simulation banner and the alarm footer stay full width: they are page-level
 * bands, not loop detail. The alarm footer collapses to a count chip under 768.
 *
 * `/?loop=<id>` preselects one loop: it is the landing target of the executive
 * dashboard's bad-actor rows (phase 9). The param seeds the initial selection
 * only — clicking a card afterwards must not be undone by a stale URL.
 */
export function DashboardPage() {
  const controllers = useControllers();
  const statuses = useLoopStatuses();
  const canManage = useCan('controllers.manage');
  const { stale } = useConnectionStatus();
  const twinRunning = useTwinRunning();
  const [params] = useSearchParams();
  const [selectedId, setSelectedId] = useState<number | null>(() => {
    const asked = Number(params.get('loop'));
    return Number.isInteger(asked) && asked > 0 ? asked : null;
  });
  const [configId, setConfigId] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);

  const newLoopDialog = canManage ? (
    <NewLoopDialog
      open={creating}
      onClose={() => setCreating(false)}
      onCreated={(created) => setSelectedId(created.id)}
    />
  ) : null;
  const newLoopButton = canManage ? (
    <Button variant="secondary" size="sm" onClick={() => setCreating(true)}>
      Nova malha
    </Button>
  ) : null;

  if (controllers.isPending) {
    return <LoadingState label="Carregando malhas…" />;
  }
  if (controllers.isError) {
    return (
      <ErrorState
        message="Não foi possível carregar as malhas."
        onRetry={() => void controllers.refetch()}
      />
    );
  }
  if (controllers.data.length === 0) {
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <EmptyState
          className="flex-1"
          message="Nenhuma malha configurada."
          hint="Cadastre um controlador para começar."
          action={newLoopButton}
        />
        {newLoopDialog}
        <AlarmFooterBar />
      </div>
    );
  }

  const selected = controllers.data.find((c) => c.id === selectedId) ?? controllers.data[0];
  const configTarget = controllers.data.find((c) => c.id === configId) ?? null;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* A model driving the plant is a fact the Loops page must not hide.
          Cache-only read: the §7 resync already primes the twin snapshot. */}
      {twinRunning ? <SimulationModeBanner running /> : null}
      <div
        data-testid="dashboard-detail"
        className="flex min-h-0 flex-1 flex-col overflow-y-auto lg:flex-row lg:overflow-hidden"
      >
        {/* Right-hand column in DOM order so the stacked (<1024) reading order
            stays cards → trend → faceplate; `lg:order-first` on the rail is what
            puts the faceplate on the left once the row exists. */}
        <div className="flex min-w-0 flex-col max-lg:shrink-0 lg:min-h-0 lg:flex-1 lg:overflow-hidden">
          <section
            aria-label="Malhas"
            className={cn(
              'relative shrink-0 border-b border-rule',
              'after:pointer-events-none after:absolute after:inset-y-0 after:right-0 after:w-8',
              'after:bg-[linear-gradient(to_right,transparent,var(--bg))]',
            )}
          >
            {newLoopButton !== null ? (
              <div className="flex justify-end px-3 pt-2">{newLoopButton}</div>
            ) : null}
            <ul className="flex flex-nowrap gap-3 overflow-x-auto p-3">
              {controllers.data.map((controller) => {
                const status = statuses.get(controller.id) ?? null;
                const selectedHere = controller.id === selected.id;
                return (
                  <li
                    key={controller.id}
                    className={cn('flex', selectedHere && 'outline outline-2 outline-focus-ring')}
                  >
                    <LoopCard
                      controller={controller}
                      status={status}
                      onOpenConfig={setConfigId}
                      stale={stale}
                      controlsSlot={
                        <div className="flex flex-col gap-2">
                          <Button
                            variant="secondary"
                            size="sm"
                            aria-label={`Abrir ${controller.name}`}
                            aria-pressed={selectedHere}
                            onClick={() => setSelectedId(controller.id)}
                          >
                            Abrir
                          </Button>
                          {/* Only the open loop carries the mode switch: the strip
                              must not offer the same command on every card. */}
                          {selectedHere ? (
                            <CardControls
                              controllerId={controller.id}
                              mode={status?.mode ?? controller.mode}
                              controls={['mode']}
                            />
                          ) : null}
                        </div>
                      }
                    />
                  </li>
                );
              })}
            </ul>
          </section>

          <TrendPanel controllerId={selected.id} scale={pvScale(selected)} />
        </div>

        <Faceplate
          controllerId={selected.id}
          tag={selected.name}
          description={selected.description}
          scale={pvScale(selected)}
          spRange={{ min: selected.sp_lo_lim, max: selected.sp_hi_lim }}
        />
      </div>

      <AlarmFooterBar />

      {configTarget !== null ? (
        <LoopConfigDialog
          key={configTarget.id}
          controller={configTarget}
          open
          onClose={() => setConfigId(null)}
        />
      ) : null}
      {newLoopDialog}
    </div>
  );
}
