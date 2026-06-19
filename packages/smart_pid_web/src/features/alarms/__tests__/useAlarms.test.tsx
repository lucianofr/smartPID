import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { useActiveAlarms, useAckAlarm, useAckAllAlarms, useAlarmRealtimeSync } from '../useAlarms';
import * as client from '../../../api/client';

vi.mock('../../../api/client');

const rows = [
  { id: 1, controller_id: 7, controller_name: 'FIC-101', alarm_type: 'HIHI',
    priority: 'CRITICAL', value: 99, limit: 90, timestamp: '2026-06-18T10:00:00Z',
    cleared_at: null, acknowledged: 0, ack_by_user: null, ack_at: null, status: 'UNACKNOWLEDGED' },
];

function wrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return { qc, Wrapper: ({ children }: { children: ReactNode }) =>
    <QueryClientProvider client={qc}>{children}</QueryClientProvider> };
}

const subscribers: Record<string, ((env: unknown) => void)[]> = {};
vi.mock('../../../realtime/useRealtime', () => ({
  useRealtime: () => ({
    connected: true,
    lastStatus: new Map(),
    lastStats: new Map(),
    subscribe: (type: string, handler: (env: unknown) => void) => {
      (subscribers[type] ??= []).push(handler);
      return () => { subscribers[type] = subscribers[type].filter((h) => h !== handler); };
    },
    onResync: () => () => {},
  }),
}));

beforeEach(() => {
  vi.clearAllMocks();
  for (const k of Object.keys(subscribers)) delete subscribers[k];
});

describe('useActiveAlarms', () => {
  it('fetches GET /alarms/active and returns rows', async () => {
    vi.spyOn(client, 'apiGet').mockResolvedValue(rows);
    const { Wrapper } = wrapper();
    const { result } = renderHook(() => useActiveAlarms(), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.apiGet).toHaveBeenCalledWith('/alarms/active');
    expect(result.current.data?.[0].status).toBe('UNACKNOWLEDGED');
  });
});

describe('useAckAlarm', () => {
  it('POSTs /alarms/{id}/ack and invalidates the active query', async () => {
    vi.spyOn(client, 'apiGet').mockResolvedValue(rows);
    vi.spyOn(client, 'apiPost').mockResolvedValue({ status: 'acknowledged' });
    const { qc, Wrapper } = wrapper();
    const spy = vi.spyOn(qc, 'invalidateQueries');
    const { result } = renderHook(() => useAckAlarm(), { wrapper: Wrapper });
    await act(async () => { await result.current.mutateAsync(1); });
    expect(client.apiPost).toHaveBeenCalledWith('/alarms/1/ack');
    expect(spy).toHaveBeenCalledWith({ queryKey: ['alarms', 'active'] });
  });
});

describe('useAckAllAlarms', () => {
  it('POSTs /alarms/ack-all and invalidates the active query', async () => {
    vi.spyOn(client, 'apiPost').mockResolvedValue({ status: 'acknowledged', acknowledged_count: 3, controller_ids: [7] });
    const { qc, Wrapper } = wrapper();
    const spy = vi.spyOn(qc, 'invalidateQueries');
    const { result } = renderHook(() => useAckAllAlarms(), { wrapper: Wrapper });
    await act(async () => { await result.current.mutateAsync(); });
    expect(client.apiPost).toHaveBeenCalledWith('/alarms/ack-all');
    expect(spy).toHaveBeenCalledWith({ queryKey: ['alarms', 'active'] });
  });
});

describe('useAlarmRealtimeSync', () => {
  it('invalidates active alarms when a WS alarm event arrives (trigger-only payload)', async () => {
    vi.spyOn(client, 'apiGet').mockResolvedValue(rows);
    const { qc, Wrapper } = wrapper();
    const spy = vi.spyOn(qc, 'invalidateQueries');
    renderHook(() => useAlarmRealtimeSync(), { wrapper: Wrapper });
    act(() => {
      subscribers['alarm']?.forEach((h) => h({ type: 'alarm', loop_id: 7, seq: 1, ts: 0,
        data: { controller_id: 7, alarm_type: 'HIHI', priority: 'CRITICAL', transition: 'raised' } }));
    });
    expect(spy).toHaveBeenCalledWith({ queryKey: ['alarms', 'active'] });
  });
});
