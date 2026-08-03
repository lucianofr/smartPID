import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ExportRequest } from '@/api/types';
import { createQueryClient, TestProviders } from '@/test/providers';
import { ExportButton } from './ExportButton';

const REQUEST: ExportRequest = {
  controller_id: 5,
  start: '2026-07-26T00:00:00Z',
  end: '2026-07-26T01:00:00Z',
};

const JOB = {
  id: 'e1',
  controller_id: 5,
  start: REQUEST.start,
  end: REQUEST.end,
  format: 'csv',
  progress: 0,
  file_path: null,
};

const fetchMock = vi.fn();

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

interface RouteOptions {
  role?: 'admin' | 'user';
  pollStatus?: 'running' | 'done' | 'error';
  downloadFails?: boolean;
}

function route({ role = 'admin', pollStatus = 'done', downloadFails = false }: RouteOptions = {}) {
  fetchMock.mockImplementation((url: string) => {
    if (url.endsWith('/auth/me')) return Promise.resolve(json({ user_id: 1, username: 'a', role }));
    if (url.endsWith('/export/e1/download')) {
      return Promise.resolve(
        downloadFails
          ? new Response('nope', { status: 500 })
          : new Response('timestamp,pv\n0,1\n', { status: 200 }),
      );
    }
    if (url.endsWith('/export/e1')) return Promise.resolve(json({ ...JOB, status: pollStatus }));
    if (url.endsWith('/export')) return Promise.resolve(json({ ...JOB, status: 'running' }, 201));
    return Promise.resolve(json({}));
  });
}

function renderButton(request: ExportRequest | null = REQUEST) {
  render(
    <TestProviders queryClient={createQueryClient()}>
      <ExportButton request={request} />
    </TestProviders>,
  );
}

function exportBody(): unknown {
  const call = fetchMock.mock.calls.find(([url]) => (url as string).endsWith('/api/export'));
  return JSON.parse((call?.[1] as RequestInit).body as string);
}

beforeEach(() => {
  localStorage.setItem('smart-pid-token', 'jwt');
  vi.stubGlobal('fetch', fetchMock);
  vi.stubGlobal('URL', Object.assign(URL, {
    createObjectURL: vi.fn(() => 'blob:export'),
    revokeObjectURL: vi.fn(),
  }));
});

afterEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  fetchMock.mockReset();
  vi.unstubAllGlobals();
});

describe('ExportButton', () => {
  it('posts the permanently singular export DTO', async () => {
    route();
    renderButton();
    fireEvent.click(await screen.findByRole('button', { name: 'Exportar CSV' }));

    await waitFor(() => expect(exportBody()).toBeDefined());
    expect(exportBody()).toEqual({
      controller_id: 5,
      start: '2026-07-26T00:00:00Z',
      end: '2026-07-26T01:00:00Z',
    });
    expect(exportBody()).not.toHaveProperty('controller_ids');
  });

  it('walks create → poll → download without offering an export history', async () => {
    route();
    renderButton();
    fireEvent.click(await screen.findByRole('button', { name: 'Exportar CSV' }));

    const download = await screen.findByRole('button', { name: 'Download CSV' });
    expect(screen.queryByText(/hist[óo]rico de exporta/i)).toBeNull();

    fireEvent.click(download);
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith('/api/export/e1/download', expect.anything()),
    );
    expect(URL.createObjectURL).toHaveBeenCalled();
  });

  it('holds a busy state while the job is still running', async () => {
    route({ pollStatus: 'running' });
    renderButton();
    fireEvent.click(await screen.findByRole('button', { name: 'Exportar CSV' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Gerando…');
  });

  it('offers a retry when the job itself fails', async () => {
    route({ pollStatus: 'error' });
    renderButton();
    fireEvent.click(await screen.findByRole('button', { name: 'Exportar CSV' }));
    expect(await screen.findByRole('button', { name: 'Exportar novamente' })).toBeVisible();
  });

  it('surfaces a failed download instead of doing nothing', async () => {
    route({ downloadFails: true });
    renderButton();
    fireEvent.click(await screen.findByRole('button', { name: 'Exportar CSV' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Download CSV' }));
    expect(
      await screen.findByRole('button', { name: 'Download falhou — repetir' }),
    ).toBeVisible();
  });

  it('cannot be fired without a loop', async () => {
    route();
    renderButton(null);
    expect(await screen.findByRole('button', { name: 'Exportar CSV' })).toBeDisabled();
  });

  it('is available to the operator role too (export.data is not admin-only)', async () => {
    route({ role: 'user' });
    renderButton();
    expect(await screen.findByRole('button', { name: 'Exportar CSV' })).toBeVisible();
  });
});
