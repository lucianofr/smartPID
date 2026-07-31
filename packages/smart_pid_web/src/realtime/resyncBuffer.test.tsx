import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createElement, useContext, useEffect, type ReactNode } from 'react';
import { RealtimeContext, RealtimeProvider } from './RealtimeProvider';
import { useRealtime } from './useRealtime';
import type { ResyncRunner } from './resync';

/**
 * Frames that arrive WHILE a resync is running (RealtimeProvider §7/§8).
 *
 * On a detected sequence gap the provider clears its cache, refetches over
 * REST, and holds the socket traffic that lands in between. Two policies are
 * pinned here because nothing else in the suite reaches them:
 *
 *  - status/stats are *coalesced* per loop, so a long resync cannot replay a
 *    burst of superseded process values onto the screen;
 *  - alarm/ai/system are *lossless* up to a 256-frame cap mirroring the
 *    backend's own per-connection limit, and drop beyond it.
 */
class FakeWS {
  static instances: FakeWS[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;
  readyState = 0;
  sent: string[] = [];

  constructor(public url: string) {
    FakeWS.instances.push(this);
  }
  send(d: string) {
    this.sent.push(d);
  }
  close() {
    this.readyState = 3;
  }
  _open() {
    this.readyState = 1;
    this.onopen?.();
    this.onmessage?.({ data: JSON.stringify({ type: 'auth_ok' }) });
  }
  _status(seq: number, pv: number) {
    this.onmessage?.({
      data: JSON.stringify({
        type: 'status',
        loop_id: 1,
        seq,
        ts: seq,
        data: { controller_id: 1, pv: { value: pv } },
      }),
    });
  }
  _alarm(seq: number) {
    this.onmessage?.({
      data: JSON.stringify({
        type: 'alarm',
        loop_id: 1,
        seq,
        ts: seq,
        data: { controller_id: 1, alarm_type: 'PV_HI', transition: 'ACTIVE' },
      }),
    });
  }
}

/** A resync that stays pending until the test releases it. */
function deferredResync() {
  let resolve!: () => void;
  const runner: ResyncRunner = () =>
    new Promise<void>((r) => {
      resolve = r;
    });
  return { runner, release: () => resolve() };
}

beforeEach(() => {
  FakeWS.instances = [];
  vi.stubGlobal('WebSocket', FakeWS as unknown as typeof WebSocket);
});
afterEach(() => {
  vi.unstubAllGlobals();
});

function makeWrapper(resync: ResyncRunner) {
  const onAuthExpired = () => {};
  return function wrapper({ children }: { children: ReactNode }) {
    return createElement(
      RealtimeProvider,
      { token: 'jwt-1', resync, onAuthExpired },
      children,
    );
  };
}

/**
 * Open, prime the sequence, then jump it. The provider treats the jump as loss
 * and enters `resyncing`; the jumping envelope is itself held back.
 */
function enterResync(ws: FakeWS) {
  act(() => ws._open());
  act(() => ws._status(1, 10));
  act(() => ws._status(99, 0));
}

describe('frames arriving during a resync', () => {
  it('holds a status frame back until the resync completes', async () => {
    const { runner, release } = deferredResync();
    const { result } = renderHook(
      () => ({
        status: useRealtime<{ pv: { value: number } }>(1, 'status'),
        phase: useContext(RealtimeContext)?.phase,
      }),
      { wrapper: makeWrapper(runner) },
    );
    const ws = FakeWS.instances[0];
    enterResync(ws);

    expect(result.current.phase).toBe('resyncing');
    expect(result.current.status.live).toBe(false);
    // Authenticated throughout — resyncing is still a connected phase.
    expect(result.current.status.connected).toBe(true);

    act(() => ws._status(100, 55));
    expect(result.current.status.last?.data.pv.value).not.toBe(55);

    await act(async () => {
      release();
      await Promise.resolve();
    });

    expect(result.current.phase).toBe('live');
    expect(result.current.status.last?.data.pv.value).toBe(55);
  });

  it('coalesces status frames so only the newest is replayed', async () => {
    const { runner, release } = deferredResync();
    const seen: number[] = [];
    const { result } = renderHook(
      () => {
        const status = useRealtime<{ pv: { value: number } }>(1, 'status');
        const { subscribe } = status;
        useEffect(
          () => subscribe((env) => seen.push(env.data.pv.value)),
          [subscribe],
        );
        return { status, phase: useContext(RealtimeContext)?.phase };
      },
      { wrapper: makeWrapper(runner) },
    );
    const ws = FakeWS.instances[0];
    enterResync(ws);
    seen.length = 0; // ignore anything dispatched before the gap

    act(() => {
      for (let i = 0; i < 50; i += 1) ws._status(100 + i, i);
    });

    await act(async () => {
      release();
      await Promise.resolve();
    });

    expect(result.current.phase).toBe('live');
    // A burst of 50 collapses to its newest sample instead of replaying a run
    // of superseded values across the trend.
    expect(seen).toEqual([49]);
    expect(result.current.status.last?.data.pv.value).toBe(49);
  });

  it('keeps every alarm up to the cap and drops the overflow', async () => {
    const { runner, release } = deferredResync();
    const alarms: unknown[] = [];
    const { result } = renderHook(
      () => {
        const alarm = useRealtime(1, 'alarm');
        const { subscribe } = alarm;
        useEffect(() => subscribe((env) => alarms.push(env)), [subscribe]);
        return { phase: useContext(RealtimeContext)?.phase };
      },
      { wrapper: makeWrapper(runner) },
    );
    const ws = FakeWS.instances[0];
    enterResync(ws);
    alarms.length = 0;

    // One past the documented 256-frame lossless cap.
    act(() => {
      for (let i = 0; i < 257; i += 1) ws._alarm(200 + i);
    });
    // Nothing is delivered while the resync is still in flight.
    expect(alarms.length).toBe(0);

    await act(async () => {
      release();
      await Promise.resolve();
    });

    expect(result.current.phase).toBe('live');
    // Lossless up to the cap; the 257th is dropped, mirroring the backend.
    expect(alarms.length).toBe(256);
  });
});
