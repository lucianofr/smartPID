import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider, useAuth } from './AuthContext';

afterEach(() => {
  vi.restoreAllMocks();
  sessionStorage.clear();
});

describe('AuthContext', () => {
  it('logs in and stores the token', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ access_token: 'jwt-123', token_type: 'bearer' }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    );
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    expect(result.current.isAuthenticated).toBe(false);
    await act(async () => {
      await result.current.login('admin', 'pw');
    });
    await waitFor(() => expect(result.current.isAuthenticated).toBe(true));
    expect(result.current.token).toBe('jwt-123');
  });

  it('throws ApiError on 401', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Invalid credentials' }), { status: 401 }),
    );
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await expect(result.current.login('admin', 'bad')).rejects.toThrow('Invalid credentials');
    expect(result.current.isAuthenticated).toBe(false);
  });
});
