import { render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { endpoints } from '@/api/endpoints';
import type { AccessLogRow, ActiveSessionRow, Role } from '@/api/types';
import { createQueryClient, TestProviders } from '@/test/providers';
import { SessionsPanel } from './SessionsPanel';

const CONNECTED: ActiveSessionRow = {
  user_id: 1,
  username: 'supervisora',
  role: 'admin',
  ip: '203.0.113.9',
  since: '2026-08-06T11:05:00+00:00',
  last_seen: '2026-08-06T11:42:07+00:00',
  online: true,
};
const IDLE: ActiveSessionRow = {
  user_id: 2,
  username: 'operador',
  role: 'user',
  ip: '198.51.100.7',
  since: '2026-08-06T09:00:00+00:00',
  last_seen: '2026-08-06T11:40:00+00:00',
  online: false,
};

const LOGIN: AccessLogRow = {
  id: 9,
  user_id: 2,
  username: 'operador',
  event: 'LOGIN',
  ip: '198.51.100.7',
  timestamp: '2026-08-06T09:00:00+00:00',
};
const LOGOUT: AccessLogRow = {
  id: 10,
  user_id: 3,
  username: 'antigo',
  event: 'LOGOUT',
  ip: '10.0.0.4',
  timestamp: '2026-08-05T17:30:00+00:00',
};

function renderPanel({
  role = 'admin' as Role,
  sessions = [CONNECTED, IDLE],
  log = [LOGOUT, LOGIN],
}: {
  role?: Role;
  sessions?: ActiveSessionRow[];
  log?: AccessLogRow[];
} = {}) {
  localStorage.setItem('smart-pid-token', 'jwt');
  vi.spyOn(endpoints, 'me').mockResolvedValue({ user_id: 1, username: role, role });
  const live = vi.spyOn(endpoints, 'activeSessions').mockResolvedValue(sessions);
  const history = vi.spyOn(endpoints, 'accessLog').mockResolvedValue(log);
  render(
    <TestProviders queryClient={createQueryClient()}>
      <SessionsPanel />
    </TestProviders>,
  );
  return { live, history };
}

/**
 * Both tables can name the same operator, so every query is scoped to one of
 * them by its caption. An unscoped `getByRole('cell')` is ambiguous here — and
 * that ambiguity is the point of the panel: the same person can be connected
 * now AND present in the history.
 */
const liveTable = () => screen.findByRole('table', { name: 'Sessões ativas' });
const logTable = () => screen.findByRole('table', { name: 'Histórico de acesso' });

const rowIn = (table: HTMLElement, name: string) =>
  within(within(table).getByRole('row', { name: new RegExp(name) }));

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('SessionsPanel', () => {
  it('lists each connected user with role, source address and activity', async () => {
    renderPanel();
    const live = await liveTable();

    const connected = rowIn(live, 'supervisora');
    expect(connected.getByText('203.0.113.9')).toBeVisible();
    expect(connected.getByText('admin')).toBeVisible();
    expect(connected.getByText('Aberta')).toBeVisible();

    const idle = rowIn(live, 'operador');
    expect(idle.getByText('198.51.100.7')).toBeVisible();
    expect(idle.getByText('user')).toBeVisible();
    expect(idle.getByText('Ociosa')).toBeVisible();
  });

  it('dates every log row, because the history spans days', async () => {
    renderPanel();
    // Local wall clock of 2026-08-05T17:30Z; the date is what makes a row from
    // yesterday distinguishable from one at the same time today.
    const stamp = new Date('2026-08-05T17:30:00+00:00');
    const pad = (n: number) => String(n).padStart(2, '0');
    const expected = `${pad(stamp.getDate())}/${pad(stamp.getMonth() + 1)}/${stamp.getFullYear()}`;

    expect(rowIn(await logTable(), 'antigo').getByText(new RegExp(expected))).toBeVisible();
  });

  it('names the sign-in events in the operator language and keeps their address', async () => {
    renderPanel();
    const log = await logTable();

    expect(rowIn(log, 'operador').getByText('Entrada')).toBeVisible();
    expect(rowIn(log, 'antigo').getByText('Saída')).toBeVisible();
    expect(rowIn(log, 'antigo').getByText('10.0.0.4')).toBeVisible();
  });

  it('prints an unknown event verbatim rather than dropping the row', async () => {
    renderPanel({ log: [{ ...LOGIN, event: 'IMPERSONATE' }] });
    expect(await screen.findByText('IMPERSONATE')).toBeVisible();
  });

  it('shows a designed empty state instead of a bare table', async () => {
    renderPanel({ sessions: [], log: [] });
    expect(await screen.findByText('Nenhuma sessão ativa.')).toBeVisible();
    expect(screen.getByText('Nenhum acesso registrado.')).toBeVisible();
  });

  it('never fetches session data for a non-admin session', async () => {
    const { live, history } = renderPanel({ role: 'user' });
    // Wait for the session to actually resolve as `user`: before /auth/me
    // lands `useCan` is false for everybody, so asserting immediately would
    // pass even if the gate were missing.
    await waitFor(() => expect(endpoints.me).toHaveBeenCalled());

    expect(live).not.toHaveBeenCalled();
    expect(history).not.toHaveBeenCalled();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });
});
