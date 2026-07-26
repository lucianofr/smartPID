import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import type { MeResponse } from '@/api/types';
import type { Role } from '@/api/types';
import { ff, makeController, statusEnvelope } from '@/test/fixtures';
import { createFakeRealtime, createQueryClient, TestProviders } from '@/test/providers';
import { Faceplate } from './Faceplate';

const scale = { euMin: 0, euMax: 200, unit: '°C' };

function me(role: Role): MeResponse {
  return { user_id: 1, username: role, role };
}

function renderFaceplate(role: Role = 'admin') {
  sessionStorage.setItem('smart-pid-token', 'jwt');
  vi.spyOn(endpoints, 'me').mockResolvedValue(me(role));
  const queryClient = createQueryClient();
  queryClient.setQueryData(queryKeys.controllers, [makeController({ id: 5, name: 'PIC-005' })]);
  const realtime = createFakeRealtime();
  return {
    ...render(
      <TestProviders queryClient={queryClient} realtime={realtime.value}>
        <Faceplate controllerId={5} tag="PIC-005" description="Pressure" scale={scale} />
      </TestProviders>,
    ),
    realtime,
  };
}

beforeEach(() => {
  sessionStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('Faceplate', () => {
  it('is a labelled complementary region for the loop', async () => {
    renderFaceplate();
    expect(await screen.findByRole('complementary', { name: 'Faceplate PIC-005' })).toBeVisible();
  });

  it('renders PV, SP and CO on their engineering bars', async () => {
    const { realtime } = renderFaceplate();
    act(() => {
      realtime.emit(statusEnvelope(5, 1, { pv: ff(150.2), sp: ff(152), co: ff(64) }));
    });
    const fp = await screen.findByRole('complementary', { name: 'Faceplate PIC-005' });
    expect(within(fp).getByText('150.2')).toBeVisible();
    expect(within(fp).getByText('152.0')).toBeVisible();
    expect(within(fp).getByRole('meter', { name: 'PV' })).toHaveAttribute('aria-valuenow', '150.2');
    expect(within(fp).getByRole('meter', { name: 'PV' })).toHaveAttribute('aria-valuemax', '200');
    const co = within(fp).getByRole('meter', { name: 'CO' });
    expect(co).toHaveAttribute('aria-valuenow', '64');
    expect(co).toHaveAttribute('aria-valuetext', '64.0 %');
  });

  it('shows the mode as a numeric badge and the stats block', async () => {
    const { realtime } = renderFaceplate();
    act(() => {
      realtime.emit(statusEnvelope(5, 1, { mode: 'AUTO' }));
      realtime.emit({
        type: 'stats',
        loop_id: 5,
        seq: 2,
        ts: 2,
        data: {
          iae: 12.4,
          itae: 0,
          ise: 0,
          mse: 0,
          std_dev: 0,
          total_variation: 0,
          variability_sp: 0,
          variability_range: 0.031,
          mean_abs_error: 0,
          pk_pk_error: 0,
          reversals: 0,
          zero_crossings: 0,
          recent_pk_pk_error: 0,
          recent_reversals: 0,
          tv_per_sample: 0,
          osc: 0,
          sample_count: 10,
        },
      });
    });
    expect(await screen.findByText('AUTO', { selector: 'span.numeric' })).toBeVisible();
    expect(screen.getByText('12.4')).toBeVisible();
    expect(screen.getByText('3.1%')).toBeVisible();
  });

  it('keeps AUTO/MAN, setpoint and output controls for the user role', async () => {
    renderFaceplate('user');
    expect(await screen.findByRole('button', { name: 'AUTO' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'MAN' })).toBeVisible();
    expect(screen.getByLabelText('Setpoint')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Set setpoint' })).toBeVisible();
    expect(screen.getByRole('slider', { name: 'Manual CO' })).toBeInTheDocument();
  });

  it('omits Apply tuning for the user role and shows it for admin', async () => {
    const view = renderFaceplate('user');
    await screen.findByRole('button', { name: 'AUTO' });
    expect(screen.queryByRole('button', { name: 'Apply tuning' })).not.toBeInTheDocument();
    view.unmount();

    renderFaceplate('admin');
    expect(await screen.findByRole('button', { name: 'Apply tuning' })).toBeVisible();
  });

  it('posts the mode command when a mode button is pressed', async () => {
    const setMode = vi.spyOn(endpoints, 'setMode').mockResolvedValue({ ok: true });
    renderFaceplate();
    fireEvent.click(await screen.findByRole('button', { name: 'MAN' }));
    await waitFor(() => expect(setMode).toHaveBeenCalledWith(5, 'MAN'));
  });

  it('posts the typed setpoint', async () => {
    const setSetpoint = vi.spyOn(endpoints, 'setSetpoint').mockResolvedValue({ ok: true });
    renderFaceplate();
    fireEvent.change(await screen.findByLabelText('Setpoint'), { target: { value: '61.5' } });
    fireEvent.click(screen.getByRole('button', { name: 'Set setpoint' }));
    await waitFor(() => expect(setSetpoint).toHaveBeenCalledWith(5, 61.5));
  });

  it('enables the manual output only in MAN', async () => {
    const { realtime } = renderFaceplate();
    act(() => {
      realtime.emit(statusEnvelope(5, 1, { mode: 'AUTO' }));
    });
    expect(await screen.findByRole('button', { name: 'Set output' })).toBeDisabled();
    act(() => {
      realtime.emit(statusEnvelope(5, 2, { mode: 'MAN' }));
    });
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Set output' })).toBeEnabled(),
    );
  });
});
