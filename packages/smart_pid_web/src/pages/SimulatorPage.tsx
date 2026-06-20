import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { AppShell } from '../components/shell/AppShell';
import { RealtimeTrend } from '../components/RealtimeTrend';
import { SimulationModeBanner } from '../features/simulator/SimulationModeBanner';
import { SimulatorControlPanel } from '../features/simulator/SimulatorControlPanel';
import { useSimulatorStatus } from '../features/simulator/useSimulatorStatus';
import { useTwinTrend } from '../features/simulator/twinTrend';

interface OpcuaStatus {
  state: string;
  endpoint: string | null;
}

export function SimulatorPage(): JSX.Element {
  // OPC status is POLLED via REST (same pattern as DashboardPage/MultiTrendPage).
  const opcua = useQuery({
    queryKey: ['opcua-status'],
    queryFn: () => apiGet<OpcuaStatus>('/opcua/status'),
    refetchInterval: 5_000,
  });
  const opcDown = opcua.data ? opcua.data.state !== 'ONLINE' : false;

  const { data } = useSimulatorStatus();
  const ids = data
    ? Object.keys(data.controllers)
        .map(Number)
        .sort((a, b) => a - b)
    : [];
  const [selected, setSelected] = useState<number | null>(null);
  const controllerId = selected ?? ids[0] ?? null;
  const trend = useTwinTrend(controllerId);

  return (
    <AppShell opcDown={opcDown}>
      <SimulationModeBanner />
      <div className="grid grid-cols-12 gap-4 items-start">
        <div className="col-span-12 [@media(min-width:960px)]:col-span-4 flex flex-col gap-4 min-w-0">
          {ids.length > 1 && (
            <label className="flex flex-col gap-1">
              <span>Loop</span>
              <select
                className="bg-surface text-text border border-border rounded-control px-2 py-1"
                style={{ fontSize: 'var(--text-sm)' }}
                aria-label="Simulator loop"
                value={controllerId ?? ''}
                onChange={(e) => setSelected(Number(e.target.value))}
              >
                {ids.map((id) => (
                  <option key={id} value={id}>
                    {id}
                  </option>
                ))}
              </select>
            </label>
          )}
          {controllerId != null ? (
            <SimulatorControlPanel controllerId={controllerId} />
          ) : (
            <p className="text-text-secondary">
              No simulator loops available. Start the simulator to begin.
            </p>
          )}
        </div>
        <section
          className="col-span-12 [@media(min-width:960px)]:col-span-8 flex flex-col gap-3 min-w-0 border border-border rounded-card bg-surface-container p-4"
          aria-label="Twin response trend"
        >
          <RealtimeTrend data={trend} />
        </section>
      </div>
    </AppShell>
  );
}
