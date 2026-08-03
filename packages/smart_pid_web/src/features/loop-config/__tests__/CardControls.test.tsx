import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { endpoints } from '@/api/endpoints';
import type { Role } from '@/api/types';
import { createQueryClient, TestProviders } from '@/test/providers';
import { CardControls } from '../CardControls';

function renderControls(
  props: Partial<React.ComponentProps<typeof CardControls>> = {},
  role: Role = 'admin',
) {
  localStorage.setItem('smart-pid-token', 'jwt');
  vi.spyOn(endpoints, 'me').mockResolvedValue({ user_id: 1, username: role, role });
  return render(
    <TestProviders queryClient={createQueryClient()}>
      <CardControls controllerId={5} mode="AUTO" {...props} />
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

describe('CardControls', () => {
  it('sends the typed setpoint for the loop it is mounted on', async () => {
    const setpoint = vi.spyOn(endpoints, 'setSetpoint').mockResolvedValue({ ok: true });
    renderControls();

    fireEvent.change(await screen.findByRole('spinbutton', { name: 'Setpoint' }), {
      target: { value: '60' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Set setpoint' }));

    await waitFor(() => expect(setpoint).toHaveBeenCalledWith(5, 60));
  });

  it('locks manual output while the loop is not in MAN', async () => {
    renderControls();
    expect(await screen.findByRole('button', { name: 'Set output' })).toBeDisabled();
  });

  it('unlocks manual output in MAN and writes the value', async () => {
    const setOutput = vi.spyOn(endpoints, 'setOutput').mockResolvedValue({ ok: true });
    renderControls({ mode: 'MAN' });

    const button = await screen.findByRole('button', { name: 'Set output' });
    expect(button).toBeEnabled();
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Saída' }), {
      target: { value: '42.5' },
    });
    fireEvent.click(button);

    await waitFor(() => expect(setOutput).toHaveBeenCalledWith(5, 42.5));
  });

  it('keeps the mode selector native so the full block enum stays reachable', async () => {
    const setMode = vi.spyOn(endpoints, 'setMode').mockResolvedValue({ ok: true });
    renderControls();

    const select = await screen.findByRole('combobox', { name: 'Mode' });
    expect(select.tagName).toBe('SELECT');
    expect(select).toHaveValue('AUTO');
    // The block enum, not just the AUTO/MAN pair the faceplate offers.
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual([
      'OOS',
      'IMAN',
      'LO',
      'MAN',
      'AUTO',
      'CAS',
      'RCAS',
      'ROUT',
      'BYPASS',
    ]);

    fireEvent.change(select, { target: { value: 'MAN' } });
    await waitFor(() => expect(setMode).toHaveBeenCalledWith(5, 'MAN'));
  });

  it('blocks a setpoint outside the loop SP limits before it reaches the wire', async () => {
    const setpoint = vi.spyOn(endpoints, 'setSetpoint').mockResolvedValue({ ok: true });
    renderControls({ spRange: { min: 0, max: 100 } });

    fireEvent.change(await screen.findByRole('spinbutton', { name: 'Setpoint' }), {
      target: { value: '160' },
    });
    expect(await screen.findByText('Setpoint deve estar entre 0 e 100')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Set setpoint' })).toBeDisabled();
    expect(setpoint).not.toHaveBeenCalled();
  });

  it('renders only the requested subset so one surface never duplicates another', async () => {
    renderControls({ controls: ['mode'] });
    expect(await screen.findByRole('combobox', { name: 'Mode' })).toBeVisible();
    expect(screen.queryByRole('spinbutton', { name: 'Setpoint' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Set output' })).not.toBeInTheDocument();
  });

  it('renders nothing without loop.operate', async () => {
    const { container } = renderControls({}, 'user');
    await screen.findByRole('spinbutton', { name: 'Setpoint' });
    expect(container).not.toBeEmptyDOMElement();

    // `viewer` is not a role the backend issues; a null role is the deny case.
    localStorage.clear();
    sessionStorage.clear();
    const denied = render(
      <TestProviders queryClient={createQueryClient()}>
        <CardControls controllerId={5} mode="AUTO" />
      </TestProviders>,
    );
    expect(denied.container.querySelector('[data-testid="card-controls"]')).toBeNull();
  });
});

/**
 * §9 makes `user` the OPERATOR role, and the backend agrees — it answers 200 to
 * mode/setpoint/output from an `operador` token. The suite above drives every
 * write as `admin` and the one `user` test only asserts the controls RENDER, so
 * a capability regression that left the buttons on screen but stopped the wire
 * would pass it. These drive the writes as `user` and assert the call.
 */
describe('CardControls — the user role commands the loop', () => {
  it('writes a setpoint', async () => {
    const setpoint = vi.spyOn(endpoints, 'setSetpoint').mockResolvedValue({ ok: true });
    renderControls({}, 'user');

    fireEvent.change(await screen.findByRole('spinbutton', { name: 'Setpoint' }), {
      target: { value: '57' },
    });
    const button = screen.getByRole('button', { name: 'Set setpoint' });
    expect(button).toBeEnabled();
    fireEvent.click(button);

    await waitFor(() => expect(setpoint).toHaveBeenCalledWith(5, 57));
  });

  it('writes a block mode', async () => {
    const setMode = vi.spyOn(endpoints, 'setMode').mockResolvedValue({ ok: true });
    renderControls({}, 'user');

    fireEvent.change(await screen.findByRole('combobox', { name: 'Mode' }), {
      target: { value: 'MAN' },
    });

    await waitFor(() => expect(setMode).toHaveBeenCalledWith(5, 'MAN'));
  });

  it('writes a manual output in MAN', async () => {
    const setOutput = vi.spyOn(endpoints, 'setOutput').mockResolvedValue({ ok: true });
    renderControls({ mode: 'MAN' }, 'user');

    const button = await screen.findByRole('button', { name: 'Set output' });
    expect(button).toBeEnabled();
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Saída' }), {
      target: { value: '12' },
    });
    fireEvent.click(button);

    await waitFor(() => expect(setOutput).toHaveBeenCalledWith(5, 12));
  });

  it('disables Set setpoint only while the box is empty, not because of the role', async () => {
    renderControls({}, 'user');
    const input = await screen.findByRole('spinbutton', { name: 'Setpoint' });
    // The reported "user cannot set SP" symptom is this empty-input guard.
    expect(screen.getByRole('button', { name: 'Set setpoint' })).toBeDisabled();

    fireEvent.change(input, { target: { value: '40' } });
    expect(screen.getByRole('button', { name: 'Set setpoint' })).toBeEnabled();
  });
});
