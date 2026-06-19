import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useAiAction, useAiStatus, useTuningRecommendation } from '../useAiControls';

vi.mock('../../../api/client', () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

import { apiGet, apiPost } from '../../../api/client';

const apiGetMock = vi.mocked(apiGet);
const apiPostMock = vi.mocked(apiPost);

function makeWrapper(): ({ children }: { children: ReactNode }) => JSX.Element {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

describe('useAiControls', () => {
  beforeEach(() => {
    apiGetMock.mockReset();
    apiPostMock.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('useAiAction', () => {
    it.each(['start', 'stop', 'pause'] as const)(
      'posts to /controllers/{id}/ai/%s',
      async (action) => {
        apiPostMock.mockResolvedValue({ ok: true });
        const { result } = renderHook(() => useAiAction(), { wrapper: makeWrapper() });

        result.current.mutate({ id: 3, action });

        await waitFor(() => expect(result.current.isSuccess).toBe(true));
        expect(apiPostMock).toHaveBeenCalledWith('/controllers/3/ai/' + action, {});
      },
    );
  });

  describe('useAiStatus', () => {
    it('calls apiGet on /controllers/{id}/ai/status', async () => {
      apiGetMock.mockResolvedValue({
        controller_id: 3,
        engine: 'fuzzy',
        objective: 'sp_tracking',
        speed: 'medium',
        current_ki: 0.5,
        last_gamma: null,
        enabled: true,
      });
      const { result } = renderHook(() => useAiStatus(3), { wrapper: makeWrapper() });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(apiGetMock).toHaveBeenCalledWith('/controllers/3/ai/status');
    });
  });

  describe('useTuningRecommendation', () => {
    it('fetches the pending recommendation for the loop', async () => {
      apiGetMock.mockResolvedValue({
        controller_id: 3,
        current_kp: 1,
        current_ti: 10,
        current_td: 0,
        recommended_kp: 1.2,
        recommended_ti: 9,
        recommended_td: 0,
        reason: 'iae improvement',
        timestamp: 1,
        status: 'pending',
        source: 'fuzzy',
      });
      const { result } = renderHook(() => useTuningRecommendation(3), {
        wrapper: makeWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(apiGetMock).toHaveBeenCalledWith('/commands/tuning-recommendations/3');
    });
  });
});
