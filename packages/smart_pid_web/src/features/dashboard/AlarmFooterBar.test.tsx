import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import type { AlarmRow } from '@/api/types';
import type { AlarmEventData, RealtimeEnvelope } from '@/lib/envelope';
import { createFakeRealtime, createQueryClient, TestProviders } from '@/test/providers';
import { AlarmFooterBar } from './AlarmFooterBar';
import { ALARM_SEVERITIES } from './useAlarmCounts';

function activeRow(overrides: Partial<AlarmRow> = {}): AlarmRow {
  return {
    id: 1,
    controller_id: 1,
    controller_name: 'FIC-101',
    alarm_type: 'HIHI',
    priority: 'CRITICAL',
    value: 99,
    limit: 90,
    timestamp: '2026-07-26T00:00:00.000Z',
    cleared_at: null,
    acknowledged: 0,
    ack_by_user: null,
    ack_at: null,
    status: 'UNACKNOWLEDGED',
    ...overrides,
  };
}

function alarmEvent(
  seq: number,
  data: Partial<AlarmEventData> = {},
): RealtimeEnvelope<AlarmEventData> & { type: 'alarm' } {
  return {
    type: 'alarm',
    loop_id: 1,
    seq,
    ts: seq,
    data: {
      controller_id: 1,
      controller_name: 'FIC-101',
      controller_description: 'Flow',
      alarm_type: 'HI',
      priority: 'WARNING',
      transition: 'TRIGGERED',
      value: 80,
      limit: 75,
      timestamp: '2026-07-26T00:00:05.000Z',
      ...data,
    },
  };
}

function renderFooter(rows: AlarmRow[] = []) {
  const queryClient = createQueryClient();
  queryClient.setQueryData(queryKeys.alarmsActive, rows);
  const realtime = createFakeRealtime();
  return {
    ...render(
      <TestProviders queryClient={queryClient} realtime={realtime.value}>
        <AlarmFooterBar />
      </TestProviders>,
    ),
    queryClient,
    realtime,
  };
}

beforeEach(() => {
  sessionStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('AlarmFooterBar', () => {
  it('exposes the four §6.9 buckets', () => {
    expect(ALARM_SEVERITIES).toEqual(['CRITICAL', 'WARNING', 'ADVISORY', 'LOG']);
    renderFooter();
    expect(screen.getByTestId('count-critical')).toHaveTextContent('CRIT');
    expect(screen.getByTestId('count-warning')).toHaveTextContent('WARN');
    expect(screen.getByTestId('count-advisory')).toHaveTextContent('ADV');
    expect(screen.getByTestId('count-log')).toHaveTextContent('LOG');
  });

  it('stays monochrome and disables ACK ALL with zero unacked alarms', () => {
    renderFooter();
    const bucket = screen.getByTestId('count-critical');
    expect(bucket).toHaveStyle({ color: 'var(--text-soft)' });
    expect(bucket).not.toHaveClass('is-unacked');
    expect(screen.getByRole('button', { name: 'ACK ALL' })).toBeDisabled();
  });

  it('colors only the buckets that hold unacknowledged alarms', () => {
    renderFooter([
      activeRow({ id: 1, alarm_type: 'HIHI', priority: 'CRITICAL', acknowledged: 0 }),
      activeRow({
        id: 2,
        alarm_type: 'HI',
        priority: 'WARNING',
        acknowledged: 1,
        status: 'ACKNOWLEDGED',
      }),
    ]);
    const crit = screen.getByTestId('count-critical');
    const warn = screen.getByTestId('count-warning');
    expect(crit).toHaveStyle({ color: 'var(--alarm-crit)' });
    expect(crit).toHaveClass('is-unacked');
    expect(warn).toHaveStyle({ color: 'var(--text-soft)' });
    expect(warn).not.toHaveClass('is-unacked');
    expect(screen.getByRole('button', { name: 'ACK ALL' })).toBeEnabled();
  });

  it('counts active and unacked separately per bucket', () => {
    renderFooter([
      activeRow({ id: 1, alarm_type: 'HIHI', priority: 'CRITICAL', acknowledged: 0 }),
      activeRow({
        id: 2,
        alarm_type: 'LOLO',
        priority: 'CRITICAL',
        acknowledged: 1,
        status: 'ACKNOWLEDGED',
      }),
    ]);
    expect(screen.getByTestId('count-critical')).toHaveTextContent('CRIT21');
    expect(screen.getByTestId('unacked-critical')).toHaveTextContent('1');
  });

  it('keys alarms by (controller, type) — a re-trigger is not a second alarm', () => {
    const { realtime } = renderFooter();
    act(() => {
      realtime.emit(alarmEvent(1));
      realtime.emit(alarmEvent(2));
    });
    expect(screen.getByTestId('count-warning')).toHaveTextContent('WARN11');
  });

  it('advances the live counters from EVENT.ALARM without a refetch', () => {
    const { realtime } = renderFooter();
    expect(screen.getByTestId('count-warning')).toHaveTextContent('0');
    act(() => {
      realtime.emit(alarmEvent(1));
    });
    expect(screen.getByTestId('count-warning')).toHaveTextContent('1');
    expect(screen.getByTestId('count-warning')).toHaveClass('is-unacked');
    expect(screen.getByText(/FIC-101/)).toBeVisible();
  });

  it('keeps a cleared-but-unacknowledged alarm visible until it is acked', () => {
    const { realtime } = renderFooter();
    act(() => {
      realtime.emit(alarmEvent(1));
      realtime.emit(alarmEvent(2, { transition: 'CLEARED' }));
    });
    // Cleared, so no longer active — but still unacknowledged.
    expect(screen.getByTestId('count-warning')).toHaveTextContent('0');
    expect(screen.getByTestId('unacked-warning')).toHaveTextContent('1');
    expect(screen.getByRole('button', { name: 'ACK ALL' })).toBeEnabled();
  });

  it('acknowledges everything and invalidates the active-alarm query', async () => {
    const ackAll = vi.spyOn(endpoints, 'ackAllAlarms').mockResolvedValue({});
    const { queryClient } = renderFooter([activeRow()]);
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries');
    fireEvent.click(screen.getByRole('button', { name: 'ACK ALL' }));
    await waitFor(() => expect(ackAll).toHaveBeenCalledTimes(1));
    await waitFor(() =>
      expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.alarmsActive }),
    );
  });

  it('keeps a single count chip for the sub-768 collapsed bar', () => {
    renderFooter([activeRow()]);
    const chip = screen.getByTestId('alarm-count-chip');
    expect(chip).toHaveTextContent('1');
    // Chip only below 768; the bucket row only at/above it.
    expect(chip.className).toContain('md:hidden');
    expect(screen.getByTestId('alarm-buckets').className).toContain('max-md:hidden');
  });
});
