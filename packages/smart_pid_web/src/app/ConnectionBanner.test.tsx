import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { RealtimeContext } from '@/realtime/RealtimeProvider';
import { createFakeRealtime } from '@/test/providers';
import { ConnectionBanner, connectionBannerState } from './ConnectionBanner';
import type { ConnectionStatus } from '@/realtime/useConnectionStatus';

/** 14:32:07 local — the wall clock the banner is expected to print. */
const LAST_READING = new Date(2026, 6, 27, 14, 32, 7).getTime();

function renderBanner(overrides: Parameters<typeof createFakeRealtime>[0]) {
  const realtime = createFakeRealtime(overrides);
  return render(
    <RealtimeContext.Provider value={realtime.value}>
      <ConnectionBanner />
    </RealtimeContext.Provider>,
  );
}

const status = (over: Partial<ConnectionStatus>): ConnectionStatus => ({
  phase: 'live',
  connected: true,
  live: true,
  stale: false,
  staleSince: null,
  ...over,
});

describe('connectionBannerState', () => {
  it('says nothing while the bus is delivering current frames', () => {
    expect(connectionBannerState(status({}))).toBeNull();
  });

  it('a socket that reports itself live but delivers nothing is still called out', () => {
    // The E2E-047 shape. Reading `live` alone would print nothing here.
    const state = connectionBannerState(status({ stale: true, staleSince: LAST_READING }));
    expect(state?.title).toBe('DADOS DESATUALIZADOS');
    expect(state?.tone).toBe('warn');
  });

  it('ranks a lost link above mere staleness', () => {
    const state = connectionBannerState(
      status({ phase: 'connecting', connected: false, live: false, stale: true, staleSince: LAST_READING }),
    );
    expect(state?.title).toBe('SEM CONEXÃO');
    expect(state?.tone).toBe('crit');
  });
});

describe('ConnectionBanner', () => {
  it('renders nothing when the link is live and fresh', () => {
    renderBanner({});
    expect(screen.queryByTestId('connection-banner')).not.toBeInTheDocument();
  });

  it('announces a lost link assertively and says the values are not current', () => {
    renderBanner({ phase: 'connecting', connected: false, live: false });
    const banner = screen.getByTestId('connection-banner');
    expect(banner).toBeVisible();
    expect(banner).toHaveAttribute('role', 'status');
    expect(banner).toHaveAttribute('aria-live', 'assertive');
    expect(banner).toHaveAttribute('data-tone', 'crit');
    expect(banner).toHaveTextContent('SEM CONEXÃO');
    expect(banner).toHaveTextContent('tentando reconectar');
    expect(banner).toHaveTextContent(/NÃO são atuais/);
  });

  it('names the last reading time so the operator can size the gap', () => {
    renderBanner({ stale: true, staleSince: LAST_READING });
    const banner = screen.getByTestId('connection-banner');
    expect(banner).toHaveTextContent('DADOS DESATUALIZADOS');
    expect(banner).toHaveTextContent('14:32:07');
    expect(banner).toHaveAttribute('data-tone', 'warn');
  });

  it('stays quiet through a routine resync — a 300 ms strip is noise, not information', () => {
    // §8 fires a resync on any seq gap. The data on screen is still current, so
    // there is nothing to warn about; flashing here is what trains an operator
    // to ignore the banner that matters.
    renderBanner({ phase: 'resyncing', connected: true, live: false });
    expect(screen.queryByTestId('connection-banner')).not.toBeInTheDocument();
  });

  it('reports the resync when it IS the recovery from a real outage', () => {
    renderBanner({
      phase: 'resyncing',
      connected: true,
      live: false,
      stale: true,
      staleSince: LAST_READING,
    });
    const banner = screen.getByTestId('connection-banner');
    expect(banner).toHaveTextContent('RESSINCRONIZANDO');
    expect(banner).toHaveTextContent('14:32:07');
    expect(banner).toHaveAttribute('data-tone', 'adv');
  });

  it('tells an expired session apart from a dead link', () => {
    renderBanner({ phase: 'auth-failed', connected: false, live: false });
    expect(screen.getByTestId('connection-banner')).toHaveTextContent('SESSÃO EXPIRADA');
  });
});
