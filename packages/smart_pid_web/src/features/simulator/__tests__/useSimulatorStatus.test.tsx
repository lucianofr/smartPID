import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/api/client';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import type { Role, SimulatorStatus } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { createQueryClient, TestProviders } from '@/test/providers';
import { useSimulatorStatus, useTwinRunning } from '../useSimulatorStatus';

/**
 * GET /simulator/status is ADMIN-ONLY (pinned by the backend RBAC contract
 * test). A `user` session must therefore reach a DESIGNED restricted state —
 * not a crash, not a "sem permissão" toast on every visit, and above all not a
 * 403 that recycles the realtime socket.
 */

const SNAPSHOT: SimulatorStatus = { enabled: true, running: true, controllers: {} };

function renderStatus(role: Role) {
  localStorage.setItem('smart-pid-token', 'jwt');
  vi.spyOn(endpoints, 'me').mockResolvedValue({ user_id: 1, username: role, role });
  const queryClient = createQueryClient();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <TestProviders queryClient={queryClient}>{children}</TestProviders>
  );
  // `user` rides along so a test can wait for GET /auth/me to land before
  // asserting on what the role-gated query did (or did not) do.
  return renderHook(() => ({ status: useSimulatorStatus(), user: useAuth().user }), { wrapper });
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});
afterEach(() => vi.restoreAllMocks());

describe('useSimulatorStatus', () => {
  it('serves the snapshot to an administrator', async () => {
    const status = vi.spyOn(endpoints, 'simulatorStatus').mockResolvedValue(SNAPSHOT);
    const { result } = renderStatus('admin');
    await waitFor(() => expect(result.current.status.data).toEqual(SNAPSHOT));
    expect(result.current.status.restricted).toBe(false);
    expect(status).toHaveBeenCalled();
  });

  it('never calls the admin-only route for a user, and reports restricted', async () => {
    const status = vi.spyOn(endpoints, 'simulatorStatus').mockResolvedValue(SNAPSHOT);
    const { result } = renderStatus('user');
    await waitFor(() => expect(result.current.user?.role).toBe('user'));
    expect(status).not.toHaveBeenCalled();
    expect(result.current.status.restricted).toBe(true);
    expect(result.current.status.data).toBeUndefined();
    expect(result.current.status.isPending).toBe(false);
  });

  it('degrades a 403 into the same restricted state instead of an error, once', async () => {
    const status = vi
      .spyOn(endpoints, 'simulatorStatus')
      .mockRejectedValue(new ApiError(403, 'forbidden', 'Admin role required'));
    const { result } = renderStatus('admin');
    // Deny-by-default makes `restricted` momentarily true before /auth/me
    // lands, so settle on the resolved role AND a finished query first.
    await waitFor(() => {
      expect(result.current.user?.role).toBe('admin');
      expect(result.current.status.isPending).toBe(false);
    });
    expect(result.current.status.restricted).toBe(true);
    // retry:false — a rejected admin-only poll must not turn into a retry storm.
    expect(status).toHaveBeenCalledTimes(1);
  });

  it('keeps a genuine server failure distinguishable from a permission wall', async () => {
    vi.spyOn(endpoints, 'simulatorStatus').mockRejectedValue(new ApiError(500, 'server', 'boom'));
    const { result } = renderStatus('admin');
    await waitFor(() => {
      expect(result.current.user?.role).toBe('admin');
      expect(result.current.status.isPending).toBe(false);
    });
    expect(result.current.status.restricted).toBe(false);
    expect(result.current.status.data).toBeUndefined();
  });
});

describe('useTwinRunning — ambient cache read', () => {
  it('reads the entry the §7 resync primes without issuing its own request', async () => {
    localStorage.setItem('smart-pid-token', 'jwt');
    vi.spyOn(endpoints, 'me').mockResolvedValue({ user_id: 1, username: 'admin', role: 'admin' });
    const status = vi.spyOn(endpoints, 'simulatorStatus').mockResolvedValue(SNAPSHOT);
    const queryClient = createQueryClient();
    const wrapper = ({ children }: { children: ReactNode }) => (
      <TestProviders queryClient={queryClient}>{children}</TestProviders>
    );
    const { result } = renderHook(() => useTwinRunning(), { wrapper });

    expect(result.current).toBe(false);
    queryClient.setQueryData(queryKeys.simulatorStatus, SNAPSHOT);
    await waitFor(() => expect(result.current).toBe(true));
    expect(status).not.toHaveBeenCalled();
  });
});
