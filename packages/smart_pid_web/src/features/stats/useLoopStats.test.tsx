import type { ReactNode } from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { queryKeys } from '@/api/queryKeys';
import type { StatsResponse } from '@/api/types';
import type { AnyEnvelope, StatsData } from '@/lib/envelope';
import { createFakeRealtime, createQueryClient, TestProviders } from '@/test/providers';
import { useLoopStats } from './useLoopStats';

/**
 * `useLoopStats` shares `queryKeys.allStats` and `useRealtimeStats()` with
 * `multitrend/useStats` (§ contract) — these tests prove the overlay behaves
 * the same way while keeping every metric field, not the 9-field `StatsRow`.
 */

const BASE_METRICS: StatsData = {
  iae: 1,
  ise: 2,
  itae: 3,
  mse: 4,
  std_dev: 5,
  total_variation: 6,
  variability_range: 0.1,
  variability_sp: 0.2,
  sample_count: 100,
  mean_abs_error: 0,
  osc: 0,
  osc_period_s: 0,
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

function restRow(controllerId: number, overrides: Partial<StatsResponse> = {}): StatsResponse {
  return { ...BASE_METRICS, controller_id: controllerId, ...overrides };
}

function statsEnvelope(loopId: number, data: Partial<StatsData>): AnyEnvelope {
  return { type: 'stats', loop_id: loopId, seq: 1, ts: 1, data: { ...BASE_METRICS, ...data } };
}

function setup(queryClient = createQueryClient()) {
  const realtime = createFakeRealtime();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <TestProviders queryClient={queryClient} realtime={realtime.value}>
      {children}
    </TestProviders>
  );
  return { realtime, queryClient, ...renderHook(() => useLoopStats(), { wrapper }) };
}

const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock);
  fetchMock.mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => [restRow(1, { iae: 9 }), restRow(2, { iae: 1 })],
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
});

describe('useLoopStats', () => {
  it('polls the canonical /controllers/stats roster', async () => {
    const { result } = setup();
    await waitFor(() => expect(result.current.rows).toHaveLength(2));
    expect(fetchMock).toHaveBeenCalledWith('/api/controllers/stats', expect.anything());
  });

  it('carries every StatsResponse metric field, keyed by controllerId (not controller_id)', async () => {
    const { result } = setup();
    await waitFor(() => expect(result.current.rows).toHaveLength(2));
    const row = result.current.rows.find((r) => r.controllerId === 1);
    expect(row).toMatchObject({
      controllerId: 1,
      iae: 9,
      mean_abs_error: 0,
      osc_sample_count: 0,
      sp_pk_pk: 0,
      overshoot: 0,
      tv_per_sample: 0,
    });
    expect(row).not.toHaveProperty('controller_id');
  });

  it('lets a live STATS frame supersede the polled row for that loop', async () => {
    const { realtime, result } = setup();
    await waitFor(() => expect(result.current.rows).toHaveLength(2));

    act(() => realtime.emit(statsEnvelope(1, { iae: 42, mean_abs_error: 7 })));

    const updated = result.current.rows.find((r) => r.controllerId === 1);
    expect(updated).toMatchObject({ iae: 42, mean_abs_error: 7 });
    // The untouched loop keeps its REST values.
    const other = result.current.rows.find((r) => r.controllerId === 2);
    expect(other).toMatchObject({ iae: 1 });
  });

  it('dedupes with multitrend useStats via the shared queryKeys.allStats entry', async () => {
    const queryClient = createQueryClient();
    queryClient.setQueryData(queryKeys.allStats, [restRow(3, { iae: 5 })]);

    const { result } = setup(queryClient);
    await waitFor(() => expect(result.current.rows).toHaveLength(1));

    expect(result.current.rows[0]).toMatchObject({ controllerId: 3, iae: 5 });
    // staleTime: Infinity on the shared test QueryClient means a preseeded
    // cache entry (as multitrend's poll would leave behind) never triggers
    // a second fetch — proof the two pages ride the same query.
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
