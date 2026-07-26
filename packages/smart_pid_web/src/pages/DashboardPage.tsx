import { EmptyState, ErrorState, LoadingState } from '@/components/MissingState';
import { useControllers } from '@/features/dashboard/useControllers';

export function DashboardPage() {
  const controllers = useControllers();

  if (controllers.isPending) {
    return <LoadingState label="Carregando malhas…" />;
  }
  if (controllers.isError) {
    return (
      <ErrorState message="Não foi possível carregar as malhas." onRetry={() => void controllers.refetch()} />
    );
  }
  if (controllers.data.length === 0) {
    return <EmptyState message="Nenhuma malha configurada." hint="Cadastre um controlador para começar." />;
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <ul className="flex flex-nowrap gap-3 overflow-x-auto p-3">
        {controllers.data.map((c) => (
          <li key={c.id} className="numeric shrink-0 text-sm">
            {c.name}
          </li>
        ))}
      </ul>
    </div>
  );
}
