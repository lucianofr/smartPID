import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
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

  // ISA-101 §8.2: severity must be encoded on THREE independent channels so it
  // survives loss of any one (color-blindness, monochrome render, motion off).
  it('encodes an unacked CRITICAL bucket on all 3 redundant channels (color + shape + count/weight)', async () => {
    renderBar([mk({ id: 1, priority: 'CRITICAL', status: 'UNACKNOWLEDGED' })]);
    const bucket = await screen.findByTestId('count-critical');
    // Wait for data to resolve (is-unacked + count populate together).
    expect(await within(bucket).findByText('1')).toBeInTheDocument();
    // (1) Color channel: the severity color token class (sev-critical → --alarm-critical).
    expect(bucket).toHaveClass('sev-critical');
    // (2) Shape channel: the geometric glyph element (octagon = CRITICAL), present
    //     INDEPENDENT of color — assert the element + its shape modifier exist.
    const glyph = bucket.querySelector('.sev-icon');
    expect(glyph).not.toBeNull();
    expect(glyph).toHaveClass('sev-icon--octagon');
    // (3) Count/weight channel: the literal count + the is-unacked weight cue.
    expect(bucket).toHaveClass('is-unacked');
  });

  it('exposes the text label of every severity bucket independent of color', async () => {
    renderBar([
      mk({ id: 1, priority: 'CRITICAL' }),
      mk({ id: 2, priority: 'WARNING' }),
      mk({ id: 3, priority: 'ADVISORY' }),
    ]);
    await screen.findByTestId('count-critical');
    expect(within(screen.getByTestId('count-critical')).getByText('CRIT')).toBeInTheDocument();
    expect(within(screen.getByTestId('count-warning')).getByText('WARN')).toBeInTheDocument();
    expect(within(screen.getByTestId('count-advisory')).getByText('DIAG')).toBeInTheDocument();
  });
});

describe('AlarmBar — reduced motion (hardened a11y path)', () => {
  const realMatchMedia = window.matchMedia;
  afterEach(() => {
    window.matchMedia = realMatchMedia;
  });

  function stubReducedMotion(reduce: boolean): void {
    window.matchMedia = ((query: string) =>
      ({
        matches: reduce && query.includes('prefers-reduced-motion'),
        media: query,
        onchange: null,
        addEventListener: () => {},
        removeEventListener: () => {},
        addListener: () => {},
        removeListener: () => {},
        dispatchEvent: () => false,
      }) as unknown as MediaQueryList) as typeof window.matchMedia;
  }

  it('shows a persistent unacked count badge + assertive live region when motion is reduced', async () => {
    stubReducedMotion(true);
    renderBar([mk({ id: 1, priority: 'CRITICAL', status: 'UNACKNOWLEDGED' })]);
    // Wait for the badge itself to appear (it renders only once data resolves AND
    // there is an unacked alarm under reduced motion).
    const badge = await screen.findByTestId('unacked-badge-critical');
    expect(badge).toHaveTextContent('1');
    expect(within(screen.getByTestId('count-critical')).getByTestId('unacked-badge-critical')).toBe(badge);
    // Assertive live region announcing new CRITICAL unacked (motion-free re-encode).
    const live = screen.getByTestId('alarm-bar-live');
    expect(live).toHaveAttribute('aria-live', 'assertive');
    expect(live).toHaveTextContent(/critical/i);
  });

  it('does not render the unacked badge when motion is allowed', async () => {
    stubReducedMotion(false);
    renderBar([mk({ id: 1, priority: 'CRITICAL', status: 'UNACKNOWLEDGED' })]);
    expect(await within(await screen.findByTestId('count-critical')).findByText('1')).toBeInTheDocument();
    expect(screen.queryByTestId('unacked-badge-critical')).not.toBeInTheDocument();
  });
});
