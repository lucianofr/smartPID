import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
import type { HistoryResponse } from '@/api/types';
import { RealtimeContext } from '@/realtime/RealtimeProvider';
import { createFakeRealtime } from '@/test/providers';
import { ff, statusEnvelope } from '@/test/fixtures';
import { useTrendWindow } from './useTrendWindow';

const trend = vi.fn();
vi.mock('@/api/endpoints', () => ({ endpoints: { trend: (...args: unknown[]) => trend(...args) } }));

/** Wire frames as `/trend/{id}` returns them: ISO timestamps, ascending. */
function ringFrames(...points: [number, number][]): HistoryResponse {
  return {
    controller_id: 5,
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

/**
 * A dense ring at the REAL telemetry rate. `scan_interval_s` /
 * `simulator_interval_ms` default to 100 ms, so an hour is ~36 000 samples —
 * not the 3 600 a 1 Hz feed would give.
 */
function denseRing(seconds: number, hz = 10): HistoryResponse {
  const n = seconds * hz;
  const frames = new Array<HistoryResponse['frames'][number]>(n);
  for (let i = 0; i < n; i += 1) {
    frames[i] = {
      timestamp: new Date((1_000_000 + i / hz) * 1000).toISOString(),
      pv: 50,
      sp: 55,
      co: 42,
      mode: 'AUTO',
      status: 'GOOD',
    };
  }
  return { controller_id: 5, count: n, frames };
}

function setup(controllerId = 5, maxSeconds = 3600, pxWidth = 800) {
  const realtime = createFakeRealtime();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <RealtimeContext.Provider value={realtime.value}>{children}</RealtimeContext.Provider>
  );
  const view = renderHook(
    ({ id, secs }: { id: number; secs: number }) => useTrendWindow(id, secs, pxWidth),
    { wrapper, initialProps: { id: controllerId, secs: maxSeconds } },
  );
  return { ...view, realtime };
}

beforeEach(() => {
  trend.mockReset();
});

describe('useTrendWindow — backend ring seed', () => {
  it('paints the stored window on mount instead of waiting an hour to fill it', async () => {
    trend.mockResolvedValue(ringFrames([1000, 10], [1001, 11], [1002, 12]));
    const { result } = setup();

    await waitFor(() => expect(result.current.sampleCount).toBe(3));
    expect(result.current.data.t).toEqual([1000, 1001, 1002]);
    expect(result.current.data.pv).toEqual([10, 11, 12]);
    expect(result.current.data.sp).toEqual([55, 55, 55]);
    expect(result.current.data.co).toEqual([42, 42, 42]);
    expect(trend).toHaveBeenCalledWith(5, 3600);
  });

  it('retains the whole requested window at the real telemetry rate', async () => {
    // The point cap was sized for 1 Hz while the feed is the 100 ms IO scan, so
    // asking for 30 minutes kept only the newest 8 000 samples — 13.4 min — and
    // the x axis quietly agreed with the shortened window, so nothing on screen
    // said the trace had been cut.
    const seconds = 1800;
    trend.mockResolvedValue(denseRing(seconds));
    const { result } = setup(5, seconds);

    await waitFor(() => expect(result.current.sampleCount).toBe(seconds * 10), {
      timeout: 15_000,
    });
    // Pen tip is the undecimated head, so this is the true plotted span.
    const span = (result.current.penTip?.t ?? 0) - result.current.data.t[0];
    expect(span).toBeCloseTo(seconds - 0.1, 1);
  });

  it('asks the ring only for the window the operator chose', async () => {
    trend.mockResolvedValue(ringFrames());
    setup(5, 60);
    await waitFor(() => expect(trend).toHaveBeenCalledWith(5, 60));
  });

  it('appends live frames on top of the seeded history', async () => {
    trend.mockResolvedValue(ringFrames([1000, 10], [1001, 11]));
    const { result, realtime } = setup();
    await waitFor(() => expect(result.current.sampleCount).toBe(2));

    act(() => {
      realtime.emit(statusEnvelope(5, 1, { pv: ff(12), timestamp: 1002 }));
    });
    expect(result.current.data.t).toEqual([1000, 1001, 1002]);
    expect(result.current.penTip).toEqual({ t: 1002, pv: 12 });
  });

  // The seed is in flight for as long as the request takes; frames that land in
  // that gap used to be wiped by a clear()+replay seed.
  it('keeps frames that arrive while the seed is in flight, without duplicating them', async () => {
    // Executor form, not Promise.withResolvers: this package compiles against
    // lib ES2022, where that helper does not exist yet.
    let settle: ((res: HistoryResponse) => void) | undefined;
    trend.mockReturnValue(
      new Promise<HistoryResponse>((resolve) => {
        settle = resolve;
      }),
    );
    const { result, realtime } = setup();

    act(() => {
      realtime.emit(statusEnvelope(5, 1, { pv: ff(20), timestamp: 1002 }));
    });
    expect(result.current.sampleCount).toBe(1);

    // The ring answers with history that predates the live frame, plus the very
    // same sample the socket already delivered.
    await act(async () => {
      settle?.(ringFrames([1000, 10], [1001, 11], [1002, 99]));
      await Promise.resolve();
    });

    await waitFor(() => expect(result.current.sampleCount).toBe(3));
    expect(result.current.data.t).toEqual([1000, 1001, 1002]);
    // The live value wins the tie — it is what the operator watched being drawn.
    expect(result.current.data.pv).toEqual([10, 11, 20]);
  });

  it('re-seeds for the newly selected loop', async () => {
    trend.mockResolvedValue(ringFrames([1000, 10]));
    const { result, rerender } = setup();
    await waitFor(() => expect(result.current.sampleCount).toBe(1));

    trend.mockResolvedValue(ringFrames([2000, 77], [2001, 78]));
    rerender({ id: 6, secs: 3600 });
    await waitFor(() => expect(result.current.data.t).toEqual([2000, 2001]));
    expect(trend).toHaveBeenLastCalledWith(6, 3600);
  });

  it('widening the window pulls back history the narrow buffer had evicted', async () => {
    trend.mockResolvedValue(ringFrames([1990, 5], [2000, 6]));
    const { result, rerender } = setup(5, 60);
    await waitFor(() => expect(result.current.sampleCount).toBe(2));

    trend.mockResolvedValue(ringFrames([1000, 1], [1990, 5], [2000, 6]));
    rerender({ id: 5, secs: 3600 });
    await waitFor(() => expect(result.current.data.t).toEqual([1000, 1990, 2000]));
  });

  it('falls back to live-only when the ring is unreachable', async () => {
    trend.mockRejectedValue(new Error('network failure'));
    const { result, realtime } = setup();

    act(() => {
      realtime.emit(statusEnvelope(5, 1, { pv: ff(3), timestamp: 1000 }));
    });
    await waitFor(() => expect(result.current.data.t).toEqual([1000]));
    expect(result.current.data.pv).toEqual([3]);
  });
});
