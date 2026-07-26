import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
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
