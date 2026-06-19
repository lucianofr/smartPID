import { describe, it, expect, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

const apiGet = vi.fn(async () => ({
  controller_id: 7,
  frames: [{ timestamp: '2026-06-18T00:00:00Z', pv: 1, sp: 2, co: 3, mode: 'AUTO', status: 'GOOD' }],
  count: 1,
}));
vi.mock('../../api/client', () => ({ apiGet: (...a: unknown[]) => apiGet(...a) }));

import { useHistory } from './useHistory';

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe('useHistory', () => {
  it('calls /history/{id} with controller_id in the PATH and window in the query string', async () => {
    const { result } = renderHook(
      () => useHistory({ controllerId: 7, start: '2026-06-18T00:00:00Z', end: '2026-06-18T01:00:00Z', limit: 500 }),
      { wrapper },
    );
    await waitFor(() => expect(result.current.count).toBe(1));
    const calledPath = apiGet.mock.calls[0][0] as string;
    expect(calledPath).toMatch(/^\/history\/7\?/);
    expect(calledPath).toContain('start=2026-06-18T00%3A00%3A00Z');
    expect(calledPath).toContain('end=2026-06-18T01%3A00%3A00Z');
    expect(calledPath).toContain('limit=500');
    expect(result.current.frames[0].pv).toBe(1);
  });

  it('is disabled when params is null (no controller selected)', () => {
    const { result } = renderHook(() => useHistory(null), { wrapper });
    expect(result.current.isLoading).toBe(false);
    expect(result.current.count).toBe(0);
  });
});
