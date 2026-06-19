import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createElement, type ReactNode } from 'react';
import { RealtimeProvider } from './RealtimeProvider';
import { useRealtime } from './useRealtime';

class MockWS {
  static instances: MockWS[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  sent: string[] = [];
  readyState = 0;
  constructor(public url: string) {
    MockWS.instances.push(this);
  }
  send(d: string) { this.sent.push(d); }
  close() { this.readyState = 3; this.onclose?.(); }
  _open() { this.readyState = 1; this.onopen?.(); }
  _emit(obj: unknown) { this.onmessage?.({ data: JSON.stringify(obj) }); }
}

beforeEach(() => {
  MockWS.instances = [];
  vi.stubGlobal('WebSocket', MockWS as unknown as typeof WebSocket);
});
afterEach(() => vi.unstubAllGlobals());

const wrapper = ({ children }: { children: ReactNode }) =>
  createElement(RealtimeProvider, { token: 'jwt-123' }, children);

describe('useRealtime', () => {
  it('connects and sends first-frame auth', async () => {
    renderHook(() => useRealtime(), { wrapper });
    const ws = MockWS.instances[0];
    act(() => ws._open());
    expect(JSON.parse(ws.sent[0])).toEqual({ type: 'auth', token: 'jwt-123' });
  });

  it('parses a status envelope into lastStatus keyed by loop_id', async () => {
    const { result } = renderHook(() => useRealtime(), { wrapper });
    const ws = MockWS.instances[0];
    act(() => ws._open());
    act(() =>
      ws._emit({ type: 'status', loop_id: 5, seq: 1, ts: 1, data: { pv: 42 } }),
    );
    await waitFor(() => expect(result.current.lastStatus.get(5)?.pv).toBe(42));
  });

  it('delivers discrete alarm events to subscribers', async () => {
    const { result } = renderHook(() => useRealtime(), { wrapper });
    const ws = MockWS.instances[0];
    act(() => ws._open());
    const seen: unknown[] = [];
    act(() => {
      result.current.subscribe('alarm', (env) => seen.push(env.data));
    });
    act(() => ws._emit({ type: 'alarm', loop_id: 9, seq: 1, ts: 1, data: { alarm_id: 'a' } }));
    await waitFor(() => expect(seen).toEqual([{ alarm_id: 'a' }]));
  });
});
