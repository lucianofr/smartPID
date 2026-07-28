import { renderHook, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
import { queryKeys } from '@/api/queryKeys';
import { createQueryClient } from '@/test/providers';
import {
  useDeleteControllerMutation,
  useModeMutation,
  useOutputMutation,
  useSetpointMutation,
  useUpdateControllerMutation,
} from '../useCommands';

const fetchMock = vi.fn();

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function setup() {
  const queryClient = createQueryClient();
  const invalidate = vi.spyOn(queryClient, 'invalidateQueries');
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return { queryClient, invalidate, wrapper };
}

const requestBody = (call: number): unknown =>
  JSON.parse((fetchMock.mock.calls[call][1] as RequestInit).body as string);

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('loop command mutations', () => {
  it('posts the setpoint and invalidates the roster and the loop AI status', async () => {
    fetchMock.mockResolvedValue(json({ ok: true, controller_id: 5, detail: null }));
    const { invalidate, wrapper } = setup();
    const { result } = renderHook(() => useSetpointMutation(), { wrapper });

    result.current.mutate({ id: 5, value: 60 });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(fetchMock.mock.calls[0][0]).toBe('/api/commands/setpoint');
    expect(requestBody(0)).toEqual({ controller_id: 5, value: 60 });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.controllers });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.aiStatus(5) });
  });

  it('posts the mode with the enum value the backend expects', async () => {
    fetchMock.mockResolvedValue(json({ ok: true, controller_id: 5, detail: null }));
    const { wrapper } = setup();
    const { result } = renderHook(() => useModeMutation(), { wrapper });

    result.current.mutate({ id: 5, mode: 'MAN' });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(fetchMock.mock.calls[0][0]).toBe('/api/commands/mode');
    expect(requestBody(0)).toEqual({ controller_id: 5, mode: 'MAN' });
  });

  it('surfaces a 409 as a conflict without clearing the submitted variables', async () => {
    fetchMock.mockResolvedValue(json({ detail: 'malha em MAN' }, 409));
    const { wrapper } = setup();
    const { result } = renderHook(() => useOutputMutation(), { wrapper });

    result.current.mutate({ id: 5, value: 42 });
    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error?.kind).toBe('conflict');
    expect(result.current.error?.detail).toBe('malha em MAN');
    // §11: the caller keeps the form; the mutation still holds what was sent.
    expect(result.current.variables).toEqual({ id: 5, value: 42 });
  });

  it('maps a 422 onto per-field issues', async () => {
    fetchMock.mockResolvedValue(
      json({ detail: [{ loc: ['body', 'value'], msg: 'value must be <= 100', type: 'le' }] }, 422),
    );
    const { wrapper } = setup();
    const { result } = renderHook(() => useOutputMutation(), { wrapper });

    result.current.mutate({ id: 5, value: 900 });
    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error?.kind).toBe('validation');
    expect(result.current.error?.fields[0].loc).toEqual(['body', 'value']);
  });

  it('PUTs a controller patch', async () => {
    fetchMock.mockResolvedValue(json({ id: 5 }));
    const { wrapper } = setup();
    const { result } = renderHook(() => useUpdateControllerMutation(), { wrapper });

    result.current.mutate({ id: 5, patch: { name: 'PIC-005' } });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(fetchMock.mock.calls[0][0]).toBe('/api/controllers/5');
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('PUT');
  });

  it('drops the deleted loop AI status instead of refetching it', async () => {
    fetchMock.mockResolvedValue(json({ ok: true }));
    const { queryClient, wrapper } = setup();
    queryClient.setQueryData(queryKeys.aiStatus(5), { controller_id: 5 });
    const { result } = renderHook(() => useDeleteControllerMutation(), { wrapper });

    result.current.mutate(5);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('DELETE');
    expect(queryClient.getQueryData(queryKeys.aiStatus(5))).toBeUndefined();
  });
});
