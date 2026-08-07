import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Button } from '@/components/Button';
import { EmptyState, ErrorState, LoadingState } from '@/components/MissingState';
import { AlarmFooterBar } from '@/features/dashboard/AlarmFooterBar';
import { Faceplate } from '@/features/dashboard/Faceplate';
import { KpiBand } from '@/features/dashboard/KpiBand';
import { activeAiStrategy, LoopCard } from '@/features/dashboard/LoopCard';
import { TrendPanel } from '@/features/dashboard/TrendPanel';
import { coScale, pvScale, useControllers } from '@/features/dashboard/useControllers';
import { useLoopAlarmSeverity } from '@/features/dashboard/useAlarmCounts';
import { useLoopStatuses } from '@/features/dashboard/useLoopStatuses';
import { LoopConfigDialog, NewLoopDialog } from '@/features/loop-config/LoopConfigDialog';
import { FeedbackBanner } from '@/features/feedback/FeedbackBanner';
import { SimulationModeBanner } from '@/features/simulator/SimulationModeBanner';
import { useTwinRunning } from '@/features/simulator/useSimulatorStatus';
import { useCan } from '@/auth/useCan';
import { useConnectionStatus } from '@/realtime/useConnectionStatus';
import { cn } from '@/lib/utils';

/** KPI figures this page cannot source without adding a poll. */
const UNAVAILABLE = '—';

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
 *
 * The KPI band sits between the page-level banners and the rail. Its two
 * roster-derived figures are exact; variability and savings are em dashes here
 * because the only sources for them are `GET /controllers/stats` and the AI
 * tuning log, and the operational page must not take on two extra polls to
 * decorate a header. The executive dashboard already owns those numbers.
 */
export function DashboardPage() {
  const controllers = useControllers();
  const statuses = useLoopStatuses();
  const alarmSeverity = useLoopAlarmSeverity();
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
  const loopCount = controllers.data.length;
  const aiActive = controllers.data.filter((c) => activeAiStrategy(c) !== null).length;

  if (loopCount === 0) {
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        {/* Zeros are the honest reading of an empty roster — dropping the band
            here would make the page jump the moment the first loop lands. */}
        <KpiBand loops={0} aiActive={0} variability={UNAVAILABLE} savings={UNAVAILABLE} />
        <FeedbackBanner />
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
      {/* Below the simulation banner on purpose: a "these numbers come from a
          model" warning outranks a summary band. */}
      <KpiBand
        loops={loopCount}
        aiActive={aiActive}
        variability={UNAVAILABLE}
        savings={UNAVAILABLE}
      />
      {/* Demo-account only, and below the KPI band: an invitation to write to
          the developer must never outrank the operational readings. */}
      <FeedbackBanner />
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
              // px-1.5 + the list's own p-3.5 puts the first card 20px off the
              // column edge (the mock's `p-5`) while the scroller itself still
              // runs to the very edge, so a clipped card keeps hinting at more.
              'relative shrink-0 border-b border-rule px-1.5 pt-4',
              'after:pointer-events-none after:absolute after:inset-y-0 after:right-0 after:w-8',
              'after:bg-[linear-gradient(to_right,transparent,var(--bg))]',
            )}
          >
            <div className="flex items-center justify-between gap-3 px-3.5">
              <h2 className="type-display text-base font-semibold text-text">Malhas PID</h2>
              {newLoopButton}
            </div>
            <ul className="flex flex-nowrap gap-3.5 overflow-x-auto p-3.5">
              {controllers.data.map((controller) => {
                const status = statuses.get(controller.id) ?? null;
                return (
                  // The selection treatment lives on the card (border + lifted
                  // shadow), not on this wrapper: an outline drawn out here sat
                  // outside the card's radius and read as a second frame.
                  <li key={controller.id} className="flex shrink-0">
                    <LoopCard
                      controller={controller}
                      status={status}
                      onOpenConfig={setConfigId}
                      onSelect={setSelectedId}
                      stale={stale}
                      selected={controller.id === selected.id}
                      alarmSeverity={alarmSeverity.get(controller.id) ?? null}
                    />
                  </li>
                );
              })}
            </ul>
          </section>

          {/* Same 20px gutter as the rail so the plot lines up with the cards
              instead of running into the viewport edge. */}
          <div className="flex min-w-0 flex-col px-5 pb-4 max-lg:shrink-0 lg:min-h-0 lg:flex-1">
            <TrendPanel controllerId={selected.id} scale={pvScale(selected)} />
          </div>
        </div>

        <Faceplate
          controllerId={selected.id}
          tag={selected.name}
          description={selected.description}
          scale={pvScale(selected)}
          coScale={coScale(selected)}
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
