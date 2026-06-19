import { useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useRealtime } from '../realtime/useRealtime';
import { periodRange, type PeriodKey } from '../lib/period';
import {
  fromRestStats,
  fromWsStats,
  aggregate,
  formatKpi,
  variabilityOutOfTarget,
  type LoopKpis,
} from '../lib/kpi';
import {
  useAiHistory,
  useAiStatus,
  useAllStats,
  useControllers,
  useOpcuaStatus,
  useTuningRecommendation,
} from '../api/executive';
import { AppShell } from '../components/shell/AppShell';
import { ExecutiveKPICard } from '../components/ExecutiveKPICard';
import { LoopHealthRow, type LoopHealth } from '../components/LoopHealthRow';
import { PeriodSelector } from '../components/PeriodSelector';
import { TuningRecommendationCard } from '../components/TuningRecommendationCard';
import './ExecutiveDashboardPage.css';

type OpcState = 'OFFLINE' | 'CONNECTING' | 'ONLINE' | 'RECONNECTING';

/** Modes are UPPERCASE. OOS/IMAN are error states; an unmonitored loop with no live
 *  frame and an empty/BYPASS mode is stopped; everything else is running. */
function healthOf(mode: string, hasLiveStatus: boolean): LoopHealth {
  if (mode === 'OOS' || mode === 'IMAN') return 'error';
  if (!hasLiveStatus && (mode === '' || mode === 'BYPASS')) return 'stopped';
  return 'running';
}

/** Per-loop AI engine + tuning recommendation. Lives as its own component so each
 *  loop gets an isolated hook scope (Rules of Hooks); calling the per-loop hooks
 *  inside a parent .map() would be a violation. */
function LoopTuningDetail({ loopId, loopName }: { loopId: number; loopName: string }) {
  const recQ = useTuningRecommendation(loopId);
  const aiQ = useAiStatus(loopId);
  return (
    <div className="exec-dash__detail" data-testid={`loop-detail-${loopId}`}>
      <span className="exec-dash__ai-engine" data-testid={`ai-engine-${loopId}`}>
        {aiQ.data?.engine ?? '—'}
      </span>
      <TuningRecommendationCard loopName={loopName} rec={recQ.data ?? null} />
    </div>
  );
}

export function ExecutiveDashboardPage(): JSX.Element {
  const [period, setPeriod] = useState<PeriodKey>('1h');
  const range = useMemo(() => periodRange(period), [period]);

  const qc = useQueryClient();
  const { lastStatus, lastStats, onResync } = useRealtime();

  const statsQ = useAllStats();
  const ctrlQ = useControllers();
  const opcQ = useOpcuaStatus();
  const aiHistoryQ = useAiHistory(range);

  useEffect(
    () =>
      onResync(() => {
        void qc.invalidateQueries({ queryKey: ['controllers'] });
        void qc.invalidateQueries({ queryKey: ['controllers', 'stats'] });
        void qc.invalidateQueries({ queryKey: ['opcua-status'] });
      }),
    [onResync, qc],
  );

  const controllers = useMemo(() => ctrlQ.data ?? [], [ctrlQ.data]);
  const opcState = (opcQ.data?.state ?? 'OFFLINE') as OpcState;
  const opcDown = opcQ.data ? opcQ.data.state !== 'ONLINE' : false;

  // Live status mode wins over the REST snapshot mode, per loop.
  const modesById = useMemo(() => {
    const m = new Map<number, string>();
    for (const c of controllers) m.set(c.id, lastStatus.get(c.id)?.mode ?? c.mode);
    return m;
  }, [controllers, lastStatus]);

  // Per-loop KPIs: REST snapshot seeded first, then the live WS frame overwrites per id.
  const loopKpis: LoopKpis[] = useMemo(() => {
    const byId = new Map<number, LoopKpis>();
    for (const r of statsQ.data ?? []) byId.set(r.controller_id, fromRestStats(r));
    for (const c of controllers) {
      const live = lastStats.get(c.id);
      if (live) byId.set(c.id, fromWsStats(c.id, live));
    }
    return [...byId.values()];
  }, [statsQ.data, controllers, lastStats]);

  const agg = useMemo(() => aggregate(loopKpis, modesById), [loopKpis, modesById]);
  const tuningEvents = aiHistoryQ.data?.length ?? 0;

  return (
    <AppShell opcDown={opcDown}>
      <main data-testid="executive-dashboard">
        <header className="exec-dash__header">
          <h1>Executive Dashboard</h1>
          <PeriodSelector value={period} onChange={setPeriod} />
        </header>

        <section
          className="exec-dash__kpis"
          aria-label="Aggregate KPIs"
          data-testid="aggregate-kpis"
        >
          <ExecutiveKPICard
            label="Loops in AUTO"
            value={formatKpi(agg.autoPct / 100, 'pct')}
            testId="kpi-auto"
          />
          <ExecutiveKPICard
            label="Avg variability 2σ/RANGE"
            value={formatKpi(agg.avgVariabilityRange, 'pct')}
            delta={{
              dir: 'up',
              value: formatKpi(agg.avgVariabilityRange, 'pct'),
              outOfTarget: variabilityOutOfTarget(agg.avgVariabilityRange),
            }}
            testId="kpi-variability"
          />
          <ExecutiveKPICard
            label="Total valve travel (TV)"
            value={formatKpi(agg.totalTv, 'index')}
            testId="kpi-tv"
          />
          <ExecutiveKPICard
            label="Avg IAE"
            value={formatKpi(agg.avgIae, 'index')}
            testId="kpi-iae"
          />
          <ExecutiveKPICard
            label="Loops"
            value={formatKpi(agg.loopCount, 'count')}
            testId="kpi-loops"
          />
        </section>

        <section className="exec-dash__health" aria-label="Loop health" data-testid="loop-health">
          {controllers.map((c) => {
            const live = lastStatus.get(c.id);
            const mode = live?.mode ?? c.mode;
            return (
              <LoopHealthRow
                key={c.id}
                name={c.name}
                mode={mode}
                health={healthOf(mode, live != null)}
                opc={opcState}
              />
            );
          })}
        </section>

        <section
          className="exec-dash__tuning"
          aria-label="Per-loop tuning"
          data-testid="loop-tuning"
        >
          <p data-testid="tuning-events-count">{tuningEvents} tuning events in period</p>
          {controllers.map((c) => (
            <LoopTuningDetail key={c.id} loopId={c.id} loopName={c.name} />
          ))}
        </section>
      </main>
    </AppShell>
  );
}
