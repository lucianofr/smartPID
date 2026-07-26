import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/api/client';
import { endpoints } from '@/api/endpoints';
import type { ProjectItem, Role } from '@/api/types';
import { createQueryClient, TestProviders } from '@/test/providers';
import { DEFAULT_PREFERENCES, PREFERENCES_KEY } from '@/features/settings/settingsTypes';
import { reloadPreferences } from '@/features/settings/useSettings';
import { ProjectImportDropzone } from './ProjectImportDropzone';
import { ProjectList } from './ProjectList';
import { ProjectsPage } from '@/pages/ProjectsPage';

const UNIT_A: ProjectItem = { name: 'unit-a', controller_count: 3, size_bytes: 2048 };
const UNIT_B: ProjectItem = { name: 'unit-b', controller_count: 0, size_bytes: 100 };

function LocationProbe() {
  return <span data-testid="pathname">{useLocation().pathname}</span>;
}

function mockSession(role: Role) {
  sessionStorage.setItem('smart-pid-token', 'jwt');
  reloadPreferences();
  vi.spyOn(endpoints, 'me').mockResolvedValue({ user_id: 1, username: role, role });
}

function renderList(role: Role = 'admin', projects: ProjectItem[] = [UNIT_A, UNIT_B]) {
  mockSession(role);
  vi.spyOn(endpoints, 'projectList').mockResolvedValue({ projects });
  return render(
    <TestProviders queryClient={createQueryClient()} initialEntries={['/projects']}>
      <ProjectList />
      <LocationProbe />
    </TestProviders>,
  );
}

const row = (name: string) => screen.getByRole('row', { name: new RegExp(name) });

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('ProjectList', () => {
  it('lists every project with its loop count and size', async () => {
    renderList();
    expect(await screen.findByRole('cell', { name: 'unit-a' })).toBeVisible();
    expect(within(row('unit-a')).getByText('3')).toBeVisible();
    expect(within(row('unit-a')).getByText('2.0 KB')).toBeVisible();
    expect(screen.getByRole('cell', { name: 'unit-b' })).toBeVisible();
  });

  it('opens a project and lands on the dashboard', async () => {
    const open = vi
      .spyOn(endpoints, 'openProject')
      .mockResolvedValue({ name: 'unit-a', path: '/p/unit-a.spid', controller_count: 3 });
    renderList();
    await screen.findByRole('cell', { name: 'unit-a' });

    fireEvent.click(within(row('unit-a')).getByRole('button', { name: 'Open' }));

    await waitFor(() => expect(open).toHaveBeenCalledWith('unit-a'));
    await waitFor(() => expect(screen.getByTestId('pathname')).toHaveTextContent('/'));
  });

  it('asks before deleting while confirmDestructive is on, and honours a refusal', async () => {
    const remove = vi.spyOn(endpoints, 'deleteProject').mockResolvedValue(undefined);
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    renderList();
    await screen.findByRole('cell', { name: 'unit-a' });

    fireEvent.click(within(row('unit-a')).getByRole('button', { name: 'Delete' }));

    expect(confirm).toHaveBeenCalledWith('Excluir o projeto "unit-a"?');
    expect(remove).not.toHaveBeenCalled();
  });

  it('deletes without a prompt once confirmDestructive is off', async () => {
    localStorage.setItem(
      PREFERENCES_KEY,
      JSON.stringify({ ...DEFAULT_PREFERENCES, confirmDestructive: false }),
    );
    const remove = vi.spyOn(endpoints, 'deleteProject').mockResolvedValue(undefined);
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    renderList();
    await screen.findByRole('cell', { name: 'unit-a' });

    fireEvent.click(within(row('unit-a')).getByRole('button', { name: 'Delete' }));

    await waitFor(() => expect(remove).toHaveBeenCalledWith('unit-a'));
    expect(confirm).not.toHaveBeenCalled();
  });

  it('surfaces the real reason when the active project cannot be deleted', async () => {
    vi.spyOn(endpoints, 'deleteProject').mockRejectedValue(
      new ApiError(409, 'conflict', "Cannot delete the active project 'unit-a'"),
    );
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    renderList();
    await screen.findByRole('cell', { name: 'unit-a' });

    fireEvent.click(within(row('unit-a')).getByRole('button', { name: 'Delete' }));

    expect(await screen.findByText('Não é possível excluir o projeto ativo.')).toBeVisible();
  });

  it('downloads the active project as a .spid blob', async () => {
    const blob = new Blob(['spid']);
    const download = vi.spyOn(endpoints, 'downloadProject').mockResolvedValue(blob);
    const createUrl = vi.fn().mockReturnValue('blob:x');
    vi.stubGlobal('URL', { createObjectURL: createUrl, revokeObjectURL: vi.fn() });
    renderList();
    await screen.findByRole('cell', { name: 'unit-a' });

    fireEvent.click(within(row('unit-a')).getByRole('button', { name: 'Download' }));

    await waitFor(() => expect(download).toHaveBeenCalled());
    expect(createUrl).toHaveBeenCalledWith(blob);
    vi.unstubAllGlobals();
  });

  it('never lists projects for a user — the whole router is admin-only', async () => {
    mockSession('user');
    const list = vi.spyOn(endpoints, 'projectList');
    render(
      <TestProviders queryClient={createQueryClient()}>
        <ProjectList />
      </TestProviders>,
    );
    expect(
      await screen.findByText('Somente administradores podem gerenciar projetos.'),
    ).toBeVisible();
    expect(list).not.toHaveBeenCalled();
  });
});

