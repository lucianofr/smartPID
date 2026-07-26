import { act, renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { ReactNode } from 'react';
import { RealtimeContext } from '@/realtime/RealtimeProvider';
import { createFakeRealtime } from '@/test/providers';
import { ff, statusEnvelope } from '@/test/fixtures';
import type { AiData, RealtimeEnvelope } from '@/lib/envelope';
import { useTrendWindow } from './useTrendWindow';

function aiEnvelope(loopId: number, seq: number, timestamp: string): RealtimeEnvelope<AiData> & { type: 'ai' } {
  return {
    type: 'ai',
    loop_id: loopId,
    seq,
    ts: seq,
    data: {
      controller_id: loopId,
      gamma: 0.1,
      new_ki: 0.2,
      engine: 'RL',
      objective: 'DISTURBANCE_REJECTION',
      integral_type: 'TIME_TI',
      execution_mode: 'SUPERVISORY',
      reasoning: 'test',
      timestamp,
    },
  };
}

function setup(controllerId = 5, maxSeconds = 60, pxWidth = 800) {
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

describe('useTrendWindow', () => {
  it('accumulates only its own loop and keeps time ascending', () => {
    const { result, realtime } = setup();
    act(() => {
      realtime.emit(statusEnvelope(5, 1, { pv: ff(10), timestamp: 1000 }));
      realtime.emit(statusEnvelope(9, 2, { pv: ff(99), timestamp: 1001 }));
      realtime.emit(statusEnvelope(5, 3, { pv: ff(11), timestamp: 1002 }));
    });
    expect(result.current.sampleCount).toBe(2);
    expect(result.current.data.t).toEqual([1000, 1002]);
    expect(result.current.data.pv).toEqual([10, 11]);
  });

  it('exposes the undecimated head as the pen tip', () => {
    const { result, realtime } = setup(5, 60, 2);
    act(() => {
      for (let i = 0; i < 12; i += 1) {
        realtime.emit(statusEnvelope(5, i + 1, { pv: ff(i), timestamp: 1000 + i }));
      }
    });
    // The plotted series is decimated…
    expect(result.current.data.t.length).toBeLessThan(result.current.sampleCount);
    // …but the pen marks the true latest sample.
    expect(result.current.penTip).toEqual({ t: 1011, pv: 11 });
  });

  it('drops samples that fall outside the window', () => {
    const { result, realtime } = setup(5, 10);
    act(() => {
      realtime.emit(statusEnvelope(5, 1, { pv: ff(1), timestamp: 1000 }));
      realtime.emit(statusEnvelope(5, 2, { pv: ff(2), timestamp: 1005 }));
      realtime.emit(statusEnvelope(5, 3, { pv: ff(3), timestamp: 1020 }));
    });
    expect(result.current.data.t).toEqual([1020]);
  });

  it('re-seeds retained samples when the window is resized', () => {
    const { result, realtime, rerender } = setup(5, 3600);
    act(() => {
      realtime.emit(statusEnvelope(5, 1, { pv: ff(1), timestamp: 1000 }));
      realtime.emit(statusEnvelope(5, 2, { pv: ff(2), timestamp: 1900 }));
    });
    expect(result.current.sampleCount).toBe(2);

    // Shrinking to 60 s keeps only the sample inside the new window…
    rerender({ id: 5, secs: 60 });
    expect(result.current.data.t).toEqual([1900]);

    // …and growing again does not resurrect what was dropped.
    rerender({ id: 5, secs: 3600 });
    expect(result.current.data.t).toEqual([1900]);
  });

  it('clears the trace when the selected loop changes', () => {
    const { result, realtime, rerender } = setup(5);
    act(() => {
      realtime.emit(statusEnvelope(5, 1, { pv: ff(1), timestamp: 1000 }));
    });
    expect(result.current.sampleCount).toBe(1);
    rerender({ id: 6, secs: 60 });
    expect(result.current.sampleCount).toBe(0);
    expect(result.current.penTip).toBeNull();
  });

  it('collects AI intervention ticks inside the window', () => {
    const { result, realtime } = setup();
    act(() => {
      realtime.emit(statusEnvelope(5, 1, { pv: ff(1), timestamp: 1000 }));
      realtime.emit(aiEnvelope(5, 2, '1970-01-01T00:16:50.000Z'));
      realtime.emit(aiEnvelope(9, 3, '1970-01-01T00:16:51.000Z'));
    });
    expect(result.current.aiTicks).toEqual([1010]);
  });
});
