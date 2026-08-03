import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { endpoints } from '@/api/endpoints';
import type { Role } from '@/api/types';
import { createQueryClient, TestProviders } from '@/test/providers';
import { AlarmPanel } from '../AlarmPanel';
import type { ActiveAlarm } from '../types';

const offsetHeightDesc = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetHeight');

function alarm(overrides: Partial<ActiveAlarm> = {}): ActiveAlarm {
  return {
    id: 42,
    controller_id: 7,
    controller_name: 'FIC-101',
    alarm_type: 'HIHI',
    priority: 'CRITICAL',
    value: 99,
    limit: 90,
    timestamp: '2026-07-26T10:00:00.000Z',
    cleared_at: null,
    acknowledged: 0,
    ack_by_user: null,
    ack_at: null,
    status: 'UNACKNOWLEDGED',
    ...overrides,
  };
}

function renderPanel(rows: ActiveAlarm[], role: Role = 'admin') {
  localStorage.setItem('smart-pid-token', 'jwt');
  vi.spyOn(endpoints, 'me').mockResolvedValue({ user_id: 1, username: role, role });
  vi.spyOn(endpoints, 'activeAlarms').mockImplementation(() => Promise.resolve([...rows]));
  return render(
    <TestProviders queryClient={createQueryClient()}>
      <AlarmPanel />
    </TestProviders>,
  );
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  Object.defineProperty(HTMLElement.prototype, 'offsetHeight', { configurable: true, value: 600 });
});

afterEach(() => {
  if (offsetHeightDesc) {
    Object.defineProperty(HTMLElement.prototype, 'offsetHeight', offsetHeightDesc);
  }
  vi.restoreAllMocks();
});

describe('AlarmPanel acknowledgement', () => {
  it('acks one row and reflects the refetched state — the row is NOT removed', async () => {
    // Stateful double: ack flips the row, it never leaves the active set (§7).
    const rows = [alarm()];
    const ack = vi.spyOn(endpoints, 'ackAlarm').mockImplementation((id) => {
      const row = rows.find((r) => r.id === id);
      if (row) {
        row.acknowledged = 1;
        row.status = 'ACKNOWLEDGED';
      }
      return Promise.resolve({});
    });
    renderPanel(rows);

    const row = await screen.findByTestId('alarm-row-42');
    expect(row).toHaveTextContent('UNACKNOWLEDGED');

    fireEvent.click(within(row).getByRole('button', { name: 'ACK' }));

    await waitFor(() => expect(ack).toHaveBeenCalledWith(42));
    await waitFor(() =>
      expect(screen.getByTestId('alarm-row-42')).toHaveTextContent('ACKNOWLEDGED'),
    );
    expect(screen.getByTestId('alarm-row-42')).toBeVisible();
  });

  it('lets a plain user acknowledge — alarms.ack is in the user capability set', async () => {
    renderPanel([alarm()], 'user');
    const row = await screen.findByTestId('alarm-row-42');
    expect(within(row).getByRole('button', { name: 'ACK' })).toBeEnabled();
  });

  it('offers nothing to acknowledge once the row is acknowledged', async () => {
    renderPanel([alarm({ acknowledged: 1, status: 'ACKNOWLEDGED' })]);
    const row = await screen.findByTestId('alarm-row-42');
    expect(within(row).getByRole('button', { name: 'ACK' })).toBeDisabled();
  });

  it('still demands acknowledgement from a cleared-but-unacked row', async () => {
    renderPanel([alarm({ cleared_at: '2026-07-26T10:01:00.000Z', status: 'CLEARED_UNACK' })]);
    const row = await screen.findByTestId('alarm-row-42');
    expect(row).toHaveTextContent('CLEARED_UNACK');
    expect(within(row).getByRole('button', { name: 'ACK' })).toBeEnabled();
  });
});

describe('AlarmPanel presentation', () => {
  it('carries severity on text AND shape, never color alone', async () => {
    renderPanel([alarm()]);
    const row = await screen.findByTestId('alarm-row-42');
    expect(row).toHaveTextContent('CRITICAL');
    expect(row.querySelector('.sev-icon--octagon')).not.toBeNull();
    expect(row.className).toContain('sev-critical');
    expect(row.className).toContain('is-unacked');
  });

  it('announces unacknowledged criticals assertively', async () => {
    renderPanel([alarm()]);
    await screen.findByTestId('alarm-row-42');
    const live = screen.getByTestId('alarm-panel-live');
    expect(live).toHaveAttribute('aria-live', 'assertive');
    expect(live).toHaveTextContent('1');
  });

  it('sorts most-severe first, then newest first inside a severity', async () => {
    renderPanel([
      alarm({ id: 1, priority: 'LOG', timestamp: '2026-07-26T12:00:00.000Z' }),
      alarm({ id: 2, priority: 'CRITICAL', timestamp: '2026-07-26T10:00:00.000Z' }),
      alarm({ id: 3, priority: 'CRITICAL', timestamp: '2026-07-26T11:00:00.000Z' }),
    ]);
    await screen.findByTestId('alarm-row-3');
    const ids = screen
      .getAllByTestId(/^alarm-row-/)
      .map((el) => el.getAttribute('data-testid'));
    expect(ids).toEqual(['alarm-row-3', 'alarm-row-2', 'alarm-row-1']);
  });

  it('windows a flood instead of mounting every row', async () => {
    const flood = Array.from({ length: 800 }, (_, i) =>
      alarm({ id: i + 1, controller_id: 1 + (i % 3) }),
    );
    renderPanel(flood);
    await screen.findByTestId('alarm-row-1');
    expect(screen.getAllByTestId(/^alarm-row-/).length).toBeLessThan(60);
  });

  it('filters the flood down to one state', async () => {
    renderPanel([
      alarm({ id: 1 }),
      alarm({ id: 2, acknowledged: 1, status: 'ACKNOWLEDGED' }),
    ]);
    await screen.findByTestId('alarm-row-1');
    fireEvent.change(screen.getByLabelText('Estado'), { target: { value: 'ACKNOWLEDGED' } });
    expect(screen.queryByTestId('alarm-row-1')).toBeNull();
    expect(screen.getByTestId('alarm-row-2')).toBeVisible();
  });

  it('filters the flood down to one loop', async () => {
    renderPanel([
      alarm({ id: 1, controller_id: 7, controller_name: 'FIC-101' }),
      alarm({ id: 2, controller_id: 9, controller_name: 'TIC-202' }),
    ]);
    await screen.findByTestId('alarm-row-1');
    fireEvent.change(screen.getByLabelText('Malha'), { target: { value: '9' } });
    expect(screen.queryByTestId('alarm-row-1')).toBeNull();
    expect(screen.getByTestId('alarm-row-2')).toBeVisible();
  });

  it('renders the designed empty state with no active alarms', async () => {
    renderPanel([]);
    expect(await screen.findByText('Nenhum alarme ativo.')).toBeVisible();
  });
});
