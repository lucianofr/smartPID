import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { AppShell } from '../components/shell/AppShell';
import { RealtimeTrend } from '../components/RealtimeTrend';
import { SimulationModeBanner } from '../features/simulator/SimulationModeBanner';
import { SimulatorControlPanel } from '../features/simulator/SimulatorControlPanel';
import { useSimulatorStatus } from '../features/simulator/useSimulatorStatus';
import { useTwinTrend } from '../features/simulator/twinTrend';
import './SimulatorPage.css';

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
      <div className="simulator-page">
        <div className="simulator-page__controls">
          {ids.length > 1 && (
            <label className="simulator-page__loop-select">
              <span>Loop</span>
              <select
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
            <p className="simulator-page__empty">
              No simulator loops available. Start the simulator to begin.
            </p>
          )}
        </div>
        <section className="simulator-page__trend" aria-label="Twin response trend">
          <RealtimeTrend data={trend} />
        </section>
      </div>
    </AppShell>
  );
}