describe('ProjectImportDropzone', () => {
  async function renderDropzone(role: Role = 'admin') {
    mockSession(role);
    render(
      <TestProviders queryClient={createQueryClient()}>
        <ProjectImportDropzone />
      </TestProviders>,
    );
    // The control only exists once GET /auth/me resolves the capability.
    return screen.findByLabelText('Import .spid');
  }

  function upload(input: HTMLElement, name = 'plant.spid') {
    fireEvent.change(input, { target: { files: [new File(['x'], name)] } });
  }

  it('uploads the picked file under its bare name', async () => {
    const importProject = vi
      .spyOn(endpoints, 'importProject')
      .mockResolvedValue({ name: 'plant', path: '/p/plant.spid', controller_count: 0 });
    upload(await renderDropzone());
    await waitFor(() => expect(importProject).toHaveBeenCalled());
    expect(importProject.mock.calls[0][1]).toBe('plant');
  });

  it('explains a rejected archive (400) rather than showing a raw failure', async () => {
    vi.spyOn(endpoints, 'importProject').mockRejectedValue(
      new ApiError(400, 'server', 'not a valid .spid archive'),
    );
    upload(await renderDropzone());
    expect(await screen.findByText('Arquivo .spid inválido.')).toBeVisible();
  });

  it('explains an oversized upload (413) with the server limit, not a 5xx', async () => {
    vi.spyOn(endpoints, 'importProject').mockRejectedValue(
      new ApiError(413, 'server', 'Upload exceeds maximum size of 52428800 bytes'),
    );
    upload(await renderDropzone());
    expect(
      await screen.findByText('O arquivo excede o tamanho máximo aceito pelo servidor.'),
    ).toBeVisible();
  });

  it('offers no upload control to a user', async () => {
    mockSession('user');
    render(
      <TestProviders queryClient={createQueryClient()}>
        <ProjectImportDropzone />
      </TestProviders>,
    );
    await waitFor(() => expect(screen.queryByLabelText('Import .spid')).toBeNull());
  });
});

describe('ProjectsPage creation', () => {
  function renderPage() {
    mockSession('admin');
    vi.spyOn(endpoints, 'projectList').mockResolvedValue({ projects: [] });
    render(
      <TestProviders queryClient={createQueryClient()} initialEntries={['/projects']}>
        <ProjectsPage />
      </TestProviders>,
    );
  }

  it('creates a project from the name field and clears it', async () => {
    const create = vi
      .spyOn(endpoints, 'createProject')
      .mockResolvedValue({ name: 'unit-c', path: '/p/unit-c.spid', controller_count: 0 });
    renderPage();
    const name = await screen.findByLabelText('New project name');

    fireEvent.change(name, { target: { value: 'unit-c' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    await waitFor(() => expect(create).toHaveBeenCalledWith('unit-c'));
    await waitFor(() => expect(name).toHaveValue(''));
  });

  it('keeps the typed name when the backend reports a duplicate (409)', async () => {
    vi.spyOn(endpoints, 'createProject').mockRejectedValue(
      new ApiError(409, 'conflict', 'Project already exists'),
    );
    renderPage();
    const name = await screen.findByLabelText('New project name');

    fireEvent.change(name, { target: { value: 'unit-a' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    expect(await screen.findByText('Já existe um projeto com esse nome.')).toBeVisible();
    expect(name).toHaveValue('unit-a');
  });
});
