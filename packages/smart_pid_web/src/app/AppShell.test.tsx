import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { endpoints } from '@/api/endpoints';
import type { Role } from '@/api/types';
import { createFakeRealtime, TestProviders, type FakeRealtime } from '@/test/providers';
import { AppShell } from './AppShell';
import { appRoutes, cfgRoutes, navRoutes } from './routes';

function renderShell(realtime?: FakeRealtime) {
  return render(
    <TestProviders realtime={realtime?.value}>
      <AppShell>
        <p>conteúdo</p>
      </AppShell>
    </TestProviders>,
  );
}

/**
 * Same shell with a resolved session role. `AuthProvider` derives every
 * capability from `GET /auth/me`, so the role has to arrive that way — seeding
 * the token alone leaves `user` null, which is the deny-everything case.
 */
function renderShellAs(role: Role) {
  localStorage.setItem('smart-pid-token', 'jwt');
  vi.spyOn(endpoints, 'me').mockResolvedValue({ user_id: 1, username: role, role });
  vi.spyOn(endpoints, 'projectList').mockResolvedValue({ projects: [] });
  vi.spyOn(endpoints, 'projectCurrent').mockResolvedValue({
    name: 'Planta Norte',
    path: '/srv/projects/planta-norte.spid',
    controller_count: 3,
  });
  return renderShell();
}

/** Radix opens on pointerdown/keyboard, never on a synthetic click. */
async function openCfgMenu() {
  fireEvent.keyDown(screen.getByRole('button', { name: 'Configurações' }), { key: 'Enter' });
  return screen.findByRole('menu');
}

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('appRoutes registry', () => {
  it('registers the dashboard as the nav-visible root route', () => {
    const root = appRoutes.find((r) => r.path === '/');
    expect(root).toBeDefined();
    expect(root?.nav).toEqual({ label: 'Loops', order: 10 });
  });

  it('sorts nav and cfg projections by order', () => {
    const routes = [
      { path: '/b', element: () => null, nav: { label: 'B', order: 20 } },
      { path: '/a', element: () => null, nav: { label: 'A', order: 10 } },
      { path: '/c', element: () => null, cfg: { label: 'C', order: 30 } },
      { path: '/d', element: () => null, cfg: { label: 'D', order: 5 } },
    ];
    expect(navRoutes(routes).map((r) => r.nav.label)).toEqual(['A', 'B']);
    expect(cfgRoutes(routes).map((r) => r.cfg.label)).toEqual(['D', 'C']);
  });

  it('carries no command-palette metadata on any route', () => {
    for (const route of appRoutes) {
      expect(route).not.toHaveProperty('command');
    }
  });
});

