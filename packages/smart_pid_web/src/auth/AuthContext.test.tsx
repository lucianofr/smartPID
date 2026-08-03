import { act, render, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createElement, useEffect, type ReactNode } from 'react';
import { AuthProvider, useAuth } from './AuthContext';
import { api } from '../api/client';

const fetchMock = vi.fn();
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

beforeEach(() => {
  localStorage.clear();
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

    expect(localStorage.getItem('smart-pid-token')).toBe('t1');
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user).toEqual({ user_id: 1, username: 'admin', role: 'admin' });
    // the /auth/me request carried the fresh token
    const meInit = fetchMock.mock.calls[1][1] as RequestInit;
    expect((meInit.headers as Record<string, string>).Authorization).toBe('Bearer t1');
  });

  it('restores a stored session by refetching /auth/me on mount', async () => {
    localStorage.setItem('smart-pid-token', 't-stored');
    fetchMock.mockResolvedValueOnce(json({ user_id: 2, username: 'op', role: 'user' }));
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.user?.role).toBe('user'));
    expect(result.current.token).toBe('t-stored');
  });

  it('migrates a legacy sessionStorage token to localStorage on mount', async () => {
    sessionStorage.setItem('smart-pid-token', 't-legacy');
    fetchMock.mockResolvedValueOnce(json({ user_id: 2, username: 'op', role: 'user' }));
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.user?.role).toBe('user'));
    expect(result.current.token).toBe('t-legacy');
    expect(localStorage.getItem('smart-pid-token')).toBe('t-legacy');
    expect(sessionStorage.getItem('smart-pid-token')).toBeNull();
  });

  it('logout clears token, user and storage', async () => {
    localStorage.setItem('smart-pid-token', 't-stored');
    fetchMock.mockResolvedValueOnce(json({ user_id: 2, username: 'op', role: 'user' }));
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.user).not.toBeNull());

    act(() => result.current.logout());

    expect(result.current.token).toBeNull();
    expect(result.current.user).toBeNull();
    expect(localStorage.getItem('smart-pid-token')).toBeNull();
    expect(sessionStorage.getItem('smart-pid-token')).toBeNull();
  });

  it('a 401 from ANY api call clears the session (§11)', async () => {
    localStorage.setItem('smart-pid-token', 't-stored');
    fetchMock.mockResolvedValueOnce(json({ user_id: 2, username: 'op', role: 'user' }));
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.user).not.toBeNull());

    fetchMock.mockResolvedValueOnce(json({ detail: 'expired' }, 401));
    await act(async () => {
      await api.get('/controllers').catch(() => {});
    });

    await waitFor(() => expect(result.current.isAuthenticated).toBe(false));
    expect(localStorage.getItem('smart-pid-token')).toBeNull();
    expect(sessionStorage.getItem('smart-pid-token')).toBeNull();
  });

  it('a 403 refetches /auth/me and notifies onPermissionDenied (§11)', async () => {
    localStorage.setItem('smart-pid-token', 't-stored');
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

  it('wires setAuthHooks synchronously in render — a descendant mount effect never observes the pre-auth default (regression: Task 11 reload race)', async () => {
    // React commits a child's mount effects BEFORE its parent's. If
    // `setAuthHooks(...)` ever moves back into an AuthProvider `useEffect`,
    // a descendant's own mount effect fires first and races ahead of it —
    // exactly the window that caused the spurious reload-logout this test
    // guards against. Wiring the hooks in the render body (current fix)
    // guarantees they are live before React begins mounting any descendant,
    // regardless of effect order.
    localStorage.setItem('smart-pid-token', 't-race');
    fetchMock.mockImplementation((url: string) =>
      Promise.resolve(
        String(url).includes('/probe')
          ? json({ ok: true })
          : json({ user_id: 9, username: 'race', role: 'user' }),
      ),
    );

    function Consumer() {
      useEffect(() => {
        // Fires as a CHILD mount effect — the earliest point a descendant
        // can issue an authenticated request during a cold reload.
        void api.get('/probe');
      }, []);
      return null;
    }

    render(createElement(AuthProvider, null, createElement(Consumer)));

    await waitFor(() => {
      const probeCall = fetchMock.mock.calls.find(([url]) => String(url).includes('/probe'));
      expect(probeCall).toBeDefined();
    });
    const [, probeInit] = fetchMock.mock.calls.find(([url]) => String(url).includes('/probe'))!;
    const headers = (probeInit as RequestInit).headers as Record<string, string>;
    // The pre-auth default (`getToken: () => null`) sends no Authorization
    // header at all — that absence is what a reverted useEffect would produce.
    expect(headers.Authorization).toBe('Bearer t-race');
  });

  it('useAuth outside the provider throws', () => {
    expect(() => renderHook(() => useAuth())).toThrow(
      'useAuth must be used within AuthProvider',
    );
  });
});