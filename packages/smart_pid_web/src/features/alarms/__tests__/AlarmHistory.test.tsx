import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/api/client';
import { endpoints, type SystemEventRow } from '@/api/endpoints';
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

function event(overrides: Partial<SystemEventRow> = {}): SystemEventRow {
  return {
    id: 1,
    timestamp: '2026-07-26T10:05:00.000Z',
    source: 'AI',
    severity: 'LOG',
    message: 'Sugestão do otimizador: Kp 1.20 -> 1.35',
    ...overrides,
  };
}

function renderHistory(events: SystemEventRow[] = []) {
  vi.spyOn(endpoints, 'controllers').mockResolvedValue([
    { id: 7, name: 'FIC-101' },
    { id: 9, name: 'TIC-202' },
  ] as ControllerResponse[]);
  vi.spyOn(endpoints, 'systemEvents').mockResolvedValue(events);
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
    expect(await screen.findByText('Nenhum alarme ou evento no período.')).toBeVisible();
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

describe('AlarmHistory merged alarm + event log', () => {
  it('fetches both logs over the same window and orders newest first', async () => {
    const history = vi
      .spyOn(endpoints, 'alarmHistory')
      .mockResolvedValue([alarm({ id: 1, timestamp: '2026-07-26T10:00:00.000Z' })]);
    renderHistory([event({ id: 5, timestamp: '2026-07-26T10:05:00.000Z' })]);

    await screen.findByTestId('history-event-5');
    const params = history.mock.calls[0][0];
    expect(endpoints.systemEvents).toHaveBeenCalledWith({
      start: params.start,
      end: params.end,
      limit: HISTORY_LIMIT,
    });

    const rows = within(
      screen.getByRole('list', { name: 'Lista do histórico de alarmes e eventos' }),
    ).getAllByRole('listitem');
    expect(rows[0]).toHaveTextContent('Sugestão do otimizador');
    expect(rows[1]).toHaveTextContent('HIHI');
  });

  it('renders the event message and source, never a fabricated value or ack', async () => {
    vi.spyOn(endpoints, 'alarmHistory').mockResolvedValue([]);
    renderHistory([event({ id: 5 })]);

    const row = await screen.findByTestId('history-event-5');
    expect(row).toHaveTextContent('LOG');
    expect(row).toHaveTextContent('AI');
    expect(row).toHaveTextContent('Sugestão do otimizador: Kp 1.20 -> 1.35');
    expect(row).not.toHaveTextContent('lim');
    expect(row).not.toHaveTextContent('ACKNOWLEDGED');
    expect(row.querySelector('.sev-icon--dot')).not.toBeNull();
  });

  it('shows alarms AND events on Todas, and only events on LOG', async () => {
    vi.spyOn(endpoints, 'alarmHistory').mockResolvedValue([alarm({ id: 1, priority: 'CRITICAL' })]);
    renderHistory([event({ id: 5 })]);

    await screen.findByTestId('history-row-1');
    expect(screen.getByTestId('history-event-5')).toBeVisible();

    fireEvent.change(screen.getByLabelText('Prioridade'), { target: { value: 'LOG' } });
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar filtros' }));

    await waitFor(() => expect(screen.queryByTestId('history-row-1')).toBeNull());
    expect(screen.getByTestId('history-event-5')).toBeVisible();
  });

  it('excludes events when a specific alarm type is selected — they have none', async () => {
    vi.spyOn(endpoints, 'alarmHistory').mockResolvedValue([
      alarm({ id: 1, alarm_type: 'HIHI' }),
      alarm({ id: 2, alarm_type: 'HI' }),
    ]);
    renderHistory([event({ id: 5 })]);
    await screen.findByTestId('history-event-5');

    fireEvent.change(screen.getByLabelText('Tipo'), { target: { value: 'HIHI' } });
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar filtros' }));

    await waitFor(() => expect(screen.queryByTestId('history-event-5')).toBeNull());
    expect(screen.getByTestId('history-row-1')).toBeVisible();
    expect(screen.queryByTestId('history-row-2')).toBeNull();
  });

  it('skips the event log when the operator picks one loop', async () => {
    vi.spyOn(endpoints, 'alarmHistory').mockResolvedValue([alarm({ id: 1, controller_id: 7 })]);
    renderHistory([event({ id: 5 })]);
    await screen.findByTestId('history-event-5');

    fireEvent.change(screen.getByLabelText('Malha'), { target: { value: '7' } });
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar filtros' }));

    await waitFor(() => expect(screen.queryByTestId('history-event-5')).toBeNull());
    // Events carry no controller id, so a specific-loop window never asks for them.
    expect(endpoints.systemEvents).toHaveBeenCalledTimes(1);
  });

  it('keys colliding alarm and event ids apart', async () => {
    const warn = vi.spyOn(console, 'error').mockImplementation(() => {});
    vi.spyOn(endpoints, 'alarmHistory').mockResolvedValue([alarm({ id: 5 })]);
    renderHistory([event({ id: 5 })]);

    await screen.findByTestId('history-event-5');
    expect(screen.getByTestId('history-row-5')).toBeVisible();
    expect(warn.mock.calls.flat().join(' ')).not.toMatch(/same key/i);
  });
});
