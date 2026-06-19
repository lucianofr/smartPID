import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, within, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AlarmBar } from '../AlarmBar';
import * as client from '../../../api/client';
import type { ActiveAlarm } from '../types';

vi.mock('../../../api/client');
vi.mock('../../../realtime/useRealtime', () => ({
  useRealtime: () => ({ connected: true, lastStatus: new Map(), lastStats: new Map(),
    subscribe: () => () => {}, onResync: () => () => {} }),
}));

function mk(over: Partial<ActiveAlarm>): ActiveAlarm {
  return { id: 1, controller_id: 7, controller_name: 'FIC-101', alarm_type: 'HI',
    priority: 'WARNING', value: 80, limit: 75, timestamp: '2026-06-18T10:00:00Z',
    cleared_at: null, acknowledged: 0, ack_by_user: null, ack_at: null,
    status: 'UNACKNOWLEDGED', ...over };
}

function renderBar(rows: ActiveAlarm[]) {
  vi.spyOn(client, 'apiGet').mockResolvedValue(rows);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><AlarmBar /></QueryClientProvider>);
}

beforeEach(() => vi.clearAllMocks());

describe('AlarmBar', () => {
  it('shows counts per priority bucket', async () => {
    renderBar([
      mk({ id: 1, priority: 'CRITICAL' }),
      mk({ id: 2, priority: 'CRITICAL' }),
      mk({ id: 3, priority: 'WARNING' }),
      mk({ id: 4, priority: 'ADVISORY' }),
    ]);
    expect(await within(await screen.findByTestId('count-critical')).findByText('2')).toBeInTheDocument();
    expect(within(screen.getByTestId('count-warning')).getByText('1')).toBeInTheDocument();
    expect(within(screen.getByTestId('count-advisory')).getByText('1')).toBeInTheDocument();
  });

  it('marks a bucket as blinking when it has unacked alarms', async () => {
    renderBar([mk({ id: 1, priority: 'CRITICAL', status: 'UNACKNOWLEDGED' })]);
    // Wait for the count to populate (data resolves async); only then is is-unacked set.
    expect(await within(await screen.findByTestId('count-critical')).findByText('1')).toBeInTheDocument();
    expect(screen.getByTestId('count-critical')).toHaveClass('is-unacked');
  });

  it('does not blink a bucket whose alarms are all acknowledged', async () => {
    renderBar([mk({ id: 1, priority: 'CRITICAL', status: 'ACKNOWLEDGED', acknowledged: 1 })]);
    expect(await within(await screen.findByTestId('count-critical')).findByText('1')).toBeInTheDocument();
    expect(screen.getByTestId('count-critical')).not.toHaveClass('is-unacked');
  });

  it('triggers ack-all → POST /alarms/ack-all', async () => {
    const post = vi.spyOn(client, 'apiPost').mockResolvedValue({ status: 'acknowledged', acknowledged_count: 1, controller_ids: [7] });
    renderBar([mk({ id: 1, priority: 'CRITICAL' })]);
    fireEvent.click(await screen.findByRole('button', { name: /ack all/i }));
    await waitFor(() => expect(post).toHaveBeenCalledWith('/alarms/ack-all'));
  });
});
