import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createElement, type ReactNode } from 'react';
import { AuthProvider, useAuth } from './AuthContext';
import { api } from '../api/client';

const fetchMock = vi.fn();
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

beforeEach(() => {
  sessionStorage.clear();
  fetchMock.mockReset();
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

const wrapper = ({ children }: { children: ReactNode }) =>
  createElement(AuthProvider, null, children);

describe('AuthProvider', () => {
  it('login stores the token and hydrates user from /auth/me', async () => {
    fetchMock
      .mockResolvedValueOnce(json({ access_token: 't1', token_type: 'bearer' }))
      .mockResolvedValueOnce(json({ user_id: 1, username: 'admin', role: 'admin' }));
    const { result } = renderHook(() => useAuth(), { wrapper });

    await act(() => result.current.login('admin', 'admin'));

    expect(sessionStorage.getItem('smart-pid-token')).toBe('t1');
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user).toEqual({ user_id: 1, username: 'admin', role: 'admin' });
    // the /auth/me request carried the fresh token
    const meInit = fetchMock.mock.calls[1][1] as RequestInit;
    expect((meInit.headers as Record<string, string>).Authorization).toBe('Bearer t1');
  });

  it('restores a stored session by refetching /auth/me on mount', async () => {
    sessionStorage.setItem('smart-pid-token', 't-stored');
    fetchMock.mockResolvedValueOnce(json({ user_id: 2, username: 'op', role: 'user' }));
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.user?.role).toBe('user'));
    expect(result.current.token).toBe('t-stored');
  });

  it('logout clears token, user and storage', async () => {
    sessionStorage.setItem('smart-pid-token', 't-stored');
    fetchMock.mockResolvedValueOnce(json({ user_id: 2, username: 'op', role: 'user' }));
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.user).not.toBeNull());

    act(() => result.current.logout());

    expect(result.current.token).toBeNull();
    expect(result.current.user).toBeNull();
    expect(sessionStorage.getItem('smart-pid-token')).toBeNull();
  });

  it('a 401 from ANY api call clears the session (§11)', async () => {
    sessionStorage.setItem('smart-pid-token', 't-stored');
    fetchMock.mockResolvedValueOnce(json({ user_id: 2, username: 'op', role: 'user' }));
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.user).not.toBeNull());

    fetchMock.mockResolvedValueOnce(json({ detail: 'expired' }, 401));
    await act(async () => {
      await api.get('/controllers').catch(() => {});
    });

    await waitFor(() => expect(result.current.isAuthenticated).toBe(false));
    expect(sessionStorage.getItem('smart-pid-token')).toBeNull();
  });

  it('a 403 refetches /auth/me and notifies onPermissionDenied (§11)', async () => {
    sessionStorage.setItem('smart-pid-token', 't-stored');
    const onPermissionDenied = vi.fn();
    fetchMock.mockResolvedValueOnce(json({ user_id: 2, username: 'op', role: 'admin' }));
    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }: { children: ReactNode }) =>
        createElement(AuthProvider, { onPermissionDenied }, children),
    });
    await waitFor(() => expect(result.current.user?.role).toBe('admin'));

    // role was downgraded server-side; the next call 403s, me now reports 'user'
    fetchMock
      .mockResolvedValueOnce(json({ detail: 'sem permissão' }, 403))
      .mockResolvedValueOnce(json({ user_id: 2, username: 'op', role: 'user' }));
    await act(async () => {
      await api.post('/controllers', {}).catch(() => {});
    });

    await waitFor(() => expect(result.current.user?.role).toBe('user'));
    expect(onPermissionDenied).toHaveBeenCalledTimes(1);
  });

  it('useAuth outside the provider throws', () => {
    expect(() => renderHook(() => useAuth())).toThrow(
      'useAuth must be used within AuthProvider',
    );
  });
});