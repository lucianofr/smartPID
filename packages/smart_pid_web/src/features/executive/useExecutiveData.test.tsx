import type { ReactNode } from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { AiTuningLogRow } from '@/api/types';
import type { AnyEnvelope, StatsData } from '@/lib/envelope';
import { createFakeRealtime, createQueryClient, TestProviders } from '@/test/providers';
import {
  aggregate,
  aiRoi,
  healthOf,
  rankBadActors,
  variabilityOutOfTarget,
  type ExecutiveLoop,
} from './types';
import { useExecutiveData } from './useExecutiveData';

const METRICS: StatsData = {
  iae: 1,
  ise: 2,
  itae: 3,
  mse: 4,
  std_dev: 5,
  total_variation: 6,
  variability_range: 0.02,
  variability_sp: 0.03,
  sample_count: 100,
  mean_abs_error: 0,
  osc: 0,
  osc_sample_count: 0,
  overshoot: 0,
  pk_pk_error: 0,
  recent_pk_pk_error: 0,
  recent_reversals: 0,
  reversals: 0,
  sp_pk_pk: 0,
  tv_per_sample: 0,
  zero_crossings: 0,
};

function controller(id: number, name: string, mode: string, ai: boolean) {
  return {
    id,
    name,
    mode,
    description: '',
    optimization_enabled: ai,
    ai_config: { engine: ai ? 'FUZZY' : 'NONE' },
  };
}

function badActor(loopId: number, iae: number | null, variabilityRange: number | null): ExecutiveLoop {
  return { loopId, name: `L${loopId}`, mode: 'AUTO', ai: false, iae, variabilityRange, health: 'running' };
}

function tuning(controllerId: number, timestamp: string, metric: number | null): AiTuningLogRow {
  return {
    id: 0,
    controller_id: controllerId,
    controller_name: null,
    timestamp,
    engine: 'FUZZY',
    ki_before: 1,
    ki_after: 2,
    objective: 'SP_TRACKING',
    metric,
  };
}

function statsEnvelope(loopId: number, data: Partial<StatsData>): AnyEnvelope {
  return { type: 'stats', loop_id: loopId, seq: 1, ts: 1, data: { ...METRICS, ...data } };
}

/** Route the mocked fetch by path — the hook fans out over five endpoints. */
const fetchMock = vi.fn();

function respond(body: unknown) {
  return { ok: true, status: 200, json: async () => body };
}

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock);
  fetchMock.mockImplementation((path: string) => {
    if (path.startsWith('/api/controllers/stats')) {
      return Promise.resolve(respond([{ ...METRICS, controller_id: 1, iae: 10 }]));
    }
    if (path.startsWith('/api/controllers')) {
      return Promise.resolve(
        respond([controller(1, 'FIC-101', 'AUTO', true), controller(2, 'TIC-202', 'MAN', false)]),
      );
    }
    if (path.startsWith('/api/opcua/status')) {
      return Promise.resolve(respond({ state: 'ONLINE', endpoint: 'opc.tcp://x' }));
    }
    if (path.startsWith('/api/system/status')) {
      return Promise.resolve(
        respond({
          status: 'running',
          uptime_s: 3661,
          active_controllers: 2,
          bus_active: true,
          api_version: '2.0.0',
        }),
      );
    }
    if (path.startsWith('/api/alarms/ai-history')) {
      return Promise.resolve(
        respond([tuning(1, '2026-01-01T00:00:00Z', 8), tuning(1, '2026-01-01T01:00:00Z', 2)]),
      );
    }
    return Promise.reject(new Error(`unstubbed ${path}`));
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
});

function setup() {
  const realtime = createFakeRealtime();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <TestProviders queryClient={createQueryClient()} realtime={realtime.value}>
      {children}
    </TestProviders>
  );
  return { realtime, ...renderHook(() => useExecutiveData('24h'), { wrapper }) };
}

describe('aggregate', () => {
  it('rolls AUTO share, AI coverage and the mean error index over the roster', () => {
    expect(
      aggregate([
        { mode: 'AUTO', ai: true, iae: 10 },
        { mode: 'MAN', ai: false, iae: 20 },
      ]),
    ).toMatchObject({ autoPercent: 50, aiCoveragePercent: 50, averageIae: 15 });
  });

  it('counts cascade slaves as automatic', () => {
    expect(aggregate([{ mode: 'CAS', ai: false }, { mode: 'RCAS', ai: false }]).autoPercent).toBe(100);
  });

  it('reports an unmeasured metric as absent instead of zero', () => {
    const kpis = aggregate([{ mode: 'AUTO', ai: true }]);
    expect(kpis).toMatchObject({ averageIae: null, averageVariabilityRange: null, totalTv: null });
    expect(kpis.autoPercent).toBe(100);
  });

  it('keeps a loop without stats out of the averages but inside the percentages', () => {
    const kpis = aggregate([
      { mode: 'AUTO', ai: true, iae: 10, variabilityRange: 0.02, tv: 3 },
      { mode: 'MAN', ai: false },
    ]);
    expect(kpis).toMatchObject({ averageIae: 10, averageVariabilityRange: 0.02, totalTv: 3 });
    expect(kpis.autoPercent).toBe(50);
  });

  it('has no loops, no percentages', () => {
    expect(aggregate([])).toMatchObject({ loopCount: 0, autoPercent: 0, aiCoveragePercent: 0 });
  });
});

