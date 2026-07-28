import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { endpoints } from '@/api/endpoints';
import type { ProjectItem, Role } from '@/api/types';
import { createQueryClient, TestProviders } from '@/test/providers';
import { WELCOME_SEEN_KEY, WelcomeGate } from './WelcomeGate';

const UNIT_A: ProjectItem = { name: 'unit-a', controller_count: 3, size_bytes: 2048 };

function LocationProbe() {
  return <span data-testid="pathname">{useLocation().pathname}</span>;
}

function renderGate(role: Role = 'admin', projects: ProjectItem[] = [UNIT_A]) {
  sessionStorage.setItem('smart-pid-token', 'jwt');
  vi.spyOn(endpoints, 'me').mockResolvedValue({ user_id: 1, username: role, role });
  const list = vi.spyOn(endpoints, 'projectList').mockResolvedValue({ projects });
  render(
    <TestProviders queryClient={createQueryClient()} initialEntries={['/']}>
      <WelcomeGate />
      <LocationProbe />
    </TestProviders>,
  );
  return list;
}

const dialog = () => screen.queryByRole('dialog', { name: 'Abrir projeto' });

beforeEach(() => {
  sessionStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('WelcomeGate', () => {
  it('offers the project list to an admin on the first authenticated view', async () => {
    renderGate();
    await waitFor(() => expect(dialog()).not.toBeNull());
    expect(screen.getByText('unit-a')).toBeVisible();
  });

  it('stays closed once the session has already seen it', async () => {
    sessionStorage.setItem(WELCOME_SEEN_KEY, '1');
    const list = renderGate();
    await waitFor(() => expect(list).not.toHaveBeenCalled());
    expect(dialog()).toBeNull();
  });

  it('never opens for a user — /project/list is admin-only', async () => {
    const list = renderGate('user');
    await waitFor(() => expect(list).not.toHaveBeenCalled());
    expect(dialog()).toBeNull();
  });

  it('stays closed when the deployment has no projects yet', async () => {
    renderGate('admin', []);
    await waitFor(() => expect(endpoints.projectList).toHaveBeenCalled());
    expect(dialog()).toBeNull();
  });

  it('opens the chosen project, marks the session and lands on the dashboard', async () => {
    const open = vi
      .spyOn(endpoints, 'openProject')
      .mockResolvedValue({ name: 'unit-a', path: '/p/unit-a.spid', controller_count: 3 });
    renderGate();
    await waitFor(() => expect(dialog()).not.toBeNull());

    fireEvent.click(screen.getByRole('button', { name: 'Open unit-a' }));

    await waitFor(() => expect(open).toHaveBeenCalledWith('unit-a'));
    await waitFor(() => expect(dialog()).toBeNull());
    expect(sessionStorage.getItem(WELCOME_SEEN_KEY)).toBe('1');
    expect(screen.getByTestId('pathname')).toHaveTextContent('/');
  });

  it('dismissing marks the session so it never reopens', async () => {
    renderGate();
    await waitFor(() => expect(dialog()).not.toBeNull());

    fireEvent.click(screen.getByRole('button', { name: 'Agora não' }));

    await waitFor(() => expect(dialog()).toBeNull());
    expect(sessionStorage.getItem(WELCOME_SEEN_KEY)).toBe('1');
  });

  it('routes to the projects page for anything beyond opening', async () => {
    renderGate();
    await waitFor(() => expect(dialog()).not.toBeNull());

    fireEvent.click(screen.getByRole('button', { name: 'Gerenciar projetos' }));

    await waitFor(() => expect(screen.getByTestId('pathname')).toHaveTextContent('/projects'));
    expect(sessionStorage.getItem(WELCOME_SEEN_KEY)).toBe('1');
  });
});
