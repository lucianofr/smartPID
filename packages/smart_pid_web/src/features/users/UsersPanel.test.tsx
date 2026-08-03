import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/api/client';
import { endpoints } from '@/api/endpoints';
import type { Role, UserRow } from '@/api/types';
import { createQueryClient, TestProviders } from '@/test/providers';
import { UsersPanel } from './UsersPanel';

const ADMIN: UserRow = {
  id: 1,
  username: 'admin',
  role: 'admin',
  active: true,
  created_at: '2026-01-01',
};
const OPERATOR: UserRow = {
  id: 2,
  username: 'operador',
  role: 'user',
  active: true,
  created_at: '2026-01-02',
};
const RETIRED: UserRow = {
  id: 3,
  username: 'antigo',
  role: 'user',
  active: false,
  created_at: '2026-01-03',
};

function renderPanel(role: Role = 'admin', users: UserRow[] = [ADMIN, OPERATOR, RETIRED]) {
  localStorage.setItem('smart-pid-token', 'jwt');
  vi.spyOn(endpoints, 'me').mockResolvedValue({ user_id: 1, username: role, role });
  const list = vi.spyOn(endpoints, 'users').mockResolvedValue(users);
  render(
    <TestProviders queryClient={createQueryClient()}>
      <UsersPanel />
    </TestProviders>,
  );
  return list;
}

const row = (name: string) => screen.getByRole('row', { name: new RegExp(name) });

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('UsersPanel roster', () => {
  it('lists every account with its role and whether it is still active', async () => {
    renderPanel();
    expect(await screen.findByRole('cell', { name: 'operador' })).toBeVisible();
    expect(within(row('operador')).getByText('user')).toBeVisible();
    expect(within(row('antigo')).getByText('Inativo')).toBeVisible();
  });

  it('refuses the whole panel to a user — users.manage is admin-only', async () => {
    localStorage.setItem('smart-pid-token', 'jwt');
    vi.spyOn(endpoints, 'me').mockResolvedValue({ user_id: 2, username: 'op', role: 'user' });
    const list = vi.spyOn(endpoints, 'users');
    render(
      <TestProviders queryClient={createQueryClient()}>
        <UsersPanel />
      </TestProviders>,
    );
    expect(
      await screen.findByText('Somente administradores podem gerenciar usuários.'),
    ).toBeVisible();
    expect(list).not.toHaveBeenCalled();
  });
});

describe('UsersPanel creation', () => {
  it('creates an account with the chosen role', async () => {
    const create = vi.spyOn(endpoints, 'createUser').mockResolvedValue(OPERATOR);
    renderPanel();
    fireEvent.click(await screen.findByRole('button', { name: 'Novo usuário' }));

    fireEvent.change(await screen.findByLabelText('Usuário'), { target: { value: 'operador' } });
    fireEvent.change(screen.getByLabelText('Senha'), { target: { value: 'segredo123' } });
    fireEvent.change(screen.getByLabelText('Perfil'), { target: { value: 'user' } });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));

    await waitFor(() =>
      expect(create).toHaveBeenCalledWith({
        username: 'operador',
        password: expect.any(String) as string,
        role: 'user',
      }),
    );
  });

  it('keeps the form editable and names the clash when the username exists (409)', async () => {
    vi.spyOn(endpoints, 'createUser').mockRejectedValue(
      new ApiError(409, 'conflict', 'Username already exists'),
    );
    renderPanel();
    fireEvent.click(await screen.findByRole('button', { name: 'Novo usuário' }));

    fireEvent.change(await screen.findByLabelText('Usuário'), { target: { value: 'admin' } });
    fireEvent.change(screen.getByLabelText('Senha'), { target: { value: 'segredo123' } });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));

    expect(await screen.findByText('Nome de usuário já existe.')).toBeVisible();
    expect(screen.getByLabelText('Usuário')).toHaveValue('admin');
    expect(screen.getByLabelText('Usuário')).toBeEnabled();
  });

  it('will not submit an account without a username and password', async () => {
    const create = vi.spyOn(endpoints, 'createUser');
    renderPanel();
    fireEvent.click(await screen.findByRole('button', { name: 'Novo usuário' }));
    await screen.findByLabelText('Usuário');

    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));

    expect(await screen.findByText('Informe um nome de usuário.')).toBeVisible();
    expect(screen.getByText('Informe uma senha.')).toBeVisible();
    expect(create).not.toHaveBeenCalled();
  });
});

