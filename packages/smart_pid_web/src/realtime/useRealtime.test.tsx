import { act, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createElement, useContext, type ReactNode } from 'react';
import { RealtimeContext, RealtimeProvider, type RealtimeContextValue } from './RealtimeProvider';
import { useRealtime } from './useRealtime';
import type { ResyncRunner } from './resync';

class MockWS {
  static instances: MockWS[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;
  sent: string[] = [];
  readyState = 0;
  constructor(public url: string) {
    MockWS.instances.push(this);
  }
  send(d: string) {
    this.sent.push(d);
  }
  close() {
    this.readyState = 3;
    this.onclose?.({ code: 1000 });
  }
  _open() {
    this.readyState = 1;
    this.onopen?.();
    // Server handshake ack (realtime.py register_realtime_ws)
    this.onmessage?.({ data: JSON.stringify({ type: 'auth_ok' }) });
  }
  _emit(obj: unknown) {
    this.onmessage?.({ data: JSON.stringify(obj) });
  }
  _close(code: number) {
    this.readyState = 3;
    this.onclose?.({ code });
  }
}

let resyncCalls: Array<{ lastSeenAlarmTs: number | null }>;
const recordingResync: ResyncRunner = (ctx) => {
  resyncCalls.push(ctx);
  return Promise.resolve();
};

beforeEach(() => {
  MockWS.instances = [];
  resyncCalls = [];
  vi.stubGlobal('WebSocket', MockWS as unknown as typeof WebSocket);
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const onAuthExpired = vi.fn();

function wrapper({ children }: { children: ReactNode }) {
  return createElement(
    RealtimeProvider,
    { token: 'jwt-123', resync: recordingResync, onAuthExpired },
    children,
  );
}

const statusEnv = (loopId: number, seq: number, pv = 42) => ({
  type: 'status',
  loop_id: loopId,
  seq,
  ts: seq,
  data: { controller_id: loopId, pv: { value: pv } },
});

describe('RealtimeProvider handshake and fan-out', () => {
  it('opens /ws/realtime and sends the first-frame auth', () => {
    renderHook(() => useRealtime(null, 'status'), { wrapper });
    const ws = MockWS.instances[0];
    expect(ws.url).toContain('/ws/realtime');
    act(() => ws._open());
    expect(JSON.parse(ws.sent[0])).toEqual({ type: 'auth', token: 'jwt-123' });
  });

  it('creates no socket without a token (phase idle)', () => {
    renderHook(() => useRealtime(null, 'status'), {
      wrapper: ({ children }: { children: ReactNode }) =>
        createElement(
          RealtimeProvider,
          { token: null, resync: recordingResync, onAuthExpired },
          children,
        ),
    });
    expect(MockWS.instances).toHaveLength(0);
  });

  it('goes live after auth_ok WITHOUT resyncing on the first connection (§8: reconnect/gap only)', async () => {
    const { result } = renderHook(() => useRealtime(null, 'status'), { wrapper });
    act(() => MockWS.instances[0]._open());
    await waitFor(() => expect(result.current.live).toBe(true));
    expect(resyncCalls).toHaveLength(0);
  });

  it('delivers the latest envelope for the subscribed (loopId, type)', async () => {
    const { result } = renderHook(() => useRealtime(5, 'status'), { wrapper });
    act(() => MockWS.instances[0]._open());
    act(() => MockWS.instances[0]._emit(statusEnv(5, 1, 42)));
    await waitFor(() =>
      expect((result.current.last?.data as { pv: { value: number } }).pv.value).toBe(42),
    );
  });

  it('filters by loop_id — other loops never reach the hook', async () => {
    const { result } = renderHook(() => useRealtime(5, 'status'), { wrapper });
    act(() => MockWS.instances[0]._open());
    act(() => MockWS.instances[0]._emit(statusEnv(9, 1)));
    act(() => MockWS.instances[0]._emit(statusEnv(5, 2, 77)));
    await waitFor(() => expect(result.current.last?.loop_id).toBe(5));
    expect((result.current.last?.data as { pv: { value: number } }).pv.value).toBe(77);
  });

  it('loopId null receives every loop of that type', async () => {
    const seen: number[] = [];
    const { result } = renderHook(() => useRealtime(null, 'alarm'), { wrapper });
    act(() => MockWS.instances[0]._open());
    act(() => {
      result.current.subscribe((env) => seen.push(env.loop_id ?? -1));
    });
    act(() =>
      MockWS.instances[0]._emit({ type: 'alarm', loop_id: 1, seq: 1, ts: 1, data: { transition: 'TRIGGERED' } }),
    );
    act(() =>
      MockWS.instances[0]._emit({ type: 'alarm', loop_id: 2, seq: 2, ts: 2, data: { transition: 'CLEARED' } }),
    );
    await waitFor(() => expect(seen).toEqual([1, 2]));
  });

  it('ignores malformed frames without crashing', async () => {
    const { result } = renderHook(() => useRealtime(null, 'status'), { wrapper });
    const ws = MockWS.instances[0];
    act(() => ws._open());
    act(() => ws.onmessage?.({ data: '{not json' }));
    act(() => ws._emit({ type: 'bogus', whatever: 1 }));
    act(() => ws._emit(statusEnv(1, 1)));
    await waitFor(() => expect(result.current.last).not.toBeNull());
  });
});

describe('RealtimeProvider close-code policy', () => {
  it('close 4401 → onAuthExpired, phase auth-failed, NO reconnect', async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useRealtime(null, 'status'), { wrapper });
    act(() => MockWS.instances[0]._open());
    act(() => MockWS.instances[0]._close(4401));
    expect(onAuthExpired).toHaveBeenCalledTimes(1);
    expect(result.current.connected).toBe(false);
    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(MockWS.instances).toHaveLength(1); // no new socket
  });

  it('other closes reconnect with doubling backoff capped at 10 s', () => {
    vi.useFakeTimers();
    renderHook(() => useRealtime(null, 'status'), { wrapper });
    act(() => MockWS.instances[0]._close(1006));
    act(() => {
      vi.advanceTimersByTime(500); // first retry after 500 ms
    });
    expect(MockWS.instances).toHaveLength(2);
    act(() => MockWS.instances[1]._close(1006));
    act(() => {
      vi.advanceTimersByTime(999);
    });
    expect(MockWS.instances).toHaveLength(2); // 1000 ms not yet elapsed
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(MockWS.instances).toHaveLength(3); // doubled to 1000 ms
  });
});

describe('§8 resync sequencing (integration)', () => {
  function deferredRunner() {
    const calls: Array<{ lastSeenAlarmTs: number | null }> = [];
    let resolve!: () => void;
    let reject!: (e: unknown) => void;
    const runner: ResyncRunner = (ctx) => {
      calls.push(ctx);
      return new Promise<void>((res, rej) => {
        resolve = res;
        reject = rej;
      });
    };
    return {
      runner,
      calls,
      resolve: () => resolve(),
      reject: (e: unknown) => reject(e),
    };
  }

  function mount(runner: ResyncRunner) {
    return renderHook(
      () => ({
        status: useRealtime<{ pv: { value: number } }>(5, 'status'),
        alarms: useRealtime(null, 'alarm'),
      }),
      {
        wrapper: ({ children }: { children: ReactNode }) =>
          createElement(
            RealtimeProvider,
            { token: 'jwt-123', resync: runner, onAuthExpired },
            children,
          ),
      },
    );
  }

  it('reconnect resyncs with the alarm last_seen_ts and buffers envelopes until done', async () => {
    vi.useFakeTimers();
    const d = deferredRunner();
    const { result } = mount(d.runner);

    // First connection: live without resync (§8 covers reconnect/gap only).
    act(() => MockWS.instances[0]._open());
    expect(result.current.status.live).toBe(true);

    // An alarm envelope stamps last_seen_ts('alarm') = 111.
    act(() =>
      MockWS.instances[0]._emit({
        type: 'alarm',
        loop_id: 5,
        seq: 1,
        ts: 111,
        data: { transition: 'TRIGGERED' },
      }),
    );

    // Drop and reconnect.
    act(() => MockWS.instances[0]._close(1006));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    const ws1 = MockWS.instances[1];
    act(() => ws1._open());

    // Resync started with the pre-disconnect alarm timestamp; not live yet.
    expect(d.calls).toEqual([{ lastSeenAlarmTs: 111 }]);
    expect(result.current.status.connected).toBe(true);
    expect(result.current.status.live).toBe(false);

    // Envelopes during resync are held back: status coalesces (latest wins),
    // alarm events queue lossless — mirroring realtime.py ConnectionBuffer.
    const alarmSeen: unknown[] = [];
    act(() => {
      result.current.alarms.subscribe((env) => alarmSeen.push(env.data));
    });
    act(() => ws1._emit(statusEnv(5, 2, 88)));
    act(() => ws1._emit(statusEnv(5, 3, 99)));
    act(() =>
      ws1._emit({ type: 'alarm', loop_id: 5, seq: 4, ts: 222, data: { transition: 'CLEARED' } }),
    );
    expect(result.current.status.last).toBeNull(); // nothing delivered yet
    expect(alarmSeen).toEqual([]);

    // Resync resolves → buffer flushes → live render resumes.
    await act(async () => {
      d.resolve();
      await Promise.resolve();
    });
    expect(result.current.status.live).toBe(true);
    expect(result.current.status.last?.data.pv.value).toBe(99); // coalesced: latest only
    expect(alarmSeen).toEqual([{ transition: 'CLEARED' }]); // lossless: delivered
  });

  it('a seq gap while live triggers resync WITHOUT reconnecting', async () => {
    const d = deferredRunner();
    const { result } = mount(d.runner);
    act(() => MockWS.instances[0]._open());
    act(() => MockWS.instances[0]._emit(statusEnv(5, 1, 10)));
    await waitFor(() => expect(result.current.status.last?.data.pv.value).toBe(10));

    // seq jumps 1 → 5: frames were lost.
    act(() => MockWS.instances[0]._emit(statusEnv(5, 5, 50)));
    expect(d.calls).toHaveLength(1);
    expect(result.current.status.live).toBe(false);
    expect(MockWS.instances).toHaveLength(1); // same socket, no reconnect

    await act(async () => {
      d.resolve();
      await Promise.resolve();
    });
    expect(result.current.status.live).toBe(true);
    // The post-gap envelope was buffered, not dropped.
    expect(result.current.status.last?.data.pv.value).toBe(50);
  });

  it('a failed resync recycles the socket and retries via backoff', async () => {
    vi.useFakeTimers();
    const d = deferredRunner();
    mount(d.runner);
    act(() => MockWS.instances[0]._open());
    act(() => MockWS.instances[0]._close(1006));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    act(() => MockWS.instances[1]._open()); // reconnect → resync starts
    expect(d.calls).toHaveLength(1);

    await act(async () => {
      d.reject(new Error('resync failed'));
      await Promise.resolve();
    });
    // Socket recycled; backoff schedules the next attempt (500 already doubled → 1000).
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(MockWS.instances).toHaveLength(3);
  });
});

describe('§7 last-frame replay', () => {
  function deferred() {
    const calls: Array<{ lastSeenAlarmTs: number | null }> = [];
    let resolve!: () => void;
    const runner: ResyncRunner = (ctx) => {
      calls.push(ctx);
      return new Promise<void>((res) => {
        resolve = res;
      });
    };
    return { runner, calls, resolve: () => resolve() };
  }

  function Probe({ loopId }: { loopId: number }) {
    const { last } = useRealtime<{ pv: { value: number } }>(loopId, 'status');
    return createElement('output', null, last === null ? 'none' : String(last.data.pv.value));
  }

  /** The provider stays mounted across rerenders; only the Probe mounts late. */
  function tree(show: boolean, resync: ResyncRunner = recordingResync) {
    return createElement(
      RealtimeProvider,
      { token: 'jwt-123', resync, onAuthExpired },
      show ? createElement(Probe, { loopId: 5 }) : null,
    );
  }

  it('hands a late subscriber the cached frame without waiting for the next one', () => {
    const { rerender } = render(tree(false));
    act(() => MockWS.instances[0]._open());
    act(() => MockWS.instances[0]._emit(statusEnv(5, 1, 42)));
    rerender(tree(true));
    expect(screen.getByText('42')).toBeInTheDocument();
  });

  it('scopes the replay to the subscriber loop', () => {
    const { rerender } = render(tree(false));
    act(() => MockWS.instances[0]._open());
    act(() => MockWS.instances[0]._emit(statusEnv(9, 1, 11)));
    rerender(tree(true));
    expect(screen.getByText('none')).toBeInTheDocument();
  });

  it('a resync drops the cache — no pre-resync frame is replayed after reconnect', async () => {
    vi.useFakeTimers();
    const d = deferred();
    const { rerender } = render(tree(false, d.runner));
    act(() => MockWS.instances[0]._open());
    act(() => MockWS.instances[0]._emit(statusEnv(5, 1, 42)));
    act(() => MockWS.instances[0]._close(1006));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    act(() => MockWS.instances[1]._open()); // reconnect → §8 resync
    await act(async () => {
      d.resolve();
      await Promise.resolve();
    });
    rerender(tree(true, d.runner)); // same props → provider effect must not remount
    expect(screen.getByText('none')).toBeInTheDocument();
  });

  it('replays the post-gap frame after a gap resync, never the pre-gap one', async () => {
    const d = deferred();
    const { rerender } = render(tree(false, d.runner));
    act(() => MockWS.instances[0]._open());
    act(() => MockWS.instances[0]._emit(statusEnv(5, 1, 10)));
    act(() => MockWS.instances[0]._emit(statusEnv(5, 5, 50))); // seq 1 → 5: gap
    expect(d.calls).toHaveLength(1);
    await act(async () => {
      d.resolve();
      await Promise.resolve();
    });
    rerender(tree(true, d.runner)); // same props → provider effect must not remount
    expect(screen.getByText('50')).toBeInTheDocument();
  });

  it('unsubscribe detaches the handler and the cache holds one frame per key', () => {
    const captured: RealtimeContextValue[] = [];
    function Capture() {
      const ctx = useContext(RealtimeContext);
      if (ctx) captured.push(ctx);
      return null;
    }
    render(
      createElement(
        RealtimeProvider,
        { token: 'jwt-123', resync: recordingResync, onAuthExpired },
        createElement(Capture),
      ),
    );
    const ctx = captured[0];
    act(() => MockWS.instances[0]._open());
    act(() => MockWS.instances[0]._emit(statusEnv(5, 1)));
    act(() => MockWS.instances[0]._emit(statusEnv(5, 2)));

    const first: number[] = [];
    const off = ctx.subscribe('status', (env) => first.push(env.seq));
    expect(first).toEqual([2]); // one replay of the newest — frames do not pile up
    off();
    act(() => MockWS.instances[0]._emit(statusEnv(5, 3)));
    expect(first).toEqual([2]); // detached: nothing after unsubscribe

    const second: number[] = [];
    const off2 = ctx.subscribe('status', (env) => second.push(env.seq));
    expect(second).toEqual([3]); // remount sees the newest frame, exactly once
    off2();
  });
});