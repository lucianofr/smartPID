import { Legend } from '@/components/Legend';
import { EmptyState, ErrorState, LoadingState } from '@/components/MissingState';
import { useControllers } from '@/features/dashboard/useControllers';
import { useLoopStatuses } from '@/features/dashboard/useLoopStatuses';
import { LoopStatsCard } from '@/features/stats/LoopStatsCard';
import { statsLegendGroups } from '@/features/stats/statsLegend';
import { useLoopStats } from '@/features/stats/useLoopStats';

/**
 * Stats screen (§6.8) — one card per configured loop with every computed
 * indicator plus the live block mode / AI engine / execution mode badges.
 * The controller roster is REST truth (`GET /controllers`); a loop with no
 * stats worker still gets a card (LoopStatsCard's own empty note), so the
 * roster — not the stats query — gates the page's own loading/error/empty
 * states.
 */
export function StatsPage() {
  const controllers = useControllers();
  const stats = useLoopStats();
  const statuses = useLoopStatuses();

  if (controllers.isPending) {
    return <LoadingState label="Carregando malhas…" />;
  }
  if (controllers.isError) {
    return (
      <ErrorState
        message="Falha ao carregar malhas."
        onRetry={() => void controllers.refetch()}
      />
    );
  }
  if (controllers.data.length === 0) {
    return <EmptyState message="Nenhuma malha configurada." />;
  }
  if (stats.isPending) {
    return <LoadingState label="Carregando estatísticas…" />;
  }
  if (stats.isError) {
    return <ErrorState message="Falha ao carregar estatísticas." onRetry={stats.refetch} />;
  }

  const rowsByLoop = new Map(stats.rows.map((row) => [row.controllerId, row]));

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto p-4">
      <h1 className="mb-3 text-sm font-medium text-text">Estatísticas</h1>
      <section
        aria-label="Estatísticas das malhas"
        className="grid grid-cols-1 gap-3.5 md:grid-cols-2 xl:grid-cols-3"
      >
        {controllers.data.map((controller) => (
          <LoopStatsCard
            key={controller.id}
            controller={controller}
            statsRow={rowsByLoop.get(controller.id)}
            status={statuses.get(controller.id)}
          />
        ))}
        <Legend groups={statsLegendGroups()} className="col-span-full" />
      </section>
    </div>
  );
}
