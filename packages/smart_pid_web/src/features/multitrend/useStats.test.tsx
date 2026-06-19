import { describe, it, expect, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import type { StatsData } from '../../realtime/envelope';

vi.mock('../../api/client', () => ({
  apiGet: vi.fn(async (path: string) => {
    if (path === '/controllers/stats') {
      return [
        {
          controller_id: 1,
          iae: 1,
          itae: 2,
          ise: 3,
          mse: 4,
          std_dev: 5,
          total_variation: 6,
          variability_range: 0.1,
          variability_sp: 0.2,
        },
      ];
    }
    throw new Error(`unexpected ${path}`);
  }),
}));

const lastStats = new Map<number, StatsData>();
vi.mock('../../realtime/useRealtime', () => ({
  useRealtime: () => ({
    connected: true,
    lastStatus: new Map(),
    lastStats,
    subscribe: () => () => {},
    onResync: () => () => {},
  }),
}));

import { useStats } from './useStats';

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe('useStats', () => {
  it('seeds rows from REST and overlays live lastStats', async () => {
    // Live frame for loop 1 overrides the REST seed (iae 1 -> 99).
    lastStats.set(1, {
      controller_id: 1,
      iae: 99,
      itae: 2,
      ise: 3,
      mse: 4,
      std_dev: 5,
      total_variation: 6,
      variability_range: 0.1,
      variability_sp: 0.2,
    });
    const { result } = renderHook(() => useStats(), { wrapper });
    await waitFor(() => expect(result.current.rows.length).toBe(1));
    // live value wins over the REST seed
    expect(result.current.rows[0].iae).toBe(99);
    expect(result.current.rows[0].loopId).toBe(1);
  });
});
