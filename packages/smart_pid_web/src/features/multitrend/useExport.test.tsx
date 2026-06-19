import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

const apiPost = vi.fn();
const apiGet = vi.fn();
vi.mock('../../api/client', () => ({
  apiPost: (...a: unknown[]) => apiPost(...a),
  apiGet: (...a: unknown[]) => apiGet(...a),
}));

import { useExport } from './useExport';

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe('useExport', () => {
  beforeEach(() => {
    apiPost.mockReset();
    apiGet.mockReset();
  });

  it('creates a job then polls until done and exposes the download href', async () => {
    apiPost.mockResolvedValue({
      id: 'abc',
      controller_id: 1,
      start: 's',
      end: 'e',
      format: 'csv',
      status: 'running',
      progress: 0,
      file_path: null,
    });
    apiGet
      .mockResolvedValueOnce({
        id: 'abc',
        controller_id: 1,
        start: 's',
        end: 'e',
        format: 'csv',
        status: 'running',
        progress: 40,
        file_path: null,
      })
      .mockResolvedValue({
        id: 'abc',
        controller_id: 1,
        start: 's',
        end: 'e',
        format: 'csv',
        status: 'done',
        progress: 100,
        file_path: '/tmp/x.csv',
      });

    const { result } = renderHook(() => useExport(), { wrapper });
    act(() => result.current.start({ controller_id: 1, start: 's', end: 'e', format: 'csv' }));

    await waitFor(() => expect(result.current.phase).toBe('done'), { timeout: 3000 });
    expect(apiPost).toHaveBeenCalledWith('/export', {
      controller_id: 1,
      start: 's',
      end: 'e',
      format: 'csv',
    });
    expect(result.current.downloadHref).toBe('/api/export/abc/download');
  });

  it('surfaces an error phase when the job fails', async () => {
    apiPost.mockResolvedValue({
      id: 'z',
      controller_id: 1,
      start: 's',
      end: 'e',
      format: 'csv',
      status: 'running',
      progress: 0,
      file_path: null,
    });
    apiGet.mockResolvedValue({
      id: 'z',
      controller_id: 1,
      start: 's',
      end: 'e',
      format: 'csv',
      status: 'error',
      progress: 0,
      file_path: null,
    });
    const { result } = renderHook(() => useExport(), { wrapper });
    act(() => result.current.start({ controller_id: 1, start: 's', end: 'e', format: 'csv' }));
    await waitFor(() => expect(result.current.phase).toBe('error'), { timeout: 3000 });
    expect(result.current.downloadHref).toBeNull();
  });
});
