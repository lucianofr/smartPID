import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, within, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AlarmPanel } from '../AlarmPanel';
import * as client from '../../../api/client';
import type { ActiveAlarm } from '../types';

vi.mock('../../../api/client');
vi.mock('../../../realtime/useRealtime', () => ({
  useRealtime: () => ({ connected: true, lastStatus: new Map(), lastStats: new Map(),
    subscribe: () => () => {}, onResync: () => () => {} }),
}));

// jsdom has no layout: offsetWidth/offsetHeight are 0 and ResizeObserver is absent,
// so @tanstack/react-virtual measures a zero-height viewport and renders no rows.
// Give the scroll element a real (non-zero) size so the virtualizer renders the
// (<=4) test rows; the ResizeObserver polyfill lives in src/test/setup.ts.
const offsetWidthSpy = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetWidth');
const offsetHeightSpy = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetHeight');

beforeEach(() => {
  vi.clearAllMocks();
  Object.defineProperty(HTMLElement.prototype, 'offsetWidth', { configurable: true, value: 600 });
  Object.defineProperty(HTMLElement.prototype, 'offsetHeight', { configurable: true, value: 600 });
});

afterEach(() => {
  if (offsetWidthSpy) Object.defineProperty(HTMLElement.prototype, 'offsetWidth', offsetWidthSpy);
  if (offsetHeightSpy) Object.defineProperty(HTMLElement.prototype, 'offsetHeight', offsetHeightSpy);
});

function mk(over: Partial<ActiveAlarm>): ActiveAlarm {
  return { id: 1, controller_id: 7, controller_name: 'FIC-101', alarm_type: 'HI',
    priority: 'WARNING', value: 80, limit: 75, timestamp: '2026-06-18T10:00:00Z',
    cleared_at: null, acknowledged: 0, ack_by_user: null, ack_at: null,
    status: 'UNACKNOWLEDGED', ...over };
}

function renderPanel(rows: ActiveAlarm[]) {
  vi.spyOn(client, 'apiGet').mockResolvedValue(rows);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}><AlarmPanel /></QueryClientProvider>,
  );
}

describe('AlarmPanel', () => {
  it('renders a row per active alarm with severity text, type, state and a row ack button', async () => {
    renderPanel([mk({ id: 1, priority: 'CRITICAL', alarm_type: 'HIHI', status: 'UNACKNOWLEDGED' })]);
    const row = await screen.findByTestId('alarm-row-1');
    expect(within(row).getByText('CRITICAL')).toBeInTheDocument();
    expect(within(row).getByText('HIHI')).toBeInTheDocument();
    expect(within(row).getByText('UNACKNOWLEDGED')).toBeInTheDocument();
    expect(within(row).getByRole('button', { name: /ack/i })).toBeInTheDocument();
  });

  it('dedupes rows by id (flood with repeated ids → one row each)', async () => {
    renderPanel([
      mk({ id: 1 }), mk({ id: 1 }), mk({ id: 1 }), mk({ id: 2 }),
    ]);
    await screen.findByTestId('alarm-row-1');
    expect(screen.getByTestId('alarm-row-1')).toBeInTheDocument();
    expect(screen.getByTestId('alarm-row-2')).toBeInTheDocument();
    expect(screen.queryAllByTestId(/alarm-row-/)).toHaveLength(2);
  });

  it('sorts by severity (CRITICAL above WARNING) by default', async () => {
    renderPanel([
      mk({ id: 5, priority: 'WARNING' }),
      mk({ id: 9, priority: 'CRITICAL', alarm_type: 'HIHI' }),
    ]);
    await screen.findByTestId('alarm-row-9');
    const rows = screen.getAllByTestId(/alarm-row-/);
    expect(rows[0]).toHaveAttribute('data-testid', 'alarm-row-9'); // CRITICAL first
  });

  it('filters the list by state', async () => {
    renderPanel([
      mk({ id: 1, status: 'UNACKNOWLEDGED' }),
      mk({ id: 2, status: 'ACKNOWLEDGED', acknowledged: 1, ack_by_user: 'admin' }),
    ]);
    await screen.findByTestId('alarm-row-1');
    fireEvent.change(screen.getByLabelText(/filter.*state/i), { target: { value: 'ACKNOWLEDGED' } });
    expect(screen.queryByTestId('alarm-row-1')).not.toBeInTheDocument();
    expect(screen.getByTestId('alarm-row-2')).toBeInTheDocument();
  });

  it('acks a single row → POST /alarms/{id}/ack', async () => {
    const post = vi.spyOn(client, 'apiPost').mockResolvedValue({ status: 'acknowledged' });
    renderPanel([mk({ id: 42, status: 'UNACKNOWLEDGED' })]);
    const row = await screen.findByTestId('alarm-row-42');
    fireEvent.click(within(row).getByRole('button', { name: /ack/i }));
    await waitFor(() => expect(post).toHaveBeenCalledWith('/alarms/42/ack'));
  });

  it('acks all alarms → POST /alarms/ack-all', async () => {
    const post = vi.spyOn(client, 'apiPost').mockResolvedValue({ status: 'acknowledged' });
    renderPanel([mk({ id: 1, status: 'UNACKNOWLEDGED' })]);
    await screen.findByTestId('alarm-row-1');
    fireEvent.click(screen.getByRole('button', { name: /ack all/i }));
    await waitFor(() => expect(post).toHaveBeenCalledWith('/alarms/ack-all'));
  });
});
