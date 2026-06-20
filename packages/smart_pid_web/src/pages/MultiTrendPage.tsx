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
      {/* Bento layout (design-system §10): trend ~8 cols, side ~4 cols; single-column
          stack below 960px. Flat token utilities only — no hardcoded palette. */}
      <div className="grid grid-cols-12 gap-4 items-start">
        <section className="col-span-12 [@media(min-width:960px)]:col-span-8 flex flex-col gap-3 min-w-0 border border-border rounded-card bg-surface-container p-4">
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => model.setPaused(!model.paused)}>
              {model.paused ? 'Resume' : 'Pause'}
            </button>
          </div>
          <div className="w-full min-w-0 h-[clamp(280px,48vh,540px)]">
            <MultiTrendChart series={model.series} onPxWidth={model.setPxWidth} />
          </div>
        </section>

        <aside className="col-span-12 [@media(min-width:960px)]:col-span-4 flex flex-col gap-4 min-w-0">
          <SeriesSelector loops={loops} selected={selection} onChange={onSelectionChange} />
          <StatsPanel rows={rows} />
          <HistoryQuery
            controllerId={exportLoop}
            onQuery={setHistoryParams}
            frames={history.frames}
            count={history.count}
            isLoading={history.isLoading}
            hasQueried={historyParams !== null}
          />
          <ExportButton request={exportRequest} />
        </aside>
      </div>
    </AppShell>
  );
}
