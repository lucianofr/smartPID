import type { ReactNode } from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { HistoryResponse } from '@/api/types';
import { ff, statusEnvelope } from '@/test/fixtures';
import { createFakeRealtime, TestProviders } from '@/test/providers';
import { useMultiTrendModel } from './useMultiTrendModel';

const trend = vi.fn();
vi.mock('@/api/endpoints', () => ({ endpoints: { trend: (...args: unknown[]) => trend(...args) } }));

function ringFrames(controllerId: number, ...points: [number, number][]): HistoryResponse {
  return {
    controller_id: controllerId,
    count: points.length,
    frames: points.map(([epoch, pv]) => ({
      timestamp: new Date(epoch * 1000).toISOString(),
      pv,
      sp: 55,
      co: 42,
      mode: 'AUTO',
      status: 'GOOD',
    })),
  };
}

function setup(roster: readonly number[] | null = null) {
  const realtime = createFakeRealtime();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <TestProviders realtime={realtime.value}>{children}</TestProviders>
  );
  return { realtime, ...renderHook(() => useMultiTrendModel(roster), { wrapper }) };
}

beforeEach(() => {
  localStorage.clear();
  trend.mockReset();
  trend.mockResolvedValue(ringFrames(1));
});

describe('useMultiTrendModel — ring seed', () => {
  it('seeds a newly assigned slot from the ring', async () => {
    trend.mockResolvedValue(ringFrames(1, [1000, 10], [1001, 11]));
    const { result } = setup();

    act(() => result.current.assign(0, { id: 1 }));

    await waitFor(() => expect(result.current.slotSeries[0].data[0]).toEqual([1000, 1001]));
    expect(result.current.slotSeries[0].data[1]).toEqual([10, 11]);
    // The cell's window is what it advertises, not an unbounded replay.
    expect(trend).toHaveBeenCalledWith(1, 60);
  });

  it('restores a persisted layout from the ring on mount', async () => {
    trend.mockResolvedValue(ringFrames(4, [2000, 7]));
    localStorage.setItem(
      'spid.multitrend',
      JSON.stringify([
        { controllerId: 4, series: { pv: true, sp: true, co: true } },
        { controllerId: null, series: { pv: false, sp: false, co: false } },
        { controllerId: null, series: { pv: false, sp: false, co: false } },
        { controllerId: null, series: { pv: false, sp: false, co: false } },
      ]),
    );
    const { result } = setup();
    await waitFor(() => expect(result.current.slotSeries[0].data[0]).toEqual([2000]));
    expect(trend).toHaveBeenCalledWith(4, 60);
  });

  it('merges live frames with the seeded window', async () => {
    trend.mockResolvedValue(ringFrames(1, [1000, 10]));
    const { result, realtime } = setup();
    act(() => result.current.assign(0, { id: 1 }));
    await waitFor(() => expect(result.current.slotSeries[0].data[0]).toEqual([1000]));

    act(() => {
      realtime.emit(statusEnvelope(1, 1, { pv: ff(12), timestamp: 1001 }));
    });
    expect(result.current.slotSeries[0].data[0]).toEqual([1000, 1001]);
    expect(result.current.slotSeries[0].data[1]).toEqual([10, 12]);
  });

  it('fetches once per occupancy, and again after the slot is re-assigned', async () => {
    trend.mockResolvedValue(ringFrames(1, [1000, 10]));
    const { result } = setup();

    act(() => result.current.assign(0, { id: 1 }));
    await waitFor(() => expect(trend).toHaveBeenCalledTimes(1));
    // A signal toggle is not a new occupancy — it must not refetch.
    act(() => result.current.toggleSeries(0, 'co'));
    expect(trend).toHaveBeenCalledTimes(1);

    act(() => result.current.clear(0));
    act(() => result.current.assign(0, { id: 1 }));
    await waitFor(() => expect(trend).toHaveBeenCalledTimes(2));
  });

  it('keeps the cell live-only when the ring is unreachable', async () => {
    trend.mockRejectedValue(new Error('network failure'));
    const { result, realtime } = setup();
    act(() => result.current.assign(0, { id: 1 }));

    act(() => {
      realtime.emit(statusEnvelope(1, 1, { pv: ff(5), timestamp: 1000 }));
    });
    await waitFor(() => expect(result.current.slotSeries[0].data[0]).toEqual([1000]));
    expect(result.current.slotSeries[0].data[1]).toEqual([5]);
  });
});
