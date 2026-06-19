import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as api from '../api';
import { useSimulatorStatus } from '../useSimulatorStatus';

vi.mock('../api');
vi.mock('../../../realtime/useRealtime', () => ({
  useRealtime: () => ({
    connected: true,
    lastStatus: new Map([[1, { pv: 55, sp: 50, co: 42, mode: 'AUTO' }]]),
    lastStats: new Map(),
    subscribe: () => () => {},
    onResync: () => () => {},
  }),
}));

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
};

beforeEach(() => vi.clearAllMocks());

describe('useSimulatorStatus', () => {
  it('returns REST config and live WS twin status', async () => {
    vi.mocked(api.getSimulatorStatus).mockResolvedValue({
      enabled: true, running: true,
      controllers: { 1: { preset: 'FLOW', gain: 1.2, tau1: 3, tau2: null, dead_time: 1 } as never },
    });
    const { result } = renderHook(() => useSimulatorStatus(), { wrapper });
    await waitFor(() => expect(result.current.data?.running).toBe(true));
    expect(result.current.live.get(1)?.co).toBe(42);
  });
});
