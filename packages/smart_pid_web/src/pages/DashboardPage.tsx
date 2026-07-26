import { useState } from 'react';
import { Button } from '@/components/Button';
import { EmptyState, ErrorState, LoadingState } from '@/components/MissingState';
import { AlarmFooterBar } from '@/features/dashboard/AlarmFooterBar';
import { Faceplate } from '@/features/dashboard/Faceplate';
import { LoopCard } from '@/features/dashboard/LoopCard';
import { TrendPanel } from '@/features/dashboard/TrendPanel';
import { pvScale, useControllers } from '@/features/dashboard/useControllers';
import { useLoopStatuses } from '@/features/dashboard/useLoopStatuses';
import { cn } from '@/lib/utils';

/**
 * Operational dashboard (§6.9).
 *
 * Layout contract: a single non-wrapping card strip on top — wrapping would
 * push the trend below the fold — then trend + ~320 px faceplate side by side
 * at ≥1024 (trend keeps ≥65% at 1440) and stacked below it, over a persistent
 * alarm footer that collapses to a count chip under 768.
 */
export function DashboardPage() {
  const controllers = useControllers();
  const statuses = useLoopStatuses();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [, setConfigId] = useState<number | null>(null);

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
        />
        <AlarmFooterBar />
      </div>
    );
  }

  const selected = controllers.data.find((c) => c.id === selectedId) ?? controllers.data[0];

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <section
        aria-label="Malhas"
        className={cn(
          'relative shrink-0 border-b border-rule',
          'after:pointer-events-none after:absolute after:inset-y-0 after:right-0 after:w-8',
          'after:bg-[linear-gradient(to_right,transparent,var(--bg))]',
        )}
      >
        <ul className="flex flex-nowrap gap-3 overflow-x-auto p-3">
          {controllers.data.map((controller) => (
            <li
              key={controller.id}
              className={cn(
                'flex',
                controller.id === selected.id && 'outline outline-2 outline-focus-ring',
              )}
            >
              <LoopCard
                controller={controller}
                status={statuses.get(controller.id) ?? null}
                onOpenConfig={setConfigId}
                controlsSlot={
                  <Button
                    variant="secondary"
                    size="sm"
                    aria-label={`Abrir ${controller.name}`}
                    aria-pressed={controller.id === selected.id}
                    onClick={() => setSelectedId(controller.id)}
                  >
                    Abrir
                  </Button>
                }
              />
            </li>
          ))}
        </ul>
      </section>

      <div
        data-testid="dashboard-detail"
        className="flex min-h-0 flex-1 flex-col overflow-y-auto lg:flex-row lg:overflow-hidden"
      >
        <TrendPanel controllerId={selected.id} scale={pvScale(selected)} />
        <Faceplate
          controllerId={selected.id}
          tag={selected.name}
          description={selected.description}
          scale={pvScale(selected)}
        />
      </div>

      <AlarmFooterBar />
    </div>
  );
}
