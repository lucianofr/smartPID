import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { endpoints } from '@/api/endpoints';
import type { Role } from '@/api/types';
import { createQueryClient, TestProviders } from '@/test/providers';
import { AlarmsPage } from './AlarmsPage';

function renderPage(role: Role) {
  localStorage.setItem('smart-pid-token', 'jwt');
  vi.spyOn(endpoints, 'me').mockResolvedValue({ user_id: 1, username: role, role });
  vi.spyOn(endpoints, 'activeAlarms').mockResolvedValue([]);
  vi.spyOn(endpoints, 'controllers').mockResolvedValue([]);
  return render(
    <TestProviders queryClient={createQueryClient()}>
      <AlarmsPage />
    </TestProviders>,
  );
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('AlarmsPage', () => {
  it('opens on the active alarms and keeps the plant-wide footer', async () => {
    renderPage('admin');
    expect(await screen.findByRole('tab', { name: 'Ativos' })).toHaveAttribute(
      'data-state',
      'active',
    );
    expect(screen.getByRole('region', { name: 'Alarmes ativos' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'ACK ALL' })).toBeVisible();
  });

  it('offers configuration only to an admin', async () => {
    renderPage('admin');
    expect(await screen.findByRole('tab', { name: 'Configuração' })).toBeVisible();
  });

  it('hides the configuration tab from a plain user who may still acknowledge', async () => {
    renderPage('user');
    await screen.findByRole('tab', { name: 'Ativos' });
    await waitFor(() => expect(screen.queryByRole('tab', { name: 'Configuração' })).toBeNull());
    expect(screen.getByRole('tab', { name: 'Histórico' })).toBeVisible();
  });
});
