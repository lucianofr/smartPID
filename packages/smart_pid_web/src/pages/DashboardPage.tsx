import { useState } from 'react';
import { Button } from '@/components/Button';
import { EmptyState, ErrorState, LoadingState } from '@/components/MissingState';
import { LoopCard } from '@/features/dashboard/LoopCard';
import { useControllers } from '@/features/dashboard/useControllers';
import { useLoopStatuses } from '@/features/dashboard/useLoopStatuses';
import { cn } from '@/lib/utils';

/**
 * Operational dashboard (§6.9): a single non-wrapping card strip over the trend
 * and faceplate. Wrapping is forbidden — it pushes the trend below the fold.
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
      <EmptyState
        message="Nenhuma malha configurada."
        hint="Cadastre um controlador para começar."
      />
    );
  }

  const selected =
    controllers.data.find((c) => c.id === selectedId) ?? controllers.data[0];

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
    </div>
  );
}
