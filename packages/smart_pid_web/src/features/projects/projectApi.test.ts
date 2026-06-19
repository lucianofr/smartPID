import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../api/client', () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiDelete: vi.fn(),
  apiUpload: vi.fn(),
  apiDownload: vi.fn(),
  ApiError: class ApiError extends Error {},
}));

import { apiGet, apiPost, apiDelete, apiUpload, apiDownload } from '../../api/client';
import { projectApi } from './projectApi';

beforeEach(() => {
  vi.clearAllMocks();
});

describe('projectApi', () => {
  it('list calls GET /project/list', async () => {
    vi.mocked(apiGet).mockResolvedValue({ projects: [] });
    await projectApi.list();
    expect(apiGet).toHaveBeenCalledWith('/project/list');
  });

  it('create POSTs the name to /project/new', async () => {
    vi.mocked(apiPost).mockResolvedValue({ name: 'p1', path: '/x/p1.spid', controller_count: 0 });
    await projectApi.create('p1');
    expect(apiPost).toHaveBeenCalledWith('/project/new', { name: 'p1' });
  });

  it('open POSTs the name to /project/open', async () => {
    vi.mocked(apiPost).mockResolvedValue({ name: 'p1', path: '/x/p1.spid', controller_count: 2 });
    await projectApi.open('p1');
    expect(apiPost).toHaveBeenCalledWith('/project/open', { name: 'p1' });
  });

  it('import sends multipart FormData with file and name', async () => {
    vi.mocked(apiUpload).mockResolvedValue({ name: 'imp', path: '/x/imp.spid', controller_count: 1 });
    const file = new File([new Uint8Array([1, 2, 3])], 'imp.spid');
    await projectApi.import(file, 'imp');
    const [path, form] = vi.mocked(apiUpload).mock.calls[0];
    expect(path).toBe('/project/import');
    expect(form).toBeInstanceOf(FormData);
    expect((form as FormData).get('name')).toBe('imp');
    expect((form as FormData).get('file')).toBeInstanceOf(File);
  });

  it('remove issues DELETE /project/{name}', async () => {
    vi.mocked(apiDelete).mockResolvedValue(undefined);
    await projectApi.remove('p1');
    expect(apiDelete).toHaveBeenCalledWith(`/project/${encodeURIComponent('p1')}`);
  });

  it('download requests a blob from /project/download', async () => {
    vi.mocked(apiDownload).mockResolvedValue(new Blob([new Uint8Array([1])]));
    const blob = await projectApi.download();
    expect(apiDownload).toHaveBeenCalledWith('/project/download');
    expect(blob).toBeInstanceOf(Blob);
  });
});
