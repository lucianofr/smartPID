import { useQuery } from '@tanstack/react-query';
import { useEffect } from 'react';
import { apiGet } from '../api/client';
import { AppShell } from '../components/shell/AppShell';
import { ControllerCard, type ControllerSummary } from '../components/ControllerCard';
import { useRealtime } from '../realtime/useRealtime';

interface OpcuaStatus { state: string; endpoint: string | null; }

export function DashboardPage() {
  const { lastStatus, onResync } = useRealtime();

  const controllers = useQuery({
    queryKey: ['controllers'],
    queryFn: () => apiGet<ControllerSummary[]>('/controllers'),
  });
  const opcua = useQuery({
    queryKey: ['opcua-status'],
    queryFn: () => apiGet<OpcuaStatus>('/opcua/status'),
    refetchInterval: 5_000, // OPC status is POLLED via REST, not WS
  });

  // On WS reconnect, re-sync REST state (controllers + opcua; alarms/ai added by later fatias).
  useEffect(
    () =>
      onResync(() => {
        controllers.refetch();
        opcua.refetch();
      }),
    [onResync, controllers, opcua],
  );

  const opcDown = opcua.data ? opcua.data.state !== 'CONNECTED' : false;

  return (
    <AppShell opcDown={opcDown}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--sp-3)' }}>
        {(controllers.data ?? []).map((c) => (
          <ControllerCard key={c.id} controller={c} status={lastStatus.get(c.id)} />
        ))}
      </div>
    </AppShell>
  );
}
