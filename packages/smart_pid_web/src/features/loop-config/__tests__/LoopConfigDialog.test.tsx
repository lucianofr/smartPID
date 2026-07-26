import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import type { ControllerResponse, Role } from '@/api/types';
import { makeController } from '@/test/fixtures';
import { createQueryClient, TestProviders } from '@/test/providers';
import { DDC_SECTIONS, LoopConfigDialog } from '../LoopConfigDialog';

const fetchMock = vi.fn();

function renderDialog(
  overrides: Partial<ControllerResponse> = {},
  role: Role = 'admin',
  onClose = vi.fn(),
) {
  sessionStorage.setItem('smart-pid-token', 'jwt');
  vi.spyOn(endpoints, 'me').mockResolvedValue({ user_id: 1, username: role, role });
  const controller = makeController({ id: 5, name: 'PIC-005', description: 'Pressure', ...overrides });
  const queryClient = createQueryClient();
  queryClient.setQueryData(queryKeys.controllers, [controller]);
  return {
    onClose,
    controller,
    ...render(
      <TestProviders queryClient={queryClient}>
        <LoopConfigDialog controller={controller} open onClose={onClose} />
      </TestProviders>,
    ),
  };
}

beforeEach(() => {
  sessionStorage.clear();
  fetchMock.mockReset();
  fetchMock.mockResolvedValue(
    new Response(JSON.stringify({ id: 5 }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  );
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('LoopConfigDialog — execution mode gating', () => {
  it('pins the DDC-only section list', () => {
    expect(DDC_SECTIONS).toEqual([
      'PID Tuning',
      'Scaling & Limits',
      'Filters & IO',
      'Shed & Safety',
      'PID Structure',
      'Integral Type',
    ]);
  });

  it('hides every DCS-owned section while the loop is SUPERVISORY', async () => {
    renderDialog({ execution_mode: 'SUPERVISORY' });
    await screen.findByLabelText('Modo de execução');
    for (const name of DDC_SECTIONS) {
      expect(screen.queryByRole('region', { name })).not.toBeInTheDocument();
    }
  });

  it('reveals them all as soon as the loop is switched to DDC', async () => {
    renderDialog({ execution_mode: 'SUPERVISORY' });
    fireEvent.change(await screen.findByLabelText('Modo de execução'), {
      target: { value: 'DDC' },
    });
    for (const name of DDC_SECTIONS) {
      expect(screen.getByRole('region', { name })).toBeVisible();
    }
  });

  it('keeps identification, scan rate and the OPC-UA bindings in both modes', async () => {
    const view = renderDialog({ execution_mode: 'SUPERVISORY' });
    const always = ['Nome', 'Descrição', 'Taxa de varredura (s)', 'NodeID PV', 'NodeID SP', 'NodeID CO', 'NodeID Ti'];
    for (const label of always) expect(await screen.findByLabelText(label)).toBeInTheDocument();
    view.unmount();

    renderDialog({ execution_mode: 'DDC' });
    for (const label of always) expect(await screen.findByLabelText(label)).toBeInTheDocument();
  });
});

describe('LoopConfigDialog — writes', () => {
  it('PUTs the edited fields', async () => {
    const { onClose } = renderDialog({ execution_mode: 'DDC' });
    fireEvent.change(await screen.findByLabelText('Nome'), { target: { value: 'PIC-006' } });
    fireEvent.change(screen.getByLabelText('Ganho (Kp)'), { target: { value: '2.5' } });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/controllers/5');
    expect((init as RequestInit).method).toBe('PUT');
    const body = JSON.parse((init as RequestInit).body as string) as Record<string, unknown>;
    expect(body.name).toBe('PIC-006');
    expect(body.pid_params).toMatchObject({ gain: 2.5 });
  });

  it('refuses to save an invalid gain band and says why', async () => {
    renderDialog({ execution_mode: 'DDC' });
    fireEvent.change(await screen.findByLabelText('Reset (Ti)'), { target: { value: '0' } });
    expect(await screen.findByText('Reset (Ti) deve ser maior que 0')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Salvar' })).toBeDisabled();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe('LoopConfigDialog — role gating', () => {
  it('gives the user role a read-only view with no write affordances', async () => {
    renderDialog({ execution_mode: 'DDC' }, 'user');
    expect(await screen.findByLabelText('Nome')).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Salvar' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Excluir' })).not.toBeInTheDocument();
  });

  it('requires the tag to be typed back before it will delete', async () => {
    renderDialog();
    fireEvent.click(await screen.findByRole('button', { name: 'Excluir' }));

    const confirm = await screen.findByRole('alertdialog');
    const remove = within(confirm).getByRole('button', { name: 'Excluir definitivamente' });
    expect(remove).toBeDisabled();

    fireEvent.change(within(confirm).getByLabelText('Digite PIC-005 para confirmar'), {
      target: { value: 'PIC-00' },
    });
    expect(remove).toBeDisabled();

    fireEvent.change(within(confirm).getByLabelText('Digite PIC-005 para confirmar'), {
      target: { value: 'PIC-005' },
    });
    expect(remove).toBeEnabled();

    fireEvent.click(remove);
    await waitFor(() => {
      expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('DELETE');
    });
    expect(fetchMock.mock.calls[0][0]).toBe('/api/controllers/5');
  });
});
