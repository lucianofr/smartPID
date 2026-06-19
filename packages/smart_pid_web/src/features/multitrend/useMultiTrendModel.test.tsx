import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import type { FFSignal, StatusData } from '../../realtime/envelope';

// Backing store for the mock. In production `lastStatus` is a fresh Map
// reference on every WS frame (context update via useSyncExternalStore), which
// is what re-runs the appending effect; the mock emulates that by snapshotting
// a NEW Map on each call so a frame set between rerenders is observed.
const store = new Map<number, StatusData>();
vi.mock('../../realtime/useRealtime', () => ({
  useRealtime: () => ({
    connected: true,
    lastStatus: new Map(store),
    lastStats: new Map(),
    subscribe: () => () => {},
    onResync: () => () => {},
  }),
}));

import { useMultiTrendModel, toEpochSeconds } from './useMultiTrendModel';

const sig = (value: number): FFSignal => ({
  value,
  severity: 'GOOD',
  limit_bits: '0',
  sub_status: 'NON_SPECIFIC',
});

// pv/sp/co arrive as FFSignal objects; timestamp is an ISO-8601 string in
// execute mode (pid_worker) and a numeric epoch in monitor mode (monitor_worker)
// — see realtime/envelope.ts.
const frame = (pv: number, ts: string | number): StatusData => ({
  pv: sig(pv),
  sp: sig(pv + 1),
  co: sig(50),
  bkcal_in: sig(0),
  bkcal_out: sig(0),
  mode: 'AUTO',
  kp: 1,
  ti: 1,
  td: 0,
  integral_val: 0,
  timestamp: ts,
});

const sec = (iso: string): number => Date.parse(iso) / 1000;

describe('toEpochSeconds', () => {
  it('returns a numeric epoch (monitor mode) unchanged', () => {
    expect(toEpochSeconds(1_750_000_000)).toBe(1_750_000_000);
  });

  it('parses an ISO-8601 string (execute mode) to epoch seconds', () => {
    expect(toEpochSeconds('2026-01-01T00:00:01Z')).toBe(
      Date.parse('2026-01-01T00:00:01Z') / 1000,
    );
  });

  it('returns NaN for unparseable input', () => {
    expect(Number.isNaN(toEpochSeconds('not-a-date'))).toBe(true);
  });
});

describe('useMultiTrendModel', () => {
  beforeEach(() => store.clear());

  it('accumulates selected loop frames into aligned series', () => {
    const { result, rerender } = renderHook(() =>
      useMultiTrendModel({ maxSeconds: 1e9, maxPoints: 1e9 }),
    );
    act(() => result.current.setSelection([{ loopId: 1, variable: 'pv' }]));
    act(() => result.current.setPxWidth(1000));

    const t1 = '2026-01-01T00:00:01Z';
    const t2 = '2026-01-01T00:00:02Z';
    store.set(1, frame(10, t1));
    rerender();
    store.set(1, frame(11, t2));
    rerender();

    expect(result.current.series.data[0]).toEqual([sec(t1), sec(t2)]);
    expect(result.current.series.data[1]).toEqual([10, 11]);
  });

  it('stops appending while paused', () => {
    const { result, rerender } = renderHook(() =>
      useMultiTrendModel({ maxSeconds: 1e9, maxPoints: 1e9 }),
    );
    act(() => result.current.setSelection([{ loopId: 1, variable: 'pv' }]));
    act(() => result.current.setPxWidth(1000));

    store.set(1, frame(10, '2026-01-01T00:00:01Z'));
    rerender();
    act(() => result.current.setPaused(true));
    store.set(1, frame(99, '2026-01-01T00:00:02Z'));
    rerender();

    expect(result.current.series.data[1]).toEqual([10]);
  });

  it('accumulates monitor-mode frames whose timestamp is a numeric epoch', () => {
    const { result, rerender } = renderHook(() =>
      useMultiTrendModel({ maxSeconds: 1e9, maxPoints: 1e9 }),
    );
    act(() => result.current.setSelection([{ loopId: 1, variable: 'pv' }]));
    act(() => result.current.setPxWidth(1000));

    // monitor_worker.py publishes time.time() -> a float epoch seconds NUMBER.
    const epoch = 1_750_000_000;
    store.set(1, frame(10, epoch));
    rerender();

    expect(result.current.series.data[0]).toEqual([epoch]);
    expect(result.current.series.data[1]).toEqual([10]);
  });

  it('de-dupes coalesced frames with an identical timestamp', () => {
    const { result, rerender } = renderHook(() =>
      useMultiTrendModel({ maxSeconds: 1e9, maxPoints: 1e9 }),
    );
    act(() => result.current.setSelection([{ loopId: 1, variable: 'pv' }]));
    act(() => result.current.setPxWidth(1000));

    const t1 = '2026-01-01T00:00:01Z';
    store.set(1, frame(10, t1));
    rerender();
    // Same timestamp (last-value coalesced re-delivery): must not append again.
    store.set(1, frame(12, t1));
    rerender();

    expect(result.current.series.data[0]).toEqual([sec(t1)]);
    expect(result.current.series.data[1]).toEqual([10]);
  });
});
