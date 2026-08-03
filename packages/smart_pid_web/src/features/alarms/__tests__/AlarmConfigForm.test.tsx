import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/api/client';
import { endpoints } from '@/api/endpoints';
import type { Role } from '@/api/types';
import { createQueryClient, TestProviders } from '@/test/providers';
import { AlarmConfigForm } from '../AlarmConfigForm';
import { ALARM_TYPES, type AlarmThreshold } from '../types';

const LIMITS: Record<string, number> = { HIHI: 95, HI: 80, LO: 20, LOLO: 5, DV_HI: 10, DV_LO: 10 };

function thresholds(): AlarmThreshold[] {
  return ALARM_TYPES.map((alarm_type) => ({
    alarm_type,
    priority: alarm_type === 'HIHI' ? 'CRITICAL' : 'WARNING',
    limit: LIMITS[alarm_type],
    enabled: true,
    deadband: 0.5,
    delay_on_s: 0,
    delay_off_s: 0,
  }));
}

function renderConfig(role: Role = 'admin') {
  localStorage.setItem('smart-pid-token', 'jwt');
  vi.spyOn(endpoints, 'me').mockResolvedValue({ user_id: 1, username: role, role });
  vi.spyOn(endpoints, 'alarmConfig').mockResolvedValue({
    controller_id: 7,
    thresholds: thresholds(),
  });
  return render(
    <TestProviders queryClient={createQueryClient()}>
      <AlarmConfigForm controllerId={7} />
    </TestProviders>,
  );
}

const form = () => screen.queryByRole('form', { name: 'Configuração de alarmes' });

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('AlarmConfigForm capability gating', () => {
  it('shows no form to a plain user — alarms.configure is admin-only', async () => {
    renderConfig('user');
    expect(await screen.findByText('Somente administradores podem configurar alarmes.')).toBeVisible();
    expect(form()).toBeNull();
  });

  it('never fetches the config a user may not see', async () => {
    const config = vi.spyOn(endpoints, 'alarmConfig');
    renderConfig('user');
    await screen.findByText('Somente administradores podem configurar alarmes.');
    expect(config).not.toHaveBeenCalled();
  });

  it('gives an admin the labelled form', async () => {
    renderConfig();
    await waitFor(() => expect(form()).not.toBeNull());
    expect(await screen.findByLabelText('HIHI')).toHaveValue(95);
    expect(screen.getByLabelText('Prioridade HIHI')).toHaveValue('CRITICAL');
    expect(screen.getByLabelText('Banda morta HIHI')).toHaveValue(0.5);
  });
});

describe('AlarmConfigForm validation', () => {
  it('rejects a HIHI that is not above HI, without touching the input', async () => {
    const update = vi.spyOn(endpoints, 'updateAlarmConfig');
    renderConfig();
    const hihi = await screen.findByLabelText('HIHI');

    fireEvent.change(hihi, { target: { value: '70' } });

    expect(screen.getByText('HIHI deve ser maior que HI')).toBeVisible();
    expect(hihi).toHaveValue(70);
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));
    expect(update).not.toHaveBeenCalled();
  });

  it('walks the ordering down the enabled limits', async () => {
    renderConfig();
    const lo = await screen.findByLabelText('LO');
    fireEvent.change(lo, { target: { value: '2' } });
    expect(screen.getByText('LO deve ser maior que LOLO')).toBeVisible();
  });

  it('skips a disabled limit instead of comparing against it', async () => {
    renderConfig();
    const hi = await screen.findByLabelText('HI');
    fireEvent.click(screen.getByRole('switch', { name: 'HI ativo' }));
    fireEvent.change(hi, { target: { value: '1' } });
    // HI is out of the chain, so HIHI is now measured against LO — and passes.
    expect(screen.queryByText(/deve ser maior que/)).toBeNull();
  });

  it('refuses a negative deadband', async () => {
    renderConfig();
    const deadband = await screen.findByLabelText('Banda morta HIHI');
    fireEvent.change(deadband, { target: { value: '-1' } });
    expect(screen.getByText('A banda morta não pode ser negativa')).toBeVisible();
  });
});

describe('AlarmConfigForm persistence', () => {
  it('PUTs the WHOLE threshold array — the backend replaces, it does not merge', async () => {
    const update = vi
      .spyOn(endpoints, 'updateAlarmConfig')
      .mockResolvedValue({ controller_id: 7, thresholds: thresholds() });
    renderConfig();

    fireEvent.change(await screen.findByLabelText('HIHI'), { target: { value: '97' } });
    fireEvent.change(screen.getByLabelText('Prioridade LO'), { target: { value: 'ADVISORY' } });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));

    await waitFor(() => expect(update).toHaveBeenCalledTimes(1));
    const [controllerId, sent] = update.mock.calls[0];
    expect(controllerId).toBe(7);
    expect(sent.map((t) => t.alarm_type)).toEqual([...ALARM_TYPES]);
    expect(sent.find((t) => t.alarm_type === 'HIHI')?.limit).toBe(97);
    expect(sent.find((t) => t.alarm_type === 'LO')?.priority).toBe('ADVISORY');
    expect(await screen.findByText('Configuração salva.')).toBeVisible();
  });

  it('maps a backend 422 onto its field and keeps what was typed', async () => {
    vi.spyOn(endpoints, 'updateAlarmConfig').mockRejectedValue(
      new ApiError(422, 'validation', 'invalid', [
        { loc: ['body', 'thresholds', 0, 'limit'], msg: 'limit acima da faixa', type: 'value_error' },
      ]),
    );
    renderConfig();

    fireEvent.change(await screen.findByLabelText('HIHI'), { target: { value: '9999' } });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));

    expect(await screen.findByText('limit acima da faixa')).toBeVisible();
    expect(screen.getByLabelText('HIHI')).toHaveValue(9999);
  });

  it('surfaces a load failure with a retry instead of an empty form', async () => {
    localStorage.setItem('smart-pid-token', 'jwt');
    vi.spyOn(endpoints, 'me').mockResolvedValue({ user_id: 1, username: 'admin', role: 'admin' });
    vi.spyOn(endpoints, 'alarmConfig').mockRejectedValue(new ApiError(500, 'server', 'boom'));
    render(
      <TestProviders queryClient={createQueryClient()}>
        <AlarmConfigForm controllerId={7} />
      </TestProviders>,
    );
    expect(
      await screen.findByText('Não foi possível carregar a configuração de alarmes.'),
    ).toBeVisible();
  });
});
