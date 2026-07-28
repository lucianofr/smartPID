import { useState } from 'react';
import { useCan } from '@/auth/useCan';
import { EmptyState } from '@/components/MissingState';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/Tabs';
import { AlarmConfigForm } from '@/features/alarms/AlarmConfigForm';
import { AlarmHistory } from '@/features/alarms/AlarmHistory';
import { AlarmPanel } from '@/features/alarms/AlarmPanel';
import { AlarmFooterBar } from '@/features/dashboard/AlarmFooterBar';
import { useControllers } from '@/features/dashboard/useControllers';
import { cn } from '@/lib/utils';

/**
 * Alarm workspace (§6.4). `Ativos` is the default view — the page an operator
 * lands on must be the one that demands action.
 *
 * The persistent §6.9 footer stays mounted here too: it is the plant-wide
 * summary, so navigating INTO the alarm page must not be the one place it
 * disappears.
 */

const SELECT_CLASS = cn(
  'min-h-11 rounded-control border border-rule-strong bg-surface-sunk px-2 text-sm text-text',
  'outline-none focus-visible:ring-2 focus-visible:ring-focus-ring',
);

function AlarmConfigSection() {
  const controllers = useControllers();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const loops = controllers.data ?? [];
  const controllerId = loops.find((c) => c.id === selectedId)?.id ?? loops[0]?.id;

  if (controllerId === undefined) {
    return <EmptyState message="Nenhuma malha configurada." hint="Cadastre um controlador." />;
  }
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <label className="flex w-56 flex-col gap-1 px-3 pt-2 text-2xs text-text-soft">
        Malha
        <select
          className={SELECT_CLASS}
          value={controllerId}
          onChange={(e) => setSelectedId(Number(e.target.value))}
        >
          {loops.map((loop) => (
            <option key={loop.id} value={loop.id}>
              {loop.name}
            </option>
          ))}
        </select>
      </label>
      <AlarmConfigForm key={controllerId} controllerId={controllerId} />
    </div>
  );
}

export function AlarmsPage() {
  const canConfigure = useCan('alarms.configure');
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <Tabs defaultValue="active" className="flex min-h-0 flex-1 flex-col">
        <TabsList className="shrink-0 px-3">
          <TabsTrigger value="active">Ativos</TabsTrigger>
          <TabsTrigger value="history">Histórico</TabsTrigger>
          {canConfigure ? <TabsTrigger value="config">Configuração</TabsTrigger> : null}
        </TabsList>
        <TabsContent value="active" className="flex min-h-0 flex-1 flex-col pt-0">
          <AlarmPanel />
        </TabsContent>
        <TabsContent value="history" className="flex min-h-0 flex-1 flex-col pt-0">
          <AlarmHistory />
        </TabsContent>
        {canConfigure ? (
          <TabsContent value="config" className="flex min-h-0 flex-1 flex-col pt-0">
            <AlarmConfigSection />
          </TabsContent>
        ) : null}
      </Tabs>
      <AlarmFooterBar />
    </div>
  );
}
