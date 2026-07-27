import { act, render, renderHook, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createElement, useEffect, useRef, type ReactNode } from 'react';
import { RealtimeProvider } from './RealtimeProvider';
import { useRealtime } from './useRealtime';
import { useLoopStatuses } from '@/features/dashboard/useLoopStatuses';
import { useMultiTrendModel } from '@/features/multitrend/useMultiTrendModel';
import type { ResyncRunner } from './resync';

/**
 * Multi-loop fan-out through the REAL provider (§7).
 *
 * Every other realtime suite either injects `createFakeRealtime` — bypassing
 * the provider, its frame cache and its dispatch — or drives a single loop.
 * Both blind spots hid the same defect: the frame-cache replay handed to a
 * subscriber was dropped for every consumer that reads through the hook relay
 * (`useRealtime().subscribe`), because React runs the hook's own effect, which
 * triggers the replay, BEFORE the consumer effect that registers the relay.
 *
 * One loop under active control hides it — its next frame lands within a
 * second. With several loops the backend coalesces `status` per (type,
 * loop_id), so a loop that has gone quiet has no next frame to give and stays
 * blank forever.
 *
 * These tests therefore speak the wire, not the context: the double below is a
 * transport, and the provider, cache and consumer hooks are the real ones.
 */

class WireSocket {
  static instances: WireSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;
  sent: string[] = [];
  constructor(public url: string) {
    WireSocket.instances.push(this);
  }
  send(d: string) {
    this.sent.push(d);
  }
  close() {}
  /** Handshake exactly as realtime.py does: accept, then `auth_ok`. */
  handshake() {
    this.onopen?.();
    this.onmessage?.({ data: JSON.stringify({ type: 'auth_ok' }) });
  }
  deliver(env: unknown) {
    this.onmessage?.({ data: JSON.stringify(env) });
  }
}

const LOOPS = [1, 2, 3, 4] as const;

/** The bridge stamps ONE monotonic seq across every loop (realtime.py:156). */
let seq = 0;
const statusEnv = (loopId: number, pv: number, t: number) => ({
  type: 'status',
  loop_id: loopId,
  seq: ++seq,
  ts: t,
  data: {
    controller_id: loopId,
    pv: { value: pv, severity: 'GOOD', limit_bits: 'NONE', sub_status: 'NONE' },
    sp: { value: 50, severity: 'GOOD', limit_bits: 'NONE', sub_status: 'NONE' },
    co: { value: pv / 2, severity: 'GOOD', limit_bits: 'NONE', sub_status: 'NONE' },
    bkcal_in: { value: 0, severity: 'GOOD', limit_bits: 'NONE', sub_status: 'NONE' },
    bkcal_out: { value: 0, severity: 'GOOD', limit_bits: 'NONE', sub_status: 'NONE' },
    mode: 'AUTO',
    kp: 1,
    ti: 10,
    td: 0,
    integral_val: 0,
    timestamp: t,
  },
});

const wire = () => WireSocket.instances[0];

/** One scan of the plant: every listed loop reports at time `t`. */
function scan(loops: readonly number[], t: number, pv: (loopId: number) => number): void {
  act(() => {
    for (const id of loops) wire().deliver(statusEnv(id, pv(id), t));
  });
}

const resync: ResyncRunner = () => Promise.resolve();
const onAuthExpired = vi.fn();

function provider(children: ReactNode) {
  return createElement(RealtimeProvider, { token: 'jwt-multi', resync, onAuthExpired }, children);
}

/** The dashboard card strip, reduced to the value each card shows. */
function CardStrip() {
  const byLoop = useLoopStatuses();
  return createElement(
    'div',
    null,
    LOOPS.map((id) =>
      createElement(
        'output',
        { key: id, 'data-testid': `pv-${id}` },
        byLoop.has(id) ? String(byLoop.get(id)!.pv.value) : '—',
      ),
    ),
  );
}

const shownPvs = () => LOOPS.map((id) => screen.getByTestId(`pv-${id}`).textContent);

beforeEach(() => {
  seq = 0;
  WireSocket.instances = [];
  vi.stubGlobal('WebSocket', WireSocket as unknown as typeof WebSocket);
});

describe('multi-loop fan-out through the real provider', () => {
  it('routes each loop to its own card as frames stream in', () => {
    render(provider(createElement(CardStrip)));
    act(() => wire().handshake());
    scan(LOOPS, 1000, (id) => id * 10);
    scan(LOOPS, 1001, (id) => id * 10 + 1);

    expect(shownPvs()).toEqual(['11', '21', '31', '41']);
  });

  it('renders every loop when the dashboard mounts between scans', () => {
    // Navigating back to the dashboard remounts the consumer while the
    // provider — and its frame cache — stay alive.
    const { rerender } = render(provider(null));
    act(() => wire().handshake());
    scan(LOOPS, 1000, (id) => id * 10);

    rerender(provider(createElement(CardStrip)));

    expect(shownPvs()).toEqual(['10', '20', '30', '40']);
  });

  it('keeps a loop that has gone quiet while the others keep reporting', () => {
    // Backend policy: `status` coalesces per (type, loop_id), so a settled loop
    // can be silent for a long time. Its last frame is all the UI will get.
    const { rerender } = render(provider(createElement(CardStrip)));
    act(() => wire().handshake());
    scan(LOOPS, 1000, (id) => id * 10);
    const busy = [1, 3, 4];
    scan(busy, 1001, (id) => id * 10 + 1);
    scan(busy, 1002, (id) => id * 10 + 2);

    rerender(provider(null));
    rerender(provider(createElement(CardStrip)));
    scan(busy, 1003, (id) => id * 10 + 3);

    expect(shownPvs()).toEqual(['13', '20', '33', '43']);
  });

  it('gives every trend slot its own loop, with no cross-loop bleed', () => {
    const { result } = renderHook(() => useMultiTrendModel(null), {
      wrapper: ({ children }: { children: ReactNode }) => provider(children),
    });
    act(() => wire().handshake());
    act(() => LOOPS.forEach((id, slot) => result.current.assign(slot, { id })));

    for (let tick = 0; tick < 4; tick += 1) {
      scan(LOOPS, 1000 + tick, (id) => id * 100 + tick);
    }

    const series = result.current.slotSeries;
    expect(series.map((s) => s.data[0].length)).toEqual([4, 4, 4, 4]);
    // data[1] is PV — each slot must carry only its own loop's samples.
    expect(series.map((s) => s.data[1])).toEqual([
      [100, 101, 102, 103],
      [200, 201, 202, 203],
      [300, 301, 302, 303],
      [400, 401, 402, 403],
    ]);
  });

  it('hands the relay a stable identity so a consumer subscribes once, not once per frame', () => {
    // Consumers key their effect on `subscribe`. Rebuilding it per envelope
    // tears every realtime consumer down and back up at frame rate, which is
    // what made the dropped replay permanent rather than a one-off.
    const registrations: number[] = [];
    function Counter() {
      const { subscribe } = useRealtime(null, 'status');
      const n = useRef(0);
      useEffect(() => {
        n.current += 1;
        registrations.push(n.current);
        return subscribe(() => {});
      }, [subscribe]);
      return null;
    }
    render(provider(createElement(Counter)));
    act(() => wire().handshake());
    for (let tick = 0; tick < 5; tick += 1) scan(LOOPS, 1000 + tick, (id) => id);

    expect(registrations).toEqual([1]);
  });
});