describe('rankBadActors', () => {
  it('ranks by IAE descending, breaking ties on variability', () => {
    const ranked = rankBadActors([
      badActor(1, 5, 0.01),
      badActor(2, 9, 0.01),
      badActor(3, 9, 0.08),
    ]);
    expect(ranked.map((l) => l.loopId)).toEqual([3, 2, 1]);
  });

  it('drops loops that reported no index at all', () => {
    expect(rankBadActors([badActor(1, null, null), badActor(2, 3, null)]).map((l) => l.loopId)).toEqual([2]);
  });

  it('caps the table so the buyer reads a short list', () => {
    const many = Array.from({ length: 9 }, (_, i) => badActor(i + 1, i + 1, 0.01));
    expect(rankBadActors(many)).toHaveLength(5);
    expect(rankBadActors(many, 2).map((l) => l.loopId)).toEqual([9, 8]);
  });
});

describe('variabilityOutOfTarget', () => {
  it('trips only above 5 % of range', () => {
    expect(variabilityOutOfTarget(0.05)).toBe(false);
    expect(variabilityOutOfTarget(0.051)).toBe(true);
    expect(variabilityOutOfTarget(null)).toBe(false);
  });
});

describe('healthOf', () => {
  it('treats the block fault states as errors', () => {
    expect(healthOf('OOS', true)).toBe('error');
    expect(healthOf('IMAN', false)).toBe('error');
  });

  it('calls a silent, mode-less loop stopped and anything else running', () => {
    expect(healthOf('', false)).toBe('stopped');
    expect(healthOf('BYPASS', false)).toBe('stopped');
    expect(healthOf('BYPASS', true)).toBe('running');
    expect(healthOf('MAN', false)).toBe('running');
  });
});

describe('aiRoi', () => {
  it('compares the first and last scored tuning of each loop', () => {
    const roi = aiRoi([
      tuning(1, '2026-01-01T00:00:00Z', 8),
      tuning(1, '2026-01-01T02:00:00Z', 2),
      tuning(2, '2026-01-01T01:00:00Z', 4),
      tuning(2, '2026-01-01T03:00:00Z', 2),
    ]);
    expect(roi).toMatchObject({ loopsCompared: 2, metricBefore: 6, metricAfter: 2, tuningEvents: 4 });
    expect(roi?.improvement).toBeCloseTo(2 / 3);
  });

  it('refuses to invent a comparison from a single tuning', () => {
    expect(aiRoi([tuning(1, '2026-01-01T00:00:00Z', 8)])).toBeNull();
    expect(aiRoi([])).toBeNull();
  });

  it('ignores unscored rows and a zero baseline', () => {
    expect(aiRoi([tuning(1, '2026-01-01T00:00:00Z', null), tuning(1, '2026-01-01T01:00:00Z', 5)])).toBeNull();
    expect(aiRoi([tuning(1, '2026-01-01T00:00:00Z', 0), tuning(1, '2026-01-01T01:00:00Z', 0)])).toBeNull();
  });
});

describe('useExecutiveData', () => {
  it('seeds the roster, the metrics, OPC and backend health from REST', async () => {
    const { result } = setup();
    await waitFor(() => expect(result.current.loops).toHaveLength(2));

    expect(result.current.kpis).toMatchObject({
      loopCount: 2,
      autoPercent: 50,
      aiCoveragePercent: 50,
      averageIae: 10,
    });
    expect(result.current.opc).toBe('ONLINE');
    expect(result.current.health.uptime_s).toBe(3661);
    expect(result.current.loops[0]).toMatchObject({ loopId: 1, name: 'FIC-101', health: 'running' });
  });

  it('overlays a live stats frame without mutating the cached REST rows', async () => {
    const { realtime, result } = setup();
    await waitFor(() => expect(result.current.kpis.averageIae).toBe(10));

    act(() => realtime.emit(statsEnvelope(1, { iae: 40 })));

    expect(result.current.kpis.averageIae).toBe(40);
    // The REST snapshot behind it is untouched — a refetch would still say 10.
    const rest = fetchMock.mock.calls.filter((c: unknown[]) => String(c[0]).includes('/controllers/stats'));
    expect(rest.length).toBeGreaterThan(0);
  });

  it('scores the bad actors from the same overlay', async () => {
    const { realtime, result } = setup();
    await waitFor(() => expect(result.current.loops).toHaveLength(2));
    act(() => realtime.emit(statsEnvelope(2, { iae: 99, variability_range: 0.4 })));

    expect(result.current.badActors.map((l) => l.loopId)).toEqual([2, 1]);
  });

  it('derives AI ROI from the tuning window', async () => {
    const { result } = setup();
    await waitFor(() => expect(result.current.roi).not.toBeNull());
    expect(result.current.roi).toMatchObject({ metricBefore: 8, metricAfter: 2, loopsCompared: 1 });
    expect(result.current.tuningEvents).toBe(2);
  });
});
