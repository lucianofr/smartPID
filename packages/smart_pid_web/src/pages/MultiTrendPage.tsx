import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { AppShell } from '../components/shell/AppShell';
import { useMultiTrendModel } from '../features/multitrend/useMultiTrendModel';
import { useStats } from '../features/multitrend/useStats';
import { useHistory, type HistoryParams } from '../features/multitrend/useHistory';
import { MultiTrendChart } from '../features/multitrend/MultiTrendChart';
import { SeriesSelector } from '../features/multitrend/SeriesSelector';
import { StatsPanel } from '../features/multitrend/StatsPanel';
import { HistoryQuery } from '../features/multitrend/HistoryQuery';
import { ExportButton } from '../features/multitrend/ExportButton';
import type { SignalKey } from '../features/multitrend/types';
import './MultiTrendPage.css';

const ONE_HOUR_MS = 3_600_000;

interface OpcuaStatus {
  state: string;
  endpoint: string | null;
}

export function MultiTrendPage(): JSX.Element {
  // OPC status is POLLED via REST (same pattern as DashboardPage); never hardcode opcDown.
  const opcua = useQuery({
    queryKey: ['opcua-status'],
    queryFn: () => apiGet<OpcuaStatus>('/opcua/status'),
    refetchInterval: 5_000,
  });
  const opcDown = opcua.data ? opcua.data.state !== 'ONLINE' : false;

  const model = useMultiTrendModel();
  const { rows } = useStats();
  const [historyParams, setHistoryParams] = useState<HistoryParams | null>(null);
  const history = useHistory(historyParams);

  const loops = useMemo(() => rows.map((r) => r.loopId), [rows]);
  const [selection, setSelectionState] = useState<SignalKey[]>([]);

  const onSelectionChange = (sel: SignalKey[]): void => {
    setSelectionState(sel);
    model.setSelection(sel);
  };

  const exportLoop = selection[0]?.loopId ?? loops[0] ?? 0;
  const exportRequest = {
    controller_id: exportLoop,
    start: historyParams?.start ?? new Date(Date.now() - ONE_HOUR_MS).toISOString(),
    end: historyParams?.end ?? new Date().toISOString(),
    format: 'csv' as const,
  };

  return (
    <AppShell opcDown={opcDown}>
      <div className="multitrend-page">
        <section className="multitrend-page__trend">
          <div className="multitrend-page__trend-toolbar">
            <button type="button" onClick={() => model.setPaused(!model.paused)}>
              {model.paused ? 'Resume' : 'Pause'}
            </button>
          </div>
          <div className="multitrend-page__chart">
            <MultiTrendChart series={model.series} onPxWidth={model.setPxWidth} />
          </div>
        </section>

        <aside className="multitrend-page__side">
          <SeriesSelector loops={loops} selected={selection} onChange={onSelectionChange} />
          <StatsPanel rows={rows} />
          <HistoryQuery
            controllerId={exportLoop}
            onQuery={setHistoryParams}
            frames={history.frames}
            count={history.count}
            isLoading={history.isLoading}
          />
          <ExportButton request={exportRequest} />
        </aside>
      </div>
    </AppShell>
  );
}
