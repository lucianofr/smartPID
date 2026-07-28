import { render, renderHook, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { queryKeys } from '@/api/queryKeys';
import type { AlarmRow } from '@/api/types';
import { AlarmFooterBar } from '@/features/dashboard/AlarmFooterBar';
import { createFakeRealtime, createQueryClient, TestProviders } from '@/test/providers';
import { useReducedMotion } from '../useReducedMotion';

type MediaListener = () => void;

const listeners = new Set<MediaListener>();
let reduceMotion = false;

/** Live matchMedia double: flipping it must reach `useSyncExternalStore`. */
function stubReducedMotion(reduce: boolean): void {
  reduceMotion = reduce;
  for (const listener of [...listeners]) listener();
}

function activeRow(overrides: Partial<AlarmRow> = {}): AlarmRow {
  return {
    id: 1,
    controller_id: 1,
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

function renderFooter(rows: AlarmRow[] = []) {
  const queryClient = createQueryClient();
  queryClient.setQueryData(queryKeys.alarmsActive, rows);
  return render(
    <TestProviders queryClient={queryClient} realtime={createFakeRealtime().value}>
      <AlarmFooterBar />
    </TestProviders>,
  );
}

beforeEach(() => {
  sessionStorage.clear();
  listeners.clear();
  reduceMotion = false;
  vi.spyOn(window, 'matchMedia').mockImplementation(
    (query: string) =>
      ({
        get matches() {
          return reduceMotion && query.includes('prefers-reduced-motion');
        },
        media: query,
        onchange: null,
        addEventListener: (_: string, listener: MediaListener) => listeners.add(listener),
        removeEventListener: (_: string, listener: MediaListener) => listeners.delete(listener),
        addListener: () => {},
        removeListener: () => {},
        dispatchEvent: () => false,
      }) as unknown as MediaQueryList,
  );
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('useReducedMotion', () => {
  it('reports the live media state', () => {
    const { result, rerender } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(false);
    stubReducedMotion(true);
    rerender();
    expect(result.current).toBe(true);
  });
});

describe('AlarmFooterBar motion paths', () => {
  it('blinks the unacked bucket when motion is allowed', () => {
    stubReducedMotion(false);
    renderFooter([activeRow()]);
    const bucket = screen.getByTestId('count-critical');
    expect(bucket).toHaveClass('alarm-blink');
    expect(bucket).toHaveClass('is-unacked');
    expect(screen.queryByTestId('unacked-badge-critical')).toBeNull();
  });

  it('swaps the blink for a persistent badge under reduced motion', () => {
    stubReducedMotion(true);
    renderFooter([activeRow()]);
    const bucket = screen.getByTestId('count-critical');
    expect(bucket).not.toHaveClass('alarm-blink');
    expect(screen.getByTestId('unacked-badge-critical')).toHaveTextContent('1');
    // The badge is a real label, not a bare glyph.
    expect(screen.getByTestId('unacked-badge-critical')).toHaveAccessibleName(
      /1 não reconhecido/i,
    );
  });

  it('never renders a badge for a bucket with nothing unacknowledged', () => {
    stubReducedMotion(true);
    renderFooter([activeRow({ acknowledged: 1, status: 'ACKNOWLEDGED' })]);
    expect(screen.queryByTestId('unacked-badge-critical')).toBeNull();
    expect(screen.queryByTestId('unacked-badge-warning')).toBeNull();
  });

  it('announces unacknowledged criticals assertively in both motion paths', () => {
    stubReducedMotion(true);
    renderFooter([activeRow()]);
    const live = screen.getByTestId('alarm-bar-live');
    expect(live).toHaveAttribute('aria-live', 'assertive');
    expect(live).toHaveTextContent('1');
  });
});

describe('AlarmFooterBar §6.9 contracts', () => {
  it('states severity with a shape, not color alone', () => {
    renderFooter([activeRow()]);
    expect(
      screen.getByTestId('count-critical').querySelector('.sev-icon--octagon'),
    ).not.toBeNull();
    expect(screen.getByTestId('count-log').querySelector('.sev-icon--dot')).not.toBeNull();
  });

  it('shows the last alarm from REST before any realtime frame arrives', () => {
    renderFooter([
      activeRow({ id: 1, timestamp: '2026-07-26T10:00:00.000Z' }),
      activeRow({ id: 2, alarm_type: 'LOLO', timestamp: '2026-07-26T11:00:00.000Z' }),
    ]);
    expect(screen.getByTestId('alarm-last-event')).toHaveTextContent('FIC-101 LOLO');
  });

  it('keeps ACK ALL and the count chip through the sub-768 collapse', () => {
    renderFooter([activeRow()]);
    const ackAll = screen.getByRole('button', { name: 'ACK ALL' });
    expect(ackAll).toBeEnabled();
    // No responsive hiding on the one control the 320 px floor must keep.
    expect(ackAll.className).not.toContain('hidden');
    expect(screen.getByTestId('alarm-count-chip')).toHaveTextContent('1');
    expect(screen.getByTestId('alarm-buckets').className).toContain('max-md:hidden');
  });
});