describe('UsersPanel changes to an existing account', () => {
  it('changes a role without touching the password', async () => {
    const update = vi
      .spyOn(endpoints, 'updateUser')
      .mockResolvedValue({ ...OPERATOR, role: 'admin' });
    renderPanel();
    await screen.findByRole('cell', { name: 'operador' });

    fireEvent.click(within(row('operador')).getByRole('button', { name: 'Editar' }));
    fireEvent.change(await screen.findByLabelText('Perfil'), { target: { value: 'admin' } });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));

    await waitFor(() => expect(update).toHaveBeenCalledWith(2, { role: 'admin' }));
  });

  it('sends a new password only when one was typed', async () => {
    const update = vi.spyOn(endpoints, 'updateUser').mockResolvedValue(OPERATOR);
    renderPanel();
    await screen.findByRole('cell', { name: 'operador' });

    fireEvent.click(within(row('operador')).getByRole('button', { name: 'Editar' }));
    fireEvent.change(await screen.findByLabelText('Nova senha'), {
      target: { value: 'outra-senha' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));

    await waitFor(() => expect(update).toHaveBeenCalledWith(2, { password: 'outra-senha' }));
  });

  it('deactivates an active account and reactivates an inactive one', async () => {
    const deactivate = vi
      .spyOn(endpoints, 'deactivateUser')
      .mockResolvedValue({ ...OPERATOR, active: false });
    const update = vi.spyOn(endpoints, 'updateUser').mockResolvedValue({ ...RETIRED, active: true });
    renderPanel();
    await screen.findByRole('cell', { name: 'operador' });

    fireEvent.click(within(row('operador')).getByRole('button', { name: 'Desativar' }));
    await waitFor(() => expect(deactivate).toHaveBeenCalledWith(2));

    fireEvent.click(within(row('antigo')).getByRole('button', { name: 'Reativar' }));
    await waitFor(() => expect(update).toHaveBeenCalledWith(3, { active: true }));
  });

  it('names the last-admin rule instead of a generic failure', async () => {
    vi.spyOn(endpoints, 'deactivateUser').mockRejectedValue(
      new ApiError(409, 'conflict', 'Cannot demote or deactivate the last active admin'),
    );
    renderPanel('admin', [ADMIN, OPERATOR]);
    // `admin` is both a username and a role, so anchor on the row, not a cell.
    await screen.findByRole('row', { name: /admin/ });

    fireEvent.click(within(row('admin')).getByRole('button', { name: 'Desativar' }));

    expect(
      await screen.findByText('Não é possível desativar o último administrador.'),
    ).toBeVisible();
  });

  it('keeps the edit dialog open when demoting the last admin is refused', async () => {
    vi.spyOn(endpoints, 'updateUser').mockRejectedValue(
      new ApiError(409, 'conflict', 'Cannot demote or deactivate the last active admin'),
    );
    renderPanel('admin', [ADMIN, OPERATOR]);
    await screen.findByRole('row', { name: /admin/ });

    fireEvent.click(within(row('admin')).getByRole('button', { name: 'Editar' }));
    fireEvent.change(await screen.findByLabelText('Perfil'), { target: { value: 'user' } });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));

    expect(
      await screen.findByText('Não é possível desativar o último administrador.'),
    ).toBeVisible();
    expect(screen.getByRole('dialog')).toBeVisible();
    expect(screen.getByLabelText('Perfil')).toHaveValue('user');
  });
});
