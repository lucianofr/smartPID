import { renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createElement, type ReactNode } from 'react';
import { AuthProvider } from './AuthContext';
import { CAPABILITY_ACTIONS, can, useCan, type CapabilityAction } from './useCan';

describe('can — pure capability matrix', () => {
  const userAllowed: CapabilityAction[] = ['view', 'alarms.ack', 'loop.operate', 'export.data'];

  it('admin can do everything', () => {
    for (const action of CAPABILITY_ACTIONS) expect(can('admin', action)).toBe(true);
  });

  it('user gets exactly the four operate/observe capabilities', () => {
    for (const action of CAPABILITY_ACTIONS) {
      expect(can('user', action)).toBe(userAllowed.includes(action));
    }
  });

  it('unknown role (me not yet resolved) denies everything', () => {
    for (const action of CAPABILITY_ACTIONS) expect(can(null, action)).toBe(false);
  });

  it('the pinned action list matches spec §9 exactly', () => {
    expect(CAPABILITY_ACTIONS).toEqual([
      'view',
      'alarms.ack',
      'loop.operate',
      'export.data',
      'tuning.edit',
      'ai.control',
      'controllers.manage',
      'alarms.configure',
      'opcua.configure',
      'projects.manage',
      'users.manage',
      'settings.manage',
      'simulator.configure',
    ]);
  });

  it('scopes the twin: configuring the simulator is admin-only, operating it is not', () => {
    expect(can('admin', 'simulator.configure')).toBe(true);
    expect(can('user', 'simulator.configure')).toBe(false);
    expect(can('user', 'loop.operate')).toBe(true);
  });
});

describe('useCan — hook over AuthContext', () => {
  const fetchMock = vi.fn();
  beforeEach(() => {
    sessionStorage.clear();
    fetchMock.mockReset();
    vi.stubGlobal('fetch', fetchMock);
  });
  afterEach(() => vi.unstubAllGlobals());

  it('reflects the hydrated role', async () => {
    sessionStorage.setItem('smart-pid-token', 't');
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ user_id: 2, username: 'op', role: 'user' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    const wrapper = ({ children }: { children: ReactNode }) =>
      createElement(AuthProvider, null, children);
    const { result } = renderHook(
      () => ({ view: useCan('view'), users: useCan('users.manage') }),
      { wrapper },
    );
    await waitFor(() => expect(result.current.view).toBe(true));
    expect(result.current.users).toBe(false);
  });
});