describe('AppShell', () => {
  it('renders registry-backed top navigation and logout', () => {
    renderShell();
    expect(screen.getByRole('link', { name: 'Loops' })).toHaveAttribute('href', '/');
    expect(screen.queryByRole('button', { name: 'Comandos' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Configurações' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'Sair' })).toBeVisible();
    expect(screen.getByText('conteúdo')).toBeVisible();
  });

  it('clears the session when Sair is pressed', () => {
    localStorage.setItem('smart-pid-token', 'jwt');
    renderShell();
    fireEvent.click(screen.getByRole('button', { name: 'Sair' }));
    expect(localStorage.getItem('smart-pid-token')).toBeNull();
  });

  it('switches the persisted theme from the cfg menu', async () => {
    renderShell();
    // Radix opens the menu on pointerdown / keyboard, not on a synthetic click.
    fireEvent.keyDown(screen.getByRole('button', { name: 'Configurações' }), { key: 'Enter' });
    const menu = await screen.findByRole('menu');
    fireEvent.click(within(menu).getByRole('menuitemradio', { name: 'Phosphor' }));
    await waitFor(() =>
      expect(document.documentElement.getAttribute('data-theme')).toBe('phosphor'),
    );
    expect(localStorage.getItem('spid.theme')).toBe('phosphor');
  });

  it('labels the configuration trigger with a gear icon, not a bracketed glyph', () => {
    renderShell();
    const trigger = screen.getByRole('button', { name: 'Configurações' });
    expect(trigger).toHaveTextContent('');
    expect(trigger.querySelector('svg')).not.toBeNull();
    expect(trigger.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
  });

  it('offers the executive dashboard in the top bar and points the wordmark at the root', () => {
    renderShell();
    const nav = screen.getByRole('navigation', { name: 'Navegação principal' });
    expect(within(nav).getAllByRole('link').map((l) => l.textContent)).toEqual([
      'Loops',
      'Trends',
      'Alarms',
      'Sim',
      'Executivo',
    ]);
    expect(within(nav).getByRole('link', { name: 'Executivo' })).toHaveAttribute(
      'href',
      '/executive',
    );
    // The wordmark is two-tone (`PID` is amber), so its accessible name comes
    // from an explicit aria-label — text-node joining would read "smart PID
    // Optimizer" in jsdom and "smartPID Optimizer" in a browser.
    expect(screen.getByRole('link', { name: 'smartPID Optimizer' })).toHaveAttribute('href', '/');
  });

  it('keeps the executive entry for a user role', async () => {
    renderShellAs('user');
    await waitFor(() => expect(endpoints.me).toHaveBeenCalled());
    const nav = screen.getByRole('navigation', { name: 'Navegação principal' });
    expect(within(nav).getByRole('link', { name: 'Executivo' })).toBeVisible();
  });

  it('names the active project after the nav once /project/current resolves', async () => {
    renderShellAs('user');
    const name = await screen.findByText('Planta Norte');
    expect(name).toBeVisible();
    // sr-only prefix, not an aria-label on a role-less span: that is the
    // labelling idiom the rest of the app uses for a bare value (TwinTrend).
    expect(screen.getByText('Projeto ativo')).toBeInTheDocument();
    // Ordering is the point: the name reads as the tail of the nav row, so a
    // future header reshuffle that drags it back beside the brand must fail.
    const nav = screen.getByRole('navigation', { name: 'Navegação principal' });
    expect(nav.compareDocumentPosition(name) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('renders no project label while /project/current has not resolved', () => {
    renderShell();
    expect(screen.queryByText('Projeto ativo')).not.toBeInTheDocument();
  });
});

/**
 * E2E-047 — the shell is where "are these numbers current?" gets answered. It
 * has to be on screen on every route, not only on the dashboard, so it is
 * asserted here rather than in a page test.
 */
describe('AppShell — connection state', () => {
  it('stays out of the way while the bus is delivering', () => {
    renderShell(createFakeRealtime());
    expect(screen.queryByTestId('connection-banner')).not.toBeInTheDocument();
  });

  it('shows the offline banner above the route content when the link drops', () => {
    renderShell(createFakeRealtime({ phase: 'connecting', connected: false, live: false }));
    const banner = screen.getByTestId('connection-banner');
    expect(banner).toHaveTextContent('SEM CONEXÃO');
    // Above the route content in DOM order — an operator scanning top-down
    // reads the warning before the values it applies to.
    expect(banner.compareDocumentPosition(screen.getByText('conteúdo'))).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
  });

  it('warns even while the socket still calls itself live but has gone quiet', () => {
    renderShell(createFakeRealtime({ stale: true, staleSince: Date.now() - 30_000 }));
    expect(screen.getByTestId('connection-banner')).toHaveTextContent('DADOS DESATUALIZADOS');
  });
});

/**
 * The `[cfg]` menu is the ONLY route to the theme picker, so "hide the admin
 * entries" must never degrade into "the menu does not open". Every assertion
 * here is pinned to the `user` role on purpose: the suite above renders with no
 * session at all, and `admin` sees a different menu — neither would notice a
 * regression that strands a real operator with no way to change theme.
 */
describe('AppShell — [cfg] menu role gating', () => {
  it('opens for a user and offers every theme, with no Administração section', async () => {
    renderShellAs('user');
    // Wait for /auth/me: before it resolves the role is null and the menu is
    // indistinguishable from the deny case.
    await waitFor(() => expect(endpoints.me).toHaveBeenCalled());

    const trigger = screen.getByRole('button', { name: 'Configurações' });
    expect(trigger).toHaveAttribute('aria-expanded', 'false');

    const menu = await openCfgMenu();
    expect(trigger).toHaveAttribute('aria-expanded', 'true');

    expect(within(menu).getByText('Tema')).toBeVisible();
    expect(within(menu).getAllByRole('menuitemradio').map((i) => i.textContent)).toEqual([
      'Optimizer',
      'Optimizer Dark',
      'Recorder',
      'Phosphor',
      'ISA-101',
      'Neon',
    ]);

    expect(within(menu).queryByText('Administração')).not.toBeInTheDocument();
    for (const label of ['Projects', 'Settings', 'Connection', 'Users']) {
      expect(within(menu).queryByRole('menuitem', { name: label })).not.toBeInTheDocument();
    }
  });

  it('lets a user actually apply a theme through that menu', async () => {
    renderShellAs('user');
    await waitFor(() => expect(endpoints.me).toHaveBeenCalled());

    const menu = await openCfgMenu();
    fireEvent.click(within(menu).getByRole('menuitemradio', { name: 'ISA-101' }));

    await waitFor(() =>
      expect(document.documentElement.getAttribute('data-theme')).toBe('isa101'),
    );
    expect(localStorage.getItem('spid.theme')).toBe('isa101');
  });

  it('keeps the admin section for an admin', async () => {
    renderShellAs('admin');
    await waitFor(() => expect(endpoints.me).toHaveBeenCalled());

    const menu = await openCfgMenu();
    await within(menu).findByText('Administração');
    expect(within(menu).getAllByRole('menuitemradio')).toHaveLength(6);
    for (const label of ['Projects', 'Settings', 'Connection', 'Users']) {
      expect(within(menu).getByRole('menuitem', { name: label })).toBeVisible();
    }
  });
});
