import type { ReactNode } from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { StatsResponse } from '@/api/types';
import type { AnyEnvelope, StatsData } from '@/lib/envelope';
import { createFakeRealtime, createQueryClient, TestProviders } from '@/test/providers';
import { useStats } from './useStats';

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
  overshoot: 0,
  pk_pk_error: 0,
  recent_pk_pk_error: 0,
  recent_reversals: 0,
  reversals: 0,
  tv_per_sample: 0,
  zero_crossings: 0,
};

function restRow(controllerId: number, iae: number): StatsResponse {
  return { ...BASE_METRICS, controller_id: controllerId, iae };
}

function statsEnvelope(loopId: number, data: Partial<StatsData>): AnyEnvelope {
  return { type: 'stats', loop_id: loopId, seq: 1, ts: 1, data: { ...BASE_METRICS, ...data } };
}

function setup() {
  const realtime = createFakeRealtime();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <TestProviders queryClient={createQueryClient()} realtime={realtime.value}>
      {children}
    </TestProviders>
  );
  return { realtime, ...renderHook(() => useStats(), { wrapper }) };
}

const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock);
  fetchMock.mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => [restRow(2, 1), restRow(1, 9)],
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
});

describe('useStats', () => {
  it('polls the whole-plant stats roster and sorts it by loop', async () => {
    const { result } = setup();
    await waitFor(() => expect(result.current.rows).toHaveLength(2));
    expect(fetchMock).toHaveBeenCalledWith('/api/controllers/stats', expect.anything());
    expect(result.current.loops).toEqual([1, 2]);
    expect(result.current.rows[0]).toMatchObject({ loopId: 1, iae: 9 });
  });

  it('lets a live STATS frame supersede the polled row for that loop', async () => {
    const { realtime, result } = setup();
    await waitFor(() => expect(result.current.rows).toHaveLength(2));

    act(() => realtime.emit(statsEnvelope(1, { iae: 42, std_dev: 7 })));

    expect(result.current.rows[0]).toMatchObject({ loopId: 1, iae: 42, sigma: 7 });
    // The untouched loop keeps its REST values.
    expect(result.current.rows[1]).toMatchObject({ loopId: 2, iae: 1 });
  });

  it('adds a loop that only the live bus knows about', async () => {
    const { realtime, result } = setup();
    await waitFor(() => expect(result.current.rows).toHaveLength(2));
    act(() => realtime.emit(statsEnvelope(5, { iae: 3 })));
    expect(result.current.loops).toEqual([1, 2, 5]);
  });
});
