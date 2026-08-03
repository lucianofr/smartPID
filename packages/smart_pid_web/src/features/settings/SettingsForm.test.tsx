import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { endpoints } from '@/api/endpoints';
import type { Role } from '@/api/types';
import { createQueryClient, TestProviders } from '@/test/providers';
import { SettingsForm } from './SettingsForm';
import { DEFAULT_PREFERENCES, PREFERENCES_KEY } from './settingsTypes';
import { readPreferences, reloadPreferences } from './useSettings';

function renderSettings(role: Role = 'admin') {
  localStorage.setItem('smart-pid-token', 'jwt');
  // The preference store is module-level; a real page load re-reads storage.
  reloadPreferences();
  vi.spyOn(endpoints, 'me').mockResolvedValue({ user_id: 1, username: role, role });
  return render(
    <TestProviders queryClient={createQueryClient()}>
      <SettingsForm />
    </TestProviders>,
  );
}

const form = () => screen.queryByRole('form', { name: 'Configurações' });
const stored = () => JSON.parse(localStorage.getItem(PREFERENCES_KEY) ?? 'null') as unknown;

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('SettingsForm capability gating', () => {
  it('shows no form to a plain user — settings.manage is admin-only', async () => {
    renderSettings('user');
    expect(
      await screen.findByText('Somente administradores podem alterar as configurações.'),
    ).toBeVisible();
    expect(form()).toBeNull();
  });

  it('gives an admin the labelled form seeded from the stored preferences', async () => {
    localStorage.setItem(
      PREFERENCES_KEY,
      JSON.stringify({ ...DEFAULT_PREFERENCES, numberDecimals: 3 }),
    );
    renderSettings();
    await waitFor(() => expect(form()).not.toBeNull());
    expect(screen.getByLabelText('Casas decimais')).toHaveValue(3);
    expect(screen.getByLabelText('Janela de tendência (s)')).toHaveValue(120);
  });
});

describe('SettingsForm persistence', () => {
  it('persists the whole preference set on Salvar', async () => {
    renderSettings();
    await waitFor(() => expect(form()).not.toBeNull());

    fireEvent.change(screen.getByLabelText('Janela de tendência (s)'), {
      target: { value: '300' },
    });
    fireEvent.click(screen.getByRole('switch', { name: 'Confirmar ações destrutivas' }));
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));

    expect(stored()).toEqual({
      trendWindowSeconds: 300,
      numberDecimals: 2,
      confirmDestructive: false,
    });
    expect(readPreferences().trendWindowSeconds).toBe(300);
    expect(await screen.findByText('Configurações salvas.')).toBeVisible();
  });

  it('rejects an out-of-range value, keeps what was typed and writes nothing', async () => {
    renderSettings();
    await waitFor(() => expect(form()).not.toBeNull());

    fireEvent.change(screen.getByLabelText('Casas decimais'), { target: { value: '9' } });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));

    expect(await screen.findByText('Use um inteiro entre 0 e 6.')).toBeVisible();
    expect(screen.getByLabelText('Casas decimais')).toHaveValue(9);
    expect(stored()).toBeNull();
  });

  it('restores the defaults and clears the stored override', async () => {
    localStorage.setItem(
      PREFERENCES_KEY,
      JSON.stringify({ ...DEFAULT_PREFERENCES, numberDecimals: 5 }),
    );
    renderSettings();
    await waitFor(() => expect(form()).not.toBeNull());
    expect(screen.getByLabelText('Casas decimais')).toHaveValue(5);

    fireEvent.click(screen.getByRole('button', { name: 'Restaurar padrões' }));

    expect(localStorage.getItem(PREFERENCES_KEY)).toBeNull();
    expect(screen.getByLabelText('Casas decimais')).toHaveValue(DEFAULT_PREFERENCES.numberDecimals);
    expect(readPreferences()).toEqual(DEFAULT_PREFERENCES);
  });
});
