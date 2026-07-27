import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { endpoints } from '@/api/endpoints';
import type { Role } from '@/api/types';
import { TestProviders } from '@/test/providers';
import { AppShell } from './AppShell';
import { appRoutes, cfgRoutes, commandRoutes, navRoutes } from './routes';

function renderShell() {
  return render(
    <TestProviders>
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
  sessionStorage.setItem('smart-pid-token', 'jwt');
  vi.spyOn(endpoints, 'me').mockResolvedValue({ user_id: 1, username: role, role });
  vi.spyOn(endpoints, 'projectList').mockResolvedValue({ projects: [] });
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
    expect(root?.command?.label).toBe('Ir para Malhas');
  });

  it('sorts nav, cfg and command projections by order', () => {
    const routes = [
      { path: '/b', element: () => null, nav: { label: 'B', order: 20 }, command: { label: 'B' } },
      { path: '/a', element: () => null, nav: { label: 'A', order: 10 }, command: { label: 'A' } },
      { path: '/c', element: () => null, cfg: { label: 'C', order: 30 }, command: { label: 'C' } },
      { path: '/d', element: () => null, cfg: { label: 'D', order: 5 }, command: { label: 'D' } },
      { path: '/e', element: () => null, command: { label: 'E' } },
    ];
    expect(navRoutes(routes).map((r) => r.nav.label)).toEqual(['A', 'B']);
    expect(cfgRoutes(routes).map((r) => r.cfg.label)).toEqual(['D', 'C']);
    expect(commandRoutes(routes).map((r) => r.command.label)).toEqual(['A', 'B', 'D', 'C', 'E']);
  });
});

describe('AppShell', () => {
  it('renders registry-backed top navigation and logout', () => {
    renderShell();
    expect(screen.getByRole('link', { name: 'Loops' })).toHaveAttribute('href', '/');
    expect(screen.getByRole('button', { name: 'Comandos' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'Configurações' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'Sair' })).toBeVisible();
    expect(screen.getByText('conteúdo')).toBeVisible();
  });

  it('clears the session when Sair is pressed', () => {
    sessionStorage.setItem('smart-pid-token', 'jwt');
    renderShell();
    fireEvent.click(screen.getByRole('button', { name: 'Sair' }));
    expect(sessionStorage.getItem('smart-pid-token')).toBeNull();
  });

  it('opens the command palette with the bare k key', () => {
    renderShell();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    fireEvent.keyDown(document.body, { key: 'k' });
    expect(screen.getByRole('dialog', { name: 'Paleta de comandos' })).toBeVisible();
    expect(screen.getByText('Ir para Malhas')).toBeVisible();
  });

  it('ignores k typed inside an editable field', () => {
    renderShell();
    const input = document.createElement('input');
    document.body.appendChild(input);
    input.focus();
    fireEvent.keyDown(input, { key: 'k' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    input.remove();
  });

  it('ignores k when it carries a modifier', () => {
    renderShell();
    fireEvent.keyDown(document.body, { key: 'k', ctrlKey: true });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
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
      'Recorder',
      'Phosphor',
      'ISA-101',
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
    expect(within(menu).getAllByRole('menuitemradio')).toHaveLength(3);
    for (const label of ['Projects', 'Settings', 'Connection', 'Users']) {
      expect(within(menu).getByRole('menuitem', { name: label })).toBeVisible();
    }
  });
});
