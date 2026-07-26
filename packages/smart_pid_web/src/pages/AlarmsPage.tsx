import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/Tabs';
import { AlarmHistory } from '@/features/alarms/AlarmHistory';
import { AlarmPanel } from '@/features/alarms/AlarmPanel';
import { AlarmFooterBar } from '@/features/dashboard/AlarmFooterBar';

/**
 * Alarm workspace (§6.4). `Ativos` is the default view — the page an operator
 * lands on must be the one that demands action.
 *
 * The persistent §6.9 footer stays mounted here too: it is the plant-wide
 * summary, so navigating INTO the alarm page must not be the one place it
 * disappears.
 */
export function AlarmsPage() {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <Tabs defaultValue="active" className="flex min-h-0 flex-1 flex-col">
        <TabsList className="shrink-0 px-3">
          <TabsTrigger value="active">Ativos</TabsTrigger>
          <TabsTrigger value="history">Histórico</TabsTrigger>
        </TabsList>
        <TabsContent value="active" className="flex min-h-0 flex-1 flex-col pt-0">
          <AlarmPanel />
        </TabsContent>
        <TabsContent value="history" className="flex min-h-0 flex-1 flex-col pt-0">
          <AlarmHistory />
        </TabsContent>
      </Tabs>
      <AlarmFooterBar />
    </div>
  );
}
