import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { AppShell } from '../AppShell';
import * as client from '../../../api/client';

// AppShell now mounts <AlarmBar/>, which uses useActiveAlarms (QueryClientProvider)
// and useAlarmRealtimeSync (useRealtime context) — supply/mocked here.
vi.mock('../../../api/client');
vi.mock('../../../realtime/useRealtime', () => ({
  useRealtime: () => ({ connected: true, lastStatus: new Map(), lastStats: new Map(),
    subscribe: () => () => {}, onResync: () => () => {} }),
}));

beforeEach(() => vi.clearAllMocks());

describe('AppShell', () => {
  it('renders the persistent alarm summary bar', () => {
    vi.spyOn(client, 'apiGet').mockResolvedValue([]);
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <AppShell opcDown={false}>
            <div>page</div>
          </AppShell>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.getByLabelText('Alarm summary')).toBeInTheDocument();
  });
});
