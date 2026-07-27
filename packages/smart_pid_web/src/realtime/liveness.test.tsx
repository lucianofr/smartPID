import { act, render, renderHook, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createElement, type ReactNode } from 'react';
import { RealtimeProvider, SILENCE_RECYCLE_MS, STALE_AFTER_MS } from './RealtimeProvider';
import { useRealtime } from './useRealtime';
import type { ResyncRunner } from './resync';

/**
 * E2E-047 — the outage the socket never reports.
 *
 * Killing the daemon behind the Vite proxy was measured to leave the browser
 * socket in `readyState: OPEN` with no `error` and no `close`, forever. The
 * phase machine was therefore never entered, the dashboard kept rendering
 * pre-outage PV as live, and it never recovered without a page reload.
 *
 * Every case here drives that shape: a socket that is open and silent. A mock
 * that closes would only exercise the path that already worked.
 */
class SilentWS {
  static instances: SilentWS[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;
  closed = false;
  sent: string[] = [];
  readyState = 0;

  constructor(public url: string) {
    SilentWS.instances.push(this);
  }
  send(d: string) {
    this.sent.push(d);
  }
  /** The real thing: close() never reports back on a half-open path. */
  close() {
    this.closed = true;
    this.readyState = 3;
  }
  _open() {
    this.readyState = 1;
    this.onopen?.();
    this.onmessage?.({ data: JSON.stringify({ type: 'auth_ok' }) });
  }
  _frame(seq: number, pv = 42) {
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
}

/**
 * The dead-man timer is polled once a second, so a threshold is observed on the
 * first tick strictly past it: never early, at most a tick late. Tests overshoot
 * by this much rather than pinning the poll period.
 */
const TICK_SLACK_MS = 1_500;

const onAuthExpired = vi.fn();
let resyncCalls: number;
const resync: ResyncRunner = () => {
  resyncCalls += 1;
  return Promise.resolve();
};

function wrapper({ children }: { children: ReactNode }) {
  return createElement(RealtimeProvider, { token: 'jwt-1', resync, onAuthExpired }, children);
}

function mount() {
  return renderHook(() => useRealtime<{ pv: { value: number } }>(1, 'status'), { wrapper });
}

/** Advance wall clock AND timers together: the watchdog compares Date.now(). */
async function idle(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

beforeEach(() => {
  SilentWS.instances = [];
  resyncCalls = 0;
  onAuthExpired.mockClear();
  vi.useFakeTimers();
  vi.stubGlobal('WebSocket', SilentWS as unknown as typeof WebSocket);
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('link liveness — a socket that is open and silent', () => {
  it('marks the rendered frame stale once the bus goes quiet', async () => {
    const { result } = mount();
    act(() => SilentWS.instances[0]._open());
    act(() => SilentWS.instances[0]._frame(1, 42));

    expect(result.current.last?.data.pv.value).toBe(42);
    expect(result.current.stale).toBe(false);

    await idle(STALE_AFTER_MS - TICK_SLACK_MS);
    expect(result.current.stale).toBe(false); // still inside the deadline

    await idle(2 * TICK_SLACK_MS);
    expect(result.current.stale).toBe(true);
    // The value is retained — the operator sees the LAST reading, marked, not a blank.
    expect(result.current.last?.data.pv.value).toBe(42);
  });

  it('a fresh frame clears stale without touching the socket', async () => {
    const { result } = mount();
    act(() => SilentWS.instances[0]._open());
    act(() => SilentWS.instances[0]._frame(1, 42));
    await idle(STALE_AFTER_MS + TICK_SLACK_MS);
    expect(result.current.stale).toBe(true);

    act(() => SilentWS.instances[0]._frame(2, 43));
    await idle(0);
    expect(result.current.stale).toBe(false);
    expect(result.current.last?.data.pv.value).toBe(43);
    expect(SilentWS.instances).toHaveLength(1);
  });

  it('recycles the dead socket and reconnects — the defect: it used to sit live forever', async () => {
    const { result } = mount();
    act(() => SilentWS.instances[0]._open());
    act(() => SilentWS.instances[0]._frame(1, 42));
    expect(result.current.live).toBe(true);

    await idle(SILENCE_RECYCLE_MS - TICK_SLACK_MS);
    expect(SilentWS.instances).toHaveLength(1);
    expect(result.current.live).toBe(true); // stale already, but still hoping

    await idle(2 * TICK_SLACK_MS);
    expect(SilentWS.instances[0].closed).toBe(true);
    expect(result.current.live).toBe(false);
    expect(result.current.connected).toBe(false);

    // Backoff schedules the replacement; the socket count is the proof it fired.
    await idle(600);
    expect(SilentWS.instances).toHaveLength(2);
  });

  it('resyncs before rendering live again, then tracks the plant — no remount', async () => {
    const { result } = mount();
    act(() => SilentWS.instances[0]._open());
    act(() => SilentWS.instances[0]._frame(1, 42));

    await idle(SILENCE_RECYCLE_MS + TICK_SLACK_MS); // outage detected → recycle
    await idle(600); // backoff → replacement socket
    const revived = SilentWS.instances[1];

    act(() => revived._open()); // auth_ok on a reconnect ⇒ §8 resync first
    expect(resyncCalls).toBe(1);
    expect(result.current.live).toBe(false); // resync gates live render

    await idle(0); // resync promise settles
    expect(result.current.live).toBe(true);
    // Still stale: resync restored REST truth, but no realtime frame has landed,
    // so the PV on screen is provably the pre-outage one.
    expect(result.current.stale).toBe(true);

    act(() => revived._frame(1, 96));
    await idle(0);
    expect(result.current.stale).toBe(false);
    expect(result.current.last?.data.pv.value).toBe(96);
  });

  it('recycles at most once per silent episode — a quiet plant must not flap', async () => {
    mount();
    act(() => SilentWS.instances[0]._open());
    act(() => SilentWS.instances[0]._frame(1, 42));

    await idle(SILENCE_RECYCLE_MS + TICK_SLACK_MS);
    await idle(600);
    expect(SilentWS.instances).toHaveLength(2);

    // The replacement authenticates and resyncs fine — the plant is simply not
    // publishing. Three more silent windows must not spawn three more sockets.
    act(() => SilentWS.instances[1]._open());
    await idle(0);
    await idle(SILENCE_RECYCLE_MS * 3);
    expect(SilentWS.instances).toHaveLength(2);
  });

  it('never recycles before the first frame — an empty plant is not an outage', async () => {
    const { result } = mount();
    act(() => SilentWS.instances[0]._open());

    await idle(SILENCE_RECYCLE_MS * 2);
    expect(SilentWS.instances).toHaveLength(1);
    expect(result.current.stale).toBe(false);
    expect(result.current.live).toBe(true);
  });

  it('stops the watchdog when the session ends', async () => {
    function Probe() {
      const { stale } = useRealtime<{ pv: { value: number } }>(1, 'status');
      return createElement('output', null, stale ? 'stale' : 'fresh');
    }
    const tree = (token: string | null) =>
      createElement(RealtimeProvider, { token, resync, onAuthExpired }, createElement(Probe));

    const { rerender } = render(tree('jwt-1'));
    act(() => SilentWS.instances[0]._open());
    act(() => SilentWS.instances[0]._frame(1, 42));
    await idle(STALE_AFTER_MS + TICK_SLACK_MS);
    expect(screen.getByText('stale')).toBeInTheDocument();

    rerender(tree(null));
    await idle(SILENCE_RECYCLE_MS * 2);
    expect(screen.getByText('fresh')).toBeInTheDocument(); // logged out — nothing to call stale
    expect(SilentWS.instances).toHaveLength(1);
  });
});
