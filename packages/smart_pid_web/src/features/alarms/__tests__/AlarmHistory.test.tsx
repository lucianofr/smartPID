import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/api/client';
import { endpoints } from '@/api/endpoints';
import type { ControllerResponse } from '@/api/types';
import { createQueryClient, TestProviders } from '@/test/providers';
import { AlarmHistory } from '../AlarmHistory';
import { HISTORY_LIMIT } from '../useAlarms';
import type { ActiveAlarm } from '../types';

const offsetHeightDesc = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetHeight');

function alarm(overrides: Partial<ActiveAlarm> = {}): ActiveAlarm {
  return {
    id: 1,
    controller_id: 7,
    controller_name: 'FIC-101',
    alarm_type: 'HIHI',
    priority: 'CRITICAL',
    value: 99,
    limit: 90,
    timestamp: '2026-07-26T10:00:00.000Z',
    cleared_at: null,
    acknowledged: 1,
    ack_by_user: 'admin',
    ack_at: '2026-07-26T10:00:30.000Z',
    status: 'ACKNOWLEDGED',
    ...overrides,
  };
}

function renderHistory() {
  vi.spyOn(endpoints, 'controllers').mockResolvedValue([
    { id: 7, name: 'FIC-101' },
    { id: 9, name: 'TIC-202' },
  ] as ControllerResponse[]);
  return render(
    <TestProviders queryClient={createQueryClient()}>
      <AlarmHistory />
    </TestProviders>,
  );
}

beforeEach(() => {
  Object.defineProperty(HTMLElement.prototype, 'offsetHeight', { configurable: true, value: 600 });
});

afterEach(() => {
  if (offsetHeightDesc) {
    Object.defineProperty(HTMLElement.prototype, 'offsetHeight', offsetHeightDesc);
  }
  vi.restoreAllMocks();
});

describe('AlarmHistory request', () => {
  it('always sends both required bounds and an explicit high limit', async () => {
    const history = vi.spyOn(endpoints, 'alarmHistory').mockResolvedValue([]);
    renderHistory();
    await waitFor(() => expect(history).toHaveBeenCalledTimes(1));
    const params = history.mock.calls[0][0];
    expect(params.limit).toBe(HISTORY_LIMIT);
    expect(Number.isNaN(Date.parse(params.start))).toBe(false);
    expect(Number.isNaN(Date.parse(params.end))).toBe(false);
    expect(Date.parse(params.start)).toBeLessThan(Date.parse(params.end));
  });

  it('narrows the window to one loop on the wire', async () => {
    const history = vi
      .spyOn(endpoints, 'alarmHistory')
      .mockResolvedValue([alarm({ id: 1, controller_id: 7 })]);
    renderHistory();
    await screen.findByTestId('history-row-1');

    fireEvent.change(screen.getByLabelText('Malha'), { target: { value: '7' } });
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar filtros' }));

    await waitFor(() =>
      expect(history).toHaveBeenLastCalledWith(expect.objectContaining({ controllerId: 7 })),
    );
  });

  it('refetches when the operator moves the range', async () => {
    const history = vi.spyOn(endpoints, 'alarmHistory').mockResolvedValue([]);
    renderHistory();
    await waitFor(() => expect(history).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByLabelText('Início'), { target: { value: '2026-07-01T00:00' } });
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar filtros' }));

    await waitFor(() => expect(history).toHaveBeenCalledTimes(2));
    expect(history.mock.calls[1][0].start).toBe(new Date('2026-07-01T00:00').toISOString());
  });
});

describe('AlarmHistory filters', () => {
  it('narrows priority and type client-side — the backend takes neither', async () => {
    const history = vi.spyOn(endpoints, 'alarmHistory').mockResolvedValue([
      alarm({ id: 1, priority: 'CRITICAL', alarm_type: 'HIHI' }),
      alarm({ id: 2, priority: 'WARNING', alarm_type: 'HI' }),
      alarm({ id: 3, priority: 'WARNING', alarm_type: 'LO' }),
    ]);
    renderHistory();
    await screen.findByTestId('history-row-1');

    fireEvent.change(screen.getByLabelText('Prioridade'), { target: { value: 'WARNING' } });
    fireEvent.change(screen.getByLabelText('Tipo'), { target: { value: 'HI' } });
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar filtros' }));

    await waitFor(() => expect(screen.queryByTestId('history-row-1')).toBeNull());
    expect(screen.getByTestId('history-row-2')).toBeVisible();
    expect(screen.queryByTestId('history-row-3')).toBeNull();
    // priority/type never reach the wire: /alarms/history has no such parameters.
    for (const [params] of history.mock.calls) {
      expect(params).not.toHaveProperty('priority');
      expect(params).not.toHaveProperty('type');
    }
  });

  it('keeps the selected range after a failed fetch', async () => {
    vi.spyOn(endpoints, 'alarmHistory').mockRejectedValue(
      new ApiError(500, 'server', 'boom'),
    );
    renderHistory();

    fireEvent.change(screen.getByLabelText('Início'), { target: { value: '2026-07-01T00:00' } });
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar filtros' }));

    expect(await screen.findByText('Não foi possível carregar o histórico.')).toBeVisible();
    expect(screen.getByLabelText('Início')).toHaveValue('2026-07-01T00:00');
  });

  it('shows the designed empty state for a quiet window', async () => {
    vi.spyOn(endpoints, 'alarmHistory').mockResolvedValue([]);
    renderHistory();
    expect(await screen.findByText('Nenhum alarme no período.')).toBeVisible();
  });

  it('states each row severity as text and shape, plus who acknowledged it', async () => {
    vi.spyOn(endpoints, 'alarmHistory').mockResolvedValue([alarm()]);
    renderHistory();
    const row = await screen.findByTestId('history-row-1');
    expect(row).toHaveTextContent('CRITICAL');
    expect(row).toHaveTextContent('FIC-101');
    expect(row).toHaveTextContent('admin');
    expect(row.querySelector('.sev-icon--octagon')).not.toBeNull();
  });
});
