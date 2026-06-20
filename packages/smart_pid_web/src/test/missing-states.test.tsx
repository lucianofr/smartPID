import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import type { ReactNode } from 'react';

/**
 * Task 9.1 — mandated missing states (§6a).
 *
 * Asserts the three ISA-101-legal states across the migrated surfaces:
 *  (a) LOADING  — `aria-busy` set + static (non-animated) placeholder bars
 *                 (NO `animate-*`/skeleton shimmer).
 *  (b) EMPTY    — an explicit per-surface empty message.
 *  (c) ERROR / WS-DISCONNECT — desaturated `--alarm-diag` token treatment via
 *                 the `text-alarm-diag`/`border-alarm-diag` utilities, plus a
 *                 reconnect/retry control and a stale-data indicator.
 *
 * These are behaviour assertions over accessible roles / names / testids; the
 * frozen DOM bindings (freeze-inventory.md) are untouched.
 */

// ── Controllable realtime mock (WS connected/disconnected) ───────────────────
let wsConnected = true;
vi.mock('../realtime/useRealtime', () => ({
  useRealtime: () => ({
    connected: wsConnected,
    lastStatus: new Map(),
    lastStats: new Map(),
    subscribe: () => () => {},
    onResync: () => () => {},
  }),
}));

vi.mock('../api/client');

import * as client from '../api/client';
import { DashboardPage } from '../pages/DashboardPage';
import { AlarmPanel } from '../features/alarms/AlarmPanel';
import { HistoryQuery } from '../features/multitrend/HistoryQuery';
import { WsConnectionBanner } from '../components/WsConnectionBanner';
import { ThemeProvider } from '../theme/ThemeProvider';

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ThemeProvider>
        <MemoryRouter>{ui}</MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

/** No `animate-*` / skeleton-shimmer class anywhere in the loading placeholders. */
function assertStaticPlaceholders(busyEl: HTMLElement): void {
  const bars = busyEl.querySelectorAll('[data-testid="loading-bar"]');
  expect(bars.length).toBeGreaterThan(0);
  for (const el of [busyEl, ...Array.from(busyEl.querySelectorAll('*'))]) {
    const cls = el.getAttribute('class') ?? '';
    expect(cls).not.toMatch(/\banimate-/);
    expect(cls.toLowerCase()).not.toMatch(/shimmer|skeleton/);
  }
}

beforeEach(() => {
  wsConnected = true;
  vi.clearAllMocks();
});
afterEach(() => vi.clearAllMocks());

// ── Dashboard ────────────────────────────────────────────────────────────────
describe('DashboardPage missing states (§6a)', () => {
  it('LOADING: sets aria-busy and renders static (non-animated) placeholder bars', () => {
    // Never-resolving controllers query → stays in the loading branch.
    vi.spyOn(client, 'apiGet').mockImplementation((path: string) => {
      if (path === '/opcua/status') return Promise.resolve({ state: 'ONLINE', endpoint: null });
      if (path === '/alarms/active') return Promise.resolve([]); // AlarmBar (AppShell)
      return new Promise(() => {}); // /controllers never resolves → loading branch
    });
    wrap(<DashboardPage />);
    const busy = screen.getByTestId('dashboard-loading');
    expect(busy).toHaveAttribute('aria-busy', 'true');
    assertStaticPlaceholders(busy);
  });

  it('EMPTY: renders an explicit "no loops" empty message when the list is empty', async () => {
    vi.spyOn(client, 'apiGet').mockImplementation((path: string) => {
      if (path === '/controllers') return Promise.resolve([]);
      if (path === '/alarms/active') return Promise.resolve([]); // AlarmBar (AppShell)
      return Promise.resolve({ state: 'ONLINE', endpoint: null });
    });
    wrap(<DashboardPage />);
    expect(await screen.findByTestId('dashboard-empty')).toHaveTextContent(/no loops/i);
  });

  it('ERROR: surfaces a diag-token error with a retry control when the query fails', async () => {
    vi.spyOn(client, 'apiGet').mockImplementation((path: string) => {
      if (path === '/controllers') return Promise.reject(new Error('boom'));
      if (path === '/alarms/active') return Promise.resolve([]); // AlarmBar (AppShell)
      return Promise.resolve({ state: 'ONLINE', endpoint: null });
    });
    wrap(<DashboardPage />);
    const err = await screen.findByTestId('dashboard-error');
    expect(err.className).toMatch(/alarm-diag/);
    expect(within(err).getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });
});

// ── AlarmPanel ───────────────────────────────────────────────────────────────
describe('AlarmPanel missing states (§6a)', () => {
  it('EMPTY: renders an explicit "no active alarms" message when there are none', async () => {
    vi.spyOn(client, 'apiGet').mockResolvedValue([]);
    wrap(<AlarmPanel />);
    expect(await screen.findByTestId('alarm-panel-empty')).toHaveTextContent(/no active alarms/i);
  });
});

// ── MultiTrend / HistoryQuery ────────────────────────────────────────────────
describe('HistoryQuery missing states (§6a)', () => {
  it('EMPTY: renders an explicit "no history" message after a query returns zero frames', () => {
    // hasQueried=true + zero frames → explicit empty (distinct from "not yet queried").
    wrap(
      <HistoryQuery
        controllerId={1}
        onQuery={() => {}}
        frames={[]}
        count={0}
        isLoading={false}
        hasQueried
      />,
    );
    expect(screen.getByTestId('history-empty')).toHaveTextContent(/no history/i);
  });

  it('LOADING: sets aria-busy and renders static placeholder bars while a query runs', () => {
    wrap(
      <HistoryQuery
        controllerId={1}
        onQuery={() => {}}
        frames={[]}
        count={0}
        isLoading
        hasQueried
      />,
    );
    const busy = screen.getByTestId('history-loading');
    expect(busy).toHaveAttribute('aria-busy', 'true');
    assertStaticPlaceholders(busy);
  });
});

// ── WS disconnect ────────────────────────────────────────────────────────────
describe('WsConnectionBanner — WS disconnect state (§6a)', () => {
  it('renders nothing while the realtime socket is connected', () => {
    wsConnected = true;
    wrap(<WsConnectionBanner />);
    expect(screen.queryByTestId('ws-disconnected')).toBeNull();
  });

  it('on disconnect: diag-token treatment + reconnect affordance + stale-data indicator', () => {
    wsConnected = false;
    wrap(<WsConnectionBanner />);
    const banner = screen.getByTestId('ws-disconnected');
    // desaturated --alarm-diag treatment (text/border), never critical red
    expect(banner.className).toMatch(/alarm-diag/);
    expect(banner.className).not.toMatch(/alarm-critical/);
    // reconnect affordance
    expect(within(banner).getByRole('button', { name: /reconnect/i })).toBeInTheDocument();
    // stale-data indication
    expect(within(banner).getByTestId('ws-stale')).toHaveTextContent(/stale/i);
  });
});